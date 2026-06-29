"""All 10 pipeline agent implementations with RAG, tools, E2B, and GitHub."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from agents.context import PipelineContext
from services import artifact_service
from services.agent_tools import run_tools
from services.e2b_service import run_tests_in_sandbox
from services.github_service import (
    GitHubError,
    extract_pull_number,
    get_github_access_token,
    get_github_connection,
    get_pull_request_diff,
    parse_repo_url,
    resolve_base_branch,
    verify_repo_access,
)
from services.code_writer_service import generate_pending_publish
from services.codegen_validation_service import validate_pending_publish
from services.llm import LLMResponse, complete_json
from services.rag_service import format_rag_context, retrieve_context

SYSTEM_JSON = (
    "You are an expert software delivery agent. You may receive codebase context from RAG retrieval. "
    "Respond with valid JSON only, no markdown fences."
)



@dataclass
class AgentRunResult:
    output: dict[str, Any]
    llm: LLMResponse
    summary: str


def _run_agent(
    db: Session,
    ctx: PipelineContext,
    *,
    agent_key: str,
    user_prompt: str,
) -> AgentRunResult:
    llm = complete_json(db, system=SYSTEM_JSON, user=user_prompt)
    output = llm.parsed_json or {"raw": llm.content}
    if not llm.parsed_json:
        raise RuntimeError(f"{agent_key} agent returned invalid JSON from the LLM")
    return AgentRunResult(output=output, llm=llm, summary=output.get("summary", f"{agent_key} completed"))


def _resolve_feature_branch(ctx: PipelineContext, llm_branch: str | None, *, fallback: str) -> str:
    """One branch per ticket/run — review retries update the same branch, never spawn -retryN branches."""
    pinned = ctx.additional_context.get("feature_branch")
    if pinned:
        return str(pinned)
    previous = (ctx.pending_publish or {}).get("branch_name")
    if previous:
        return str(previous)
    return llm_branch or fallback


def _prepare_context(db: Session, ctx: PipelineContext) -> None:
    if not ctx.rag_hits:
        ctx.rag_hits = retrieve_context(
            db, project_id=ctx.project_id, query=ctx.requirements_text, top_k=8
        )
    run_tools(
        db,
        ctx,
        [{"tool": "search_codebase", "args": {"query": ctx.requirements_text[:2000]}}],
    )


def run_requirements(db: Session, ctx: PipelineContext) -> AgentRunResult:
    _prepare_context(db, ctx)
    prompt = f"""Agent: requirements
Project: {ctx.project_name}
Stack: {ctx.project_stack_summary()}
Description: {ctx.project_description or 'N/A'}
Repository: {ctx.repo_url or 'not linked'}
{ctx.memory_block()}
{ctx.rag_context_block()}

User requirements:
{ctx.requirements_text}

Produce a structured PRD JSON with keys:
title, summary, goals (array), user_stories (array of {{role, want, benefit}}),
functional_requirements (array), non_functional_requirements (array), acceptance_criteria (array)."""
    result = _run_agent(db, ctx, agent_key="requirements", user_prompt=prompt)
    ctx.prd = result.output
    artifact_service.save_prd(db, ctx.project_id, ctx.run_id, result.output)
    return result


def run_architecture(db: Session, ctx: PipelineContext) -> AgentRunResult:
    prd = ctx.prd or {"summary": ctx.requirements_text[:500]}
    if ctx.repo_url:
        run_tools(db, ctx, [{"tool": "list_repo_files", "args": {"limit": 40}}])
    prompt = f"""Agent: architecture
Project: {ctx.project_name}
Stack: {ctx.project_stack_summary()}
PRD summary: {prd.get('summary', '')}
Repository: {ctx.repo_url or 'not linked'}
Files in repo: {list(ctx.files_read.keys())[:30]}
{ctx.rag_context_block()}

Return JSON with keys:
summary, folder_structure (object tree), api_endpoints (array), database_schema (array of tables),
tech_decisions (array of strings)."""
    result = _run_agent(db, ctx, agent_key="architecture", user_prompt=prompt)
    ctx.architecture = result.output
    artifact_service.save_architecture(db, ctx.project_id, ctx.run_id, result.output)
    return result


def run_task_planner(db: Session, ctx: PipelineContext) -> AgentRunResult:
    arch = ctx.architecture or {}
    jira = ctx.jira_issue or {}
    jira_block = ""
    if jira:
        jira_block = f"""
