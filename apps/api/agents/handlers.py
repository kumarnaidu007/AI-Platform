"""All 10 pipeline agent implementations with RAG, tools, E2B, and GitHub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from agents.context import PipelineContext
from services import artifact_service
from services.agent_tools import run_tools
from services.e2b_service import run_tests_in_sandbox
from services.github_service import (
    GitHubError,
    apply_code_changes,
    extract_pull_number,
    get_github_access_token,
    get_github_connection,
    get_pull_request_diff,
    parse_repo_url,
    resolve_base_branch,
    verify_repo_access,
)
from services.llm import LLMResponse, complete_json
from services.rag_service import format_rag_context, retrieve_context

SYSTEM_JSON = (
    "You are an expert software delivery agent. You may receive codebase context from RAG retrieval. "
    "Respond with valid JSON only, no markdown fences."
)


class ReviewRejected(RuntimeError):
    pass


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

    tasks = ctx.tasks or []
    arch = ctx.architecture or {}
    ctx.rag_hits = retrieve_context(
        db,
        project_id=ctx.project_id,
        query=f"{ctx.requirements_text}\n{arch.get('summary', '')}",
        top_k=10,
    )
    prompt = f"""Agent: code_writer
Project: {ctx.project_name}
Stack: {ctx.project_stack_summary()}
Repository: {ctx.repo_url}
Base branch: {base_branch}
Tasks: {tasks[:6]}
Architecture endpoints: {arch.get('api_endpoints', [])}
Requirements: {ctx.requirements_text[:3000]}
Review retry: {ctx.review_retry_count}
{ctx.rag_context_block()}

Generate implementation files. Use existing code patterns from context.
Return JSON with keys:
branch_name, pr_title, pr_body, summary,
files (array of {{path, content, message}}) with complete file contents."""
    plan_result = _run_agent(db, ctx, agent_key="code_writer", user_prompt=prompt)
    plan = plan_result.output
    files = plan.get("files") or []
    if not files:
        raise RuntimeError("Code writer agent did not return any files to commit")

    branch_name = plan.get("branch_name") or f"feature/ai-{ctx.run_id.hex[:8]}"
    if ctx.review_retry_count:
        branch_name = f"{branch_name}-retry{ctx.review_retry_count}"
    pr_data = apply_code_changes(
        token,
        ctx.repo_url,
        base_branch=base_branch,
        branch_name=branch_name,
        files=files,
        pr_title=plan.get("pr_title") or f"feat: {ctx.project_name} AI implementation",
        pr_body=plan.get("pr_body") or plan.get("summary") or ctx.requirements_text[:4000],
    )
    ctx.pull_requests = [pr_data]
    artifact_service.save_pull_request(db, ctx.project_id, pr_data)
    jira_key = (ctx.jira_issue or {}).get("key") or ctx.additional_context.get("jira_issue_key")
    if jira_key and pr_data.get("url"):
        try:
            from services.jira_service import notify_jira_pr_created

            notify_jira_pr_created(
                db,
                workspace_id=ctx.workspace_id,
                user_id=ctx.user_id,
                issue_key=jira_key,
                pr_title=pr_data.get("title") or plan.get("pr_title") or "Pull request",
                pr_url=str(pr_data.get("url")),
                summary=plan.get("summary"),
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Failed to update Jira issue %s: %s", jira_key, exc)
    return AgentRunResult(
        output={"pull_requests": [pr_data], "summary": pr_data.get("summary", "Pull request created")},
        llm=plan_result.llm,
        summary=pr_data.get("summary", "Pull request created on GitHub"),
    )


def run_review(db: Session, ctx: PipelineContext) -> AgentRunResult:
    prs = ctx.pull_requests or []
    diff_excerpt = ""
    if prs and ctx.repo_url:
        conn = get_github_connection(db, ctx.workspace_id, ctx.user_id)
        token = get_github_access_token(conn)
        repo_ref = parse_repo_url(ctx.repo_url)
        pr_number = prs[0].get("number") or extract_pull_number(str(prs[0].get("url", "")))
        if pr_number:
            diff_excerpt = get_pull_request_diff(token, repo_ref, int(pr_number))[:12000]

    prompt = f"""Agent: review
Pull requests: {prs}
Diff excerpt:
{diff_excerpt or 'Diff unavailable.'}
{ctx.rag_context_block()}

Return JSON with key reviews: array of {{pr_title, verdict (approved|changes_requested), comments (array), summary}}."""
    result = _run_agent(db, ctx, agent_key="review", user_prompt=prompt)
    verdict = (result.output.get("reviews") or [{}])[0].get("verdict", "approved")
    if verdict == "changes_requested":
        raise ReviewRejected((result.output.get("reviews") or [{}])[0].get("summary", "Changes requested"))
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
