"""Platform agent catalog helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from models.agents import PlatformAgent


def agent_is_assignable(agent: PlatformAgent) -> bool:
    return agent.is_enabled


def agent_to_dict(agent: PlatformAgent) -> dict[str, Any]:
    metadata = agent.metadata_json or {}
    return {
        "id": agent.id,
        "agent_key": agent.agent_key,
        "name": agent.name,
        "description": agent.description,
        "category": agent.category,
        "default_step_order": agent.default_step_order,
        "is_enabled": agent.is_enabled,
        "group": metadata.get("group", agent.category.title()),
        "artifact": metadata.get("artifact"),
        "metadata": metadata,
    }


def list_platform_agents(db: Session) -> list[PlatformAgent]:
    return (
        db.query(PlatformAgent)
        .order_by(PlatformAgent.default_step_order, PlatformAgent.name)
        .all()
    )
