"""Plan-driven code generation: tiered parallel file generation with deterministic validation."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from sqlalchemy.orm import Session

from agents.context import PipelineContext
from db.session import SessionLocal
from services.codegen_validation_service import (
    expand_regen_dependents,
    file_specific_rules,
    generation_priority,
    should_skip_rag_indexing,
    sort_entries_for_generation,
    validate_pending_publish,
)
from services.github_service import GitHubError, get_file_content
from services.llm import LLMResponse, complete_json
from services.implementation_plan_service import (
    contracts_block,
    ensure_plan_ready_for_codegen,
    fix_generation_issues,
    review_feedback_block,
    prior_file_signatures,
)
from services.rag_service import format_rag_context, retrieve_context

logger = logging.getLogger(__name__)


def _emit_progress(ctx: PipelineContext, event: str, **payload: Any) -> None:
    """Write incremental progress so the UI shows activity while code_writer runs."""
    if ctx.progress_callback is None:
        return
    try:
        ctx.progress_callback(event, payload)
    except Exception as exc:
        logger.warning("Progress callback failed for %s: %s", event, exc)

SYSTEM_JSON = (
    "You are an expert software engineer. Follow the specification exactly. "
    "Respond with valid JSON only, no markdown fences."
)

LARGE_FILE_HINTS = (".json", "countries", "seed", "migration")
PARALLEL_WORKERS = 2
FILE_GEN_MAX_ATTEMPTS = 3


def _implementation_plan(ctx: PipelineContext) -> dict[str, Any]:
    plan = ctx.additional_context.get("implementation_plan")
    return plan if isinstance(plan, dict) else {}


def _planned_file_entries(ctx: PipelineContext) -> list[dict[str, str]]:
    plan = _implementation_plan(ctx)
    entries: list[dict[str, str]] = []
    for item in plan.get("files_to_create") or []:
        if isinstance(item, dict) and item.get("path"):
            entries.append(
                {
                    "path": str(item["path"]).lstrip("/"),
                    "purpose": str(item.get("purpose") or ""),
                    "action": "create",
                }
            )
    for item in plan.get("files_to_modify") or []:
        if isinstance(item, dict) and item.get("path"):
            entries.append(
                {
                    "path": str(item["path"]).lstrip("/"),
                    "purpose": str(item.get("purpose") or ""),
                    "action": "modify",
                }
            )
    return entries


def _spec_block(ctx: PipelineContext, *, max_chars: int = 14000) -> str:
    plan = _implementation_plan(ctx)
    jira_key = ctx.additional_context.get("jira_issue_key") or ""
    parts = [
        f"Jira ticket: {jira_key}",
        f"Project: {ctx.project_name}",
        f"Stack: {ctx.project_stack_summary()}",
        f"Repository: {ctx.repo_url or 'n/a'}",
    ]
    if plan.get("summary"):
        parts.append(f"Plan summary: {plan['summary']}")
    if plan.get("steps"):
        parts.append(f"Plan steps: {json.dumps(plan['steps'][:12])}")
    specs = ctx.additional_context.get("spec_documents")
    if isinstance(specs, dict):
        for doc_type, content in specs.items():
            parts.append(f"\n## {str(doc_type).upper()} SPEC\n{json.dumps(content)[:4000]}")
    parts.append(f"\n## REQUIREMENTS\n{ctx.requirements_text[:max_chars]}")
    return "\n".join(parts)[:max_chars + 8000]


def _default_branch_name(ctx: PipelineContext) -> str:
    pinned = ctx.additional_context.get("feature_branch")
    if pinned:
        return str(pinned)
    previous = (ctx.pending_publish or {}).get("branch_name")
    if previous:
        return str(previous)
    jira_key = str(ctx.additional_context.get("jira_issue_key") or "").upper()
    if jira_key:
        slug = jira_key.lower().replace(" ", "-")
        return f"feature/{slug}"
    return f"feature/ai-{ctx.run_id.hex[:8]}"


def _is_large_file(path: str) -> bool:
    lower = path.lower()
    return any(hint in lower for hint in LARGE_FILE_HINTS)


def _merge_llm_responses(responses: list[LLMResponse]) -> LLMResponse:
    if not responses:
        return LLMResponse("", None, 0, 0, 0.0, "none", "none")
    if len(responses) == 1:
        return responses[0]
    return LLMResponse(
        content=responses[-1].content,
        parsed_json=responses[-1].parsed_json,
        input_tokens=sum(r.input_tokens for r in responses),
        output_tokens=sum(r.output_tokens for r in responses),
        cost_usd=round(sum(r.cost_usd for r in responses), 6),
        model_name=responses[-1].model_name,
        provider=responses[-1].provider,
    )


def _generate_publish_metadata(
    db: Session,
    ctx: PipelineContext,
    *,
    base_branch: str,
    file_paths: list[str],
) -> dict[str, Any]:
    jira_key = ctx.additional_context.get("jira_issue_key") or ""
    plan = _implementation_plan(ctx)
    default_branch = _default_branch_name(ctx)
    prompt = f"""Agent: code_writer_metadata
