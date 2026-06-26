"""Sequential pipeline agent executor."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from agents.context import PipelineContext
from agents.handlers import AGENT_RUNNERS, AgentRunResult


def run_agent_sequence(
    db: Session,
    ctx: PipelineContext,
    agent_keys: list[str],
    *,
    before_step: Callable[[str], None] | None = None,
    after_step: Callable[[str, AgentRunResult], None] | None = None,
) -> PipelineContext:
    for agent_key in agent_keys:
        runner = AGENT_RUNNERS.get(agent_key)
        if not runner:
            raise ValueError(f"Unknown agent: {agent_key}")
        if before_step:
            before_step(agent_key)
        result = runner(db, ctx)
        if after_step:
            after_step(agent_key, result)
    return ctx
