"""LangGraph-style pipeline orchestration with approval, retry, and parallel steps."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from agents.context import PipelineContext
from agents.handlers import AGENT_RUNNERS, AgentRunResult, ReviewRejected

logger = logging.getLogger(__name__)

PLANNING_AGENTS = frozenset({"requirements", "architecture", "task_planner"})
REVIEW_LOOP = ("code_writer", "review")
PARALLEL_GROUPS: list[frozenset[str]] = [
    frozenset({"test_writer", "deploy"}),
]
MAX_REVIEW_RETRIES = 3


class ApprovalRequired(Exception):
    """Raised when pipeline pauses for human approval after planning phase."""

    def __init__(self, plan: dict[str, Any]):
        self.plan = plan
        super().__init__("Pipeline awaiting human approval")


def _ordered_keys(agent_keys: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for key in agent_keys:
        if key not in seen:
            ordered.append(key)
            seen.add(key)
    return ordered


def _group_parallel_keys(agent_keys: list[str]) -> list[list[str]]:
    """Expand agent list into sequential steps; parallel groups run together."""
    remaining = _ordered_keys(agent_keys)
    steps: list[list[str]] = []
    while remaining:
        matched = False
        for group in PARALLEL_GROUPS:
            if group.issubset(set(remaining)):
                batch = [k for k in remaining if k in group]
                steps.append(batch)
                remaining = [k for k in remaining if k not in group]
                matched = True
                break
        if not matched:
            steps.append([remaining[0]])
            remaining = remaining[1:]
    return steps


def run_planning_phase(
    db: Session,
    ctx: PipelineContext,
    agent_keys: list[str],
    *,
    before_step: Callable[[str], None],
    after_step: Callable[[str, AgentRunResult], None],
) -> dict[str, Any]:
    for key in agent_keys:
        if key not in PLANNING_AGENTS:
            continue
        runner = AGENT_RUNNERS[key]
        before_step(key)
        result = runner(db, ctx)
        after_step(key, result)
    return build_approval_plan(ctx)


def build_approval_plan(ctx: PipelineContext) -> dict[str, Any]:
    return {
        "summary": (ctx.prd or {}).get("summary") or ctx.requirements_text[:500],
        "goals": (ctx.prd or {}).get("goals", []),
        "tasks": ctx.tasks,
        "architecture_summary": (ctx.architecture or {}).get("summary"),
        "api_endpoints": (ctx.architecture or {}).get("api_endpoints", []),
        "acceptance_criteria": (ctx.prd or {}).get("acceptance_criteria", []),
    }


def run_development_phase(
    db: Session,
    ctx: PipelineContext,
    agent_keys: list[str],
    *,
    before_step: Callable[[str], None],
    after_step: Callable[[str, AgentRunResult], None],
    start_after: str | None = None,
) -> None:
    keys = _ordered_keys(agent_keys)
    if start_after and start_after in keys:
        keys = keys[keys.index(start_after) + 1 :]

    i = 0
    while i < len(keys):
        key = keys[i]
        if key == "code_writer":
            _run_review_loop(db, ctx, keys, before_step=before_step, after_step=after_step)
            while i < len(keys) and keys[i] in REVIEW_LOOP:
                i += 1
            continue
        if key in REVIEW_LOOP:
            i += 1
            continue

        batch_started = False
        for group in PARALLEL_GROUPS:
            if key in group:
                batch = [k for k in keys[i:] if k in group]
                _run_parallel_batch(db, ctx, batch, before_step=before_step, after_step=after_step)
                i += len(batch)
                batch_started = True
                break
        if batch_started:
            continue

        runner = AGENT_RUNNERS.get(key)
        if not runner:
            raise ValueError(f"Unknown agent: {key}")
        before_step(key)
        result = runner(db, ctx)
        after_step(key, result)
        i += 1


def _run_review_loop(
    db: Session,
    ctx: PipelineContext,
    agent_keys: list[str],
    *,
    before_step: Callable[[str], None],
    after_step: Callable[[str, AgentRunResult], None],
) -> None:
    include_review = "review" in agent_keys
    max_attempts = MAX_REVIEW_RETRIES if include_review else 1
    for attempt in range(max_attempts):
        ctx.review_retry_count = attempt
        before_step("code_writer")
        code_result = AGENT_RUNNERS["code_writer"](db, ctx)
        after_step("code_writer", code_result)

        if not include_review:
            return

        before_step("review")
        try:
            review_result = AGENT_RUNNERS["review"](db, ctx)
            after_step("review", review_result)
            verdict = (review_result.output.get("reviews") or [{}])[0].get("verdict", "approved")
            if verdict != "changes_requested":
                return
            logger.info("Review requested changes (attempt %s/%s)", attempt + 1, MAX_REVIEW_RETRIES)
        except ReviewRejected:
            logger.info("Review rejected (attempt %s/%s)", attempt + 1, MAX_REVIEW_RETRIES)
    raise RuntimeError(f"Code review failed after {MAX_REVIEW_RETRIES} attempts")


def _run_parallel_batch(
    db: Session,
    ctx: PipelineContext,
    keys: list[str],
    *,
    before_step: Callable[[str], None],
    after_step: Callable[[str, AgentRunResult], None],
) -> None:
    """Run a batch of independent agents (sequential DB session; grouped for orchestration)."""
    for agent_key in keys:
        runner = AGENT_RUNNERS[agent_key]
        before_step(agent_key)
        result = runner(db, ctx)
        after_step(agent_key, result)


def run_full_pipeline(
    db: Session,
    ctx: PipelineContext,
    agent_keys: list[str],
    *,
    before_step: Callable[[str], None],
    after_step: Callable[[str, AgentRunResult], None],
    skip_planning: bool = False,
    approved: bool = False,
) -> None:
    keys = _ordered_keys(agent_keys)
    has_planning = any(k in PLANNING_AGENTS for k in keys)

    if has_planning and not skip_planning and not approved:
        plan = run_planning_phase(db, ctx, keys, before_step=before_step, after_step=after_step)
        raise ApprovalRequired(plan)

    dev_keys = [k for k in keys if k not in PLANNING_AGENTS or (skip_planning and k in PLANNING_AGENTS)]
    if not skip_planning:
        dev_keys = [k for k in keys if k not in PLANNING_AGENTS]
    run_development_phase(db, ctx, dev_keys, before_step=before_step, after_step=after_step)