Jira: {jira_key}
Base branch: {base_branch}
Suggested feature branch: {default_branch}
Files changed: {file_paths[:20]}
Plan summary: {plan.get('summary', '')[:1500]}

Return JSON with keys only:
branch_name (string, use suggested branch unless plan specifies otherwise),
pr_title (string),
pr_body (string, include Jira link text),
summary (string, one paragraph)."""
    llm = complete_json(db, system=SYSTEM_JSON, user=prompt, max_completion_tokens=2048)
    if not llm.parsed_json:
        return {
            "branch_name": default_branch,
            "pr_title": f"{jira_key}: implementation" if jira_key else f"feat: {ctx.project_name}",
            "pr_body": plan.get("summary") or ctx.requirements_text[:2000],
            "summary": plan.get("summary") or "Implementation ready for review",
        }
    data = llm.parsed_json
    return {
        "branch_name": data.get("branch_name") or default_branch,
        "pr_title": data.get("pr_title") or f"feat: {ctx.project_name}",
        "pr_body": data.get("pr_body") or data.get("summary") or "",
        "summary": data.get("summary") or "Code changes ready for your review",
    }


def _generate_single_file(
    db: Session,
    ctx: PipelineContext,
    *,
    entry: dict[str, str],
    base_branch: str,
    existing_content: str,
    prior_files: list[dict[str, str]],
    rag_block: str,
) -> tuple[dict[str, str], LLMResponse]:
    path = entry["path"]
    action = entry["action"]
    purpose = entry["purpose"]
    large = _is_large_file(path)

    prior_summary = prior_file_signatures(prior_files)

    existing_block = ""
    if action == "modify" and existing_content:
        cap = 6000 if not large else 3000
        existing_block = f"\nCurrent file content (apply minimal edits, preserve style):\n{existing_content[:cap]}\n"

    size_hint = (
        "For JSON data files: include a representative subset of ~30-50 entries if the full ISO list "
        "would be too large; structure must be production-ready and documented in a comment at top."
        if large and path.endswith(".json")
        else "Return the complete file content."
    )

    plan = _implementation_plan(ctx)
    contracts = contracts_block(plan)
    feedback = review_feedback_block(ctx)
    per_file_rules = file_specific_rules(path)

    prompt = f"""Agent: code_writer_file
Generate exactly ONE file.

Path: {path}
Action: {action}
Purpose: {purpose}
Base branch: {base_branch}
Review retry: {ctx.review_retry_count}
{size_hint}
{contracts}
{feedback}
{f"FILE-SPECIFIC RULES (mandatory):\\n{per_file_rules}" if per_file_rules else ""}

{prior_summary}
{rag_block}

Specification:
{_spec_block(ctx, max_chars=8000)}
{existing_block}

CRITICAL: Match interface names, method signatures, and JSON shapes from technical contracts and already-generated files exactly.
Do NOT use reflection in controllers. Implement interfaces explicitly.

Return JSON with keys:
path (must match exactly),
content (complete file source code or JSON text),
message (short git commit message)."""

    max_tokens = 16384 if large else 8192
    llm = complete_json(db, system=SYSTEM_JSON, user=prompt, max_completion_tokens=max_tokens, retries=3)
    if not llm.parsed_json:
        raise RuntimeError(f"Code writer could not generate valid JSON for file: {path}")

    data = llm.parsed_json
    content = str(data.get("content") or "")
    if not content.strip():
        raise RuntimeError(f"Code writer returned empty content for file: {path}")

    file_item = {
        "path": path,
        "content": content,
        "message": str(data.get("message") or f"feat: update {path}"),
    }
    return file_item, llm


def _discover_files_from_plan_fallback(db: Session, ctx: PipelineContext) -> list[dict[str, str]]:
    """When no file list in plan, ask LLM for paths only (small JSON)."""
    prompt = f"""Agent: code_writer_plan
Based on the specification, list files to create or modify.
Do NOT include file contents.

{_spec_block(ctx, max_chars=6000)}