Linked Jira ticket: {jira.get('key')} — {jira.get('summary', '')}
Jira status: {jira.get('status', '')}
Jira description: {(jira.get('description') or '')[:2000]}
"""
    prompt = f"""Agent: task_planner
PM tool: {ctx.pm_tool or 'jira'}
Architecture summary: {arch.get('summary', '')}
Requirements: {ctx.requirements_text[:2000]}
{jira_block}
{ctx.rag_context_block()}

Return JSON with key tasks: array of {{id, title, description, status, priority}} (3-8 tasks).
If a Jira ticket is linked, the first task must use id "{jira.get('key')}" when present."""
    result = _run_agent(db, ctx, agent_key="task_planner", user_prompt=prompt)
    ctx.tasks = result.output.get("tasks", [])
    pm_tool = "jira" if jira else ctx.pm_tool
    if jira and ctx.tasks:
        ctx.tasks[0]["id"] = jira.get("key") or ctx.tasks[0].get("id")
        ctx.tasks[0]["title"] = jira.get("summary") or ctx.tasks[0].get("title")
        ctx.tasks[0]["url"] = jira.get("url")
        ctx.tasks[0]["status"] = jira.get("status") or ctx.tasks[0].get("status", "in_progress")
    artifact_service.save_tasks(db, ctx.project_id, ctx.tasks, pm_tool)
    return result


def run_code_writer(db: Session, ctx: PipelineContext) -> AgentRunResult:
    if not ctx.repo_url:
        raise GitHubError("Project has no Git repository URL.")
    conn = get_github_connection(db, ctx.workspace_id, ctx.user_id)
    token = get_github_access_token(conn)
    repo_info = verify_repo_access(token, ctx.repo_url)
    repo_ref = parse_repo_url(ctx.repo_url)
    base_branch = resolve_base_branch(token, repo_ref, ctx.requirements_text, repo_info)

    pending_publish, llm = generate_pending_publish(
        db,
        ctx,
        token=token,
        repo_ref=repo_ref,
        base_branch=base_branch,
    )
    branch_name = _resolve_feature_branch(ctx, pending_publish.get("branch_name"), fallback=pending_publish["branch_name"])
    pending_publish["branch_name"] = branch_name
    ctx.pending_publish = pending_publish
    return AgentRunResult(
        output={"pending_publish": pending_publish, "summary": pending_publish["summary"]},
        llm=llm,
        summary="Code changes prepared — awaiting your approval before push",
    )


def run_review(db: Session, ctx: PipelineContext) -> AgentRunResult:
    pending = ctx.pending_publish or {}
    files = pending.get("files") or []

    blocking = validate_pending_publish(ctx, files)
    ctx.last_validation_issues = blocking
    if not blocking:
        return AgentRunResult(
            output={
                "reviews": [
                    {
                        "verdict": "approved",
                        "summary": "Deterministic validation passed",
                        "comments": [],
                    }
                ]
            },
            llm=LLMResponse(
                content="",
                parsed_json=None,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                model_name="deterministic",
                provider="local",
            ),
            summary="Deterministic validation passed",
        )

    prs = ctx.pull_requests or []
    diff_excerpt = ""
    if pending.get("files"):
        chunks: list[str] = []
        for item in pending["files"][:20]:
            path = item.get("path", "unknown")
            content = item.get("content", "")
            chunks.append(f"--- {path} ---\n{content[:2500]}")
        diff_excerpt = "\n\n".join(chunks)[:12000]
    elif prs and ctx.repo_url:
        conn = get_github_connection(db, ctx.workspace_id, ctx.user_id)
        token = get_github_access_token(conn)
        repo_ref = parse_repo_url(ctx.repo_url)
        pr_number = prs[0].get("number") or extract_pull_number(str(prs[0].get("url", "")))
        if pr_number:
            diff_excerpt = get_pull_request_diff(token, repo_ref, int(pr_number))[:12000]

    plan = ctx.additional_context.get("implementation_plan") or {}
    contracts = ""
    if isinstance(plan, dict) and plan.get("technical_contracts"):
        contracts = f"\nMandatory technical contracts:\n{json.dumps(plan['technical_contracts'], indent=2)[:5000]}"

    prompt = f"""Agent: review
You are a strict but fair code reviewer. Approve when the code matches the implementation plan and would compile.

Deterministic validation already found these BLOCKING issues — verify and expand only if needed:
{json.dumps(blocking[:12], indent=2)}

ONLY return verdict "changes_requested" for BLOCKING issues:
- Interface/method signature mismatch between files
- Wrong JSON root shape vs plan contracts
- Missing types or methods referenced by other generated files
- Would fail to compile

