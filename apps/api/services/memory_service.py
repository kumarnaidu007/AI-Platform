"""Cross-run agent memory per project."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from models.rag import AgentMemory


def load_project_memory(db: Session, project_id: UUID) -> dict[str, Any]:
    rows = db.query(AgentMemory).filter(AgentMemory.project_id == project_id).all()
    return {row.memory_key: row.content_json for row in rows}


def save_memory(db: Session, project_id: UUID, memory_key: str, content: dict[str, Any]) -> None:
    row = (
        db.query(AgentMemory)
        .filter(AgentMemory.project_id == project_id, AgentMemory.memory_key == memory_key)
        .first()
    )
    if not row:
        row = AgentMemory(project_id=project_id, memory_key=memory_key, content_json=content)
        db.add(row)
    else:
        row.content_json = {**(row.content_json or {}), **content}
    db.commit()


def append_run_memory(db: Session, project_id: UUID, run_id: UUID, summary: dict[str, Any]) -> None:
    key = "pipeline_history"
    row = (
        db.query(AgentMemory)
        .filter(AgentMemory.project_id == project_id, AgentMemory.memory_key == key)
        .first()
    )
    history = list((row.content_json or {}).get("runs", [])) if row else []
    history.append({"run_id": str(run_id), **summary})
    history = history[-20:]
    save_memory(db, project_id, key, {"runs": history})