Return JSON with key files: array of {{path, purpose, action (create|modify)}} (max 12 files)."""
    llm = complete_json(db, system=SYSTEM_JSON, user=prompt, max_completion_tokens=4096, retries=2)
    if not llm.parsed_json:
        raise RuntimeError("Code writer could not determine which files to generate")
    entries: list[dict[str, str]] = []
    for item in llm.parsed_json.get("files") or []:
        if isinstance(item, dict) and item.get("path"):
            entries.append(
                {
                    "path": str(item["path"]).lstrip("/"),
                    "purpose": str(item.get("purpose") or ""),
                    "action": str(item.get("action") or "create"),
                }
            )
    if not entries:
        raise RuntimeError("Code writer plan contained no files")
    return entries


def _paths_to_regenerate(ctx: PipelineContext, entries: list[dict[str, str]]) -> set[str] | None:
    """None means regenerate all files; otherwise only the returned paths."""
    if ctx.review_retry_count == 0:
        return None

    all_paths = [e["path"] for e in entries]
    paths: set[str] = set()

    for issue in ctx.last_validation_issues or []:
        if issue.get("file"):
            paths.add(issue["file"])

    for fb in ctx.review_feedback:
        for comment in fb.get("comments") or []:
            text = str(comment)
            for p in all_paths:
                basename = p.split("/")[-1]
                if p in text or basename in text:
                    paths.add(p)

    if not paths:
        paths = {p for p in all_paths if p.endswith((".cs", ".json"))}

    return expand_regen_dependents(paths, all_paths)


def _generate_file_worker(
    entry: dict[str, str],
    *,
    ctx: PipelineContext,
    base_branch: str,
    existing_content: str,
    prior_files: list[dict[str, str]],
    rag_block: str,
) -> tuple[dict[str, str], LLMResponse]:
    """Thread worker — each call uses its own DB session for LLM config."""
    from services.llm import _is_transient_http_error

    last_exc: Exception | None = None
    for attempt in range(FILE_GEN_MAX_ATTEMPTS):
        db = SessionLocal()
        try:
            return _generate_single_file(
                db,
                ctx,
                entry=entry,
                base_branch=base_branch,
                existing_content=existing_content,
                prior_files=prior_files,
                rag_block=rag_block,
            )
        except Exception as exc:
            last_exc = exc
            if _is_transient_http_error(exc) and attempt < FILE_GEN_MAX_ATTEMPTS - 1:
                logger.warning(
                    "Transient LLM error for %s (attempt %s/%s): %s",
                    entry["path"],
                    attempt + 1,
                    FILE_GEN_MAX_ATTEMPTS,
                    exc,
                )
                time.sleep(min(2 ** attempt * 3, 30))
                continue
            raise
        finally:
            db.close()
    raise RuntimeError(f"Code writer failed for {entry['path']}: {last_exc}") from last_exc


def _generate_tier_parallel(
    entries: list[dict[str, str]],
    *,
    ctx: PipelineContext,
    base_branch: str,
    token: str,
    repo_ref,
    prior_files: list[dict[str, str]],
    rag_block: str,
) -> tuple[list[dict[str, str]], list[LLMResponse]]:
    if len(entries) <= 1:
        results: list[tuple[dict[str, str], LLMResponse]] = []
        for entry in entries:
            existing = ""
            if entry["action"] == "modify":
                try:
                    existing = get_file_content(token, repo_ref, entry["path"], branch=base_branch)
                except GitHubError:
                    pass
            file_result = _generate_file_worker(
                entry,
                ctx=ctx,
                base_branch=base_branch,
                existing_content=existing,
                prior_files=prior_files + [r[0] for r in results],
                rag_block=rag_block,
            )
            results.append(file_result)
            file_item, file_llm = file_result
            _emit_progress(
                ctx,
                "file_generated",
                path=entry["path"],
                lines=len(file_item["content"].splitlines()),
                tokens_in=file_llm.input_tokens,
                tokens_out=file_llm.output_tokens,
            )
        files = [r[0] for r in results]
        return files, [r[1] for r in results]

    futures = {}
    with ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS, len(entries))) as pool:
        for entry in entries:
            existing = ""
            if entry["action"] == "modify":
                try:
                    existing = get_file_content(token, repo_ref, entry["path"], branch=base_branch)
                except GitHubError:
                    pass
            future = pool.submit(
                _generate_file_worker,
                entry,
                ctx=ctx,
                base_branch=base_branch,
                existing_content=existing,
                prior_files=prior_files,
                rag_block=rag_block,
            )
            futures[future] = entry["path"]

        results: list[tuple[dict[str, str], LLMResponse]] = []
        for future in as_completed(futures):
            path = futures[future]
            try:
                file_item, file_llm = future.result()
                results.append((file_item, file_llm))
                _emit_progress(
                    ctx,
                    "file_generated",
                    path=path,
                    lines=len(file_item["content"].splitlines()),
                    tokens_in=file_llm.input_tokens,
                    tokens_out=file_llm.output_tokens,
                )
                logger.info("Generated file %s", path)
            except Exception as exc:
                raise RuntimeError(f"Code writer failed for {path}: {exc}") from exc

    results.sort(key=lambda r: generation_priority(r[0]["path"]))
    return [r[0] for r in results], [r[1] for r in results]


def generate_pending_publish(
    db: Session,
    ctx: PipelineContext,
    *,
    token: str,
    repo_ref,
    base_branch: str,
) -> tuple[dict[str, Any], LLMResponse]:
    """Build pending_publish using the approved implementation plan."""
    _emit_progress(ctx, "started", retry=ctx.review_retry_count)
    ensure_plan_ready_for_codegen(db, ctx)
    _emit_progress(ctx, "plan_ready")

    if should_skip_rag_indexing(ctx):
        ctx.rag_hits = []
        rag_block = ""
        _emit_progress(ctx, "skip_rag")
        logger.info("Skipping RAG retrieval for planned intake implementation")
    else:
        ctx.rag_hits = retrieve_context(
            db,
            project_id=ctx.project_id,
            query=ctx.requirements_text[:3000],
            top_k=8,
        )
        rag_block = ""
        if ctx.rag_hits:
            rag_block = "\nRelevant codebase context:\n" + format_rag_context(ctx.rag_hits[:6])

    entries = sort_entries_for_generation(_planned_file_entries(ctx))
    if not entries:
        logger.warning("No files in implementation plan; falling back to LLM file discovery")
        entries = sort_entries_for_generation(_discover_files_from_plan_fallback(db, ctx))

    _emit_progress(
        ctx,
        "files_planned",
        total=len(entries),
        paths=[e["path"] for e in entries],
    )

    regen_paths = _paths_to_regenerate(ctx, entries)
    reuse_by_path: dict[str, dict[str, str]] = {}
    if regen_paths is not None and ctx.pending_publish:
        for item in ctx.pending_publish.get("files") or []:
            if isinstance(item, dict) and item.get("path"):
                reuse_by_path[str(item["path"])] = item

    generated: list[dict[str, str]] = []
    if reuse_by_path and regen_paths is not None:
        for entry in entries:
            path = entry["path"]
            if path not in regen_paths and path in reuse_by_path:
                generated.append(reuse_by_path[path])

    llm_responses: list[LLMResponse] = []

    tiers: dict[int, list[dict[str, str]]] = {}
    for entry in entries:
        if regen_paths is not None and entry["path"] not in regen_paths and entry["path"] in reuse_by_path:
            continue
        tier = generation_priority(entry["path"])[0]
        tiers.setdefault(tier, []).append(entry)

    for tier in sorted(tiers.keys()):
        tier_entries = tiers[tier]
        _emit_progress(
            ctx,
            "tier_started",
            tier=tier,
            files=[e["path"] for e in tier_entries],
            completed=len(generated),
            total=len(entries),
        )
        tier_files, tier_llms = _generate_tier_parallel(
            tiers[tier],
            ctx=ctx,
            base_branch=base_branch,
            token=token,
            repo_ref=repo_ref,
            prior_files=generated,
            rag_block=rag_block,
        )
        generated.extend(tier_files)
        llm_responses.extend(tier_llms)
        generated.sort(key=lambda f: generation_priority(f["path"]))

    # Deterministic validation + targeted auto-fix (no slow LLM consistency pass)
    fix_llm: LLMResponse | None = None
    for fix_round in range(2):
        blocking = validate_pending_publish(ctx, generated)
        ctx.last_validation_issues = blocking
        _emit_progress(ctx, "validating", round=fix_round + 1, issues=len(blocking))
        if not blocking:
            break
        logger.warning(
            "Blocking validation issues (round %s): %s",
            fix_round + 1,
            blocking,
        )
        generated, fix_llm = fix_generation_issues(db, ctx, generated, blocking)
        _emit_progress(ctx, "fixing", round=fix_round + 1, files=[i["file"] for i in blocking[:8]])
        if fix_llm:
            llm_responses.append(fix_llm)

    ctx.last_validation_issues = validate_pending_publish(ctx, generated)

    _emit_progress(ctx, "metadata")
    meta = _generate_publish_metadata(
        db,
        ctx,
        base_branch=base_branch,
        file_paths=[f["path"] for f in generated],
    )
    llm_responses.append(
        LLMResponse("", meta, 0, 0, 0.0, llm_responses[-1].provider if llm_responses else "none", "meta")
    )

    pending = {
        "branch_name": meta["branch_name"],
        "base_branch": base_branch,
        "pr_title": meta["pr_title"],
        "pr_body": meta["pr_body"],
        "files": generated,
        "summary": meta["summary"],
        "repo_url": ctx.repo_url,
    }
    _emit_progress(ctx, "completed", file_count=len(generated))
    return pending, _merge_llm_responses(llm_responses)