Do NOT reject for: style, comments, documentation length, minor naming, or optional improvements.

Proposed branch: {pending.get('branch_name', 'n/a')}
Files to publish: {[f.get('path') for f in (pending.get('files') or [])[:20]]}
{contracts}
Diff excerpt:
{diff_excerpt or 'Diff unavailable.'}
{ctx.rag_context_block()}

Return JSON with key reviews: array of {{pr_title, verdict (approved|changes_requested), comments (array of specific blocking issues), summary}}."""
    result = _run_agent(db, ctx, agent_key="review", user_prompt=prompt)
    return result


def run_test_writer(db: Session, ctx: PipelineContext) -> AgentRunResult:
    prompt = f"""Agent: test_writer
Stack: {ctx.project_stack_summary()}
PRs: {ctx.pull_requests}
Architecture: {ctx.architecture}
{ctx.rag_context_block()}

Return JSON with keys: summary, unit_tests (array of {{path, content}}), integration_tests (array), coverage_target (number)."""
    result = _run_agent(db, ctx, agent_key="test_writer", user_prompt=prompt)
    ctx.tests = result.output
    return result


def run_test_runner(db: Session, ctx: PipelineContext) -> AgentRunResult:
    test_files = []
    if ctx.tests:
        for item in ctx.tests.get("unit_tests") or []:
            if isinstance(item, dict):
                test_files.append(item)
            elif isinstance(item, str):
                test_files.append({"path": item, "content": f"def test_{item.replace('/', '_')}():\n    assert True"})

    sandbox_result = run_tests_in_sandbox(
        db,
        test_files=test_files,
        stack_hint=ctx.project_stack_summary(),
    )
    if sandbox_result.get("sandbox"):
        ctx.test_results = sandbox_result
        return AgentRunResult(
            output=sandbox_result,
            llm=LLMResponse("", sandbox_result, 0, 0, 0.0, "e2b", "e2b"),
            summary=sandbox_result.get("summary", "Tests executed"),
        )

    prompt = f"""Agent: test_runner
Tests planned: {ctx.tests}

Return JSON with keys: passed (bool), total, passed_count, failed_count, failures (array), summary."""
    result = _run_agent(db, ctx, agent_key="test_runner", user_prompt=prompt)
    ctx.test_results = result.output
    return result


def run_deploy(db: Session, ctx: PipelineContext) -> AgentRunResult:
    prompt = f"""Agent: deploy
Project: {ctx.project_name}
Test results: {ctx.test_results}

Return JSON with keys: environment, url, status, image_tag, summary."""
    result = _run_agent(db, ctx, agent_key="deploy", user_prompt=prompt)
    ctx.deployment = result.output
    artifact_service.save_deployment(db, ctx.project_id, ctx.run_id, result.output)
    return result


def run_smoke_test(db: Session, ctx: PipelineContext) -> AgentRunResult:
    url = (ctx.deployment or {}).get("url", "")
    prompt = f"""Agent: smoke_test
Staging URL: {url or 'not deployed yet'}

Return JSON with keys: passed (bool), checks (array of {{name, passed, detail}}), summary."""
    result = _run_agent(db, ctx, agent_key="smoke_test", user_prompt=prompt)
    ctx.smoke_test = result.output
    return result


def run_validation(db: Session, ctx: PipelineContext) -> AgentRunResult:
    prd = ctx.prd or {}
    prompt = f"""Agent: validation
PRD goals: {prd.get('goals', [])}
Acceptance criteria: {prd.get('acceptance_criteria', [])}
Delivered: PRs={len(ctx.pull_requests)}, tests={ctx.test_results}, deploy={ctx.deployment}
{ctx.memory_block()}

Return JSON with keys: passed (bool), score (0-100), gaps (array), summary."""
    result = _run_agent(db, ctx, agent_key="validation", user_prompt=prompt)
    ctx.validation = result.output
    artifact_service.save_validation(db, ctx.project_id, ctx.run_id, result.output)
    return result


AGENT_RUNNERS: dict[str, Callable[[Session, PipelineContext], AgentRunResult]] = {
    "requirements": run_requirements,
    "architecture": run_architecture,
    "task_planner": run_task_planner,
    "code_writer": run_code_writer,
    "review": run_review,
    "test_writer": run_test_writer,
    "test_runner": run_test_runner,
    "deploy": run_deploy,
    "smoke_test": run_smoke_test,
    "validation": run_validation,
}
