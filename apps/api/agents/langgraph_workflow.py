"""
LangGraph orchestration layer.

Pipeline state is checkpointed in `pipeline_runs.graph_state_json` and threaded via
`langgraph_thread_id`. The workflow in `agents.workflow` implements planning approval
gates, review retry loops, and parallel agent batches.
"""

from __future__ import annotations

from typing import Any, TypedDict

from agents.context import PipelineContext


class GraphState(TypedDict, total=False):
    """LangGraph-compatible state snapshot."""

    run_id: str
    requirements_text: str
    approved: bool
    review_retry_count: int
    checkpoint: dict[str, Any]


def state_from_context(ctx: PipelineContext, *, approved: bool = False) -> GraphState:
    return {
        "run_id": str(ctx.run_id),
        "requirements_text": ctx.requirements_text,
        "approved": approved,
        "review_retry_count": ctx.review_retry_count,
        "checkpoint": ctx.to_checkpoint(),
    }


def apply_state_to_context(ctx: PipelineContext, state: GraphState) -> PipelineContext:
    if state.get("checkpoint"):
        ctx = PipelineContext.from_checkpoint(ctx, state["checkpoint"])
    ctx.review_retry_count = int(state.get("review_retry_count") or 0)
    return ctx
