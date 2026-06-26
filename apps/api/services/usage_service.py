"""Token usage tracking per user, project, and pipeline run."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import UsageLedger, User


def record_usage(
    db: Session,
    *,
    workspace_id: UUID,
    user_id: UUID | None,
    project_id: UUID | None,
    pipeline_run_id: UUID | None,
    event_type: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    db.add(
        UsageLedger(
            workspace_id=workspace_id,
            user_id=user_id,
            project_id=project_id,
            pipeline_run_id=pipeline_run_id,
            event_type=event_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
    )


def usage_summary_by_user(db: Session, workspace_id: UUID) -> list[dict]:
    rows = (
        db.query(
            UsageLedger.user_id,
            func.coalesce(func.sum(UsageLedger.input_tokens), 0),
            func.coalesce(func.sum(UsageLedger.output_tokens), 0),
            func.coalesce(func.sum(UsageLedger.cost_usd), 0),
            func.count(UsageLedger.id),
        )
        .filter(UsageLedger.workspace_id == workspace_id)
        .group_by(UsageLedger.user_id)
        .all()
    )
    user_ids = [r[0] for r in rows if r[0]]
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    return [
        {
            "user_id": str(uid) if uid else None,
            "user_name": users[uid].full_name if uid and uid in users else "Unknown",
            "user_email": users[uid].email if uid and uid in users else None,
            "input_tokens": int(inp),
            "output_tokens": int(out),
            "total_tokens": int(inp) + int(out),
            "cost_usd": float(cost),
            "events": int(events),
        }
        for uid, inp, out, cost, events in rows
    ]


def usage_summary_by_project(db: Session, workspace_id: UUID) -> list[dict]:
    from models import Project

    rows = (
        db.query(
            UsageLedger.project_id,
            func.coalesce(func.sum(UsageLedger.input_tokens), 0),
            func.coalesce(func.sum(UsageLedger.output_tokens), 0),
            func.coalesce(func.sum(UsageLedger.cost_usd), 0),
            func.count(UsageLedger.id),
        )
        .filter(UsageLedger.workspace_id == workspace_id, UsageLedger.project_id.isnot(None))
        .group_by(UsageLedger.project_id)
        .all()
    )
    project_ids = [r[0] for r in rows if r[0]]
    projects = {p.id: p for p in db.query(Project).filter(Project.id.in_(project_ids)).all()} if project_ids else {}
    return [
        {
            "project_id": str(pid),
            "project_name": projects[pid].name if pid in projects else "Unknown",
            "input_tokens": int(inp),
            "output_tokens": int(out),
            "total_tokens": int(inp) + int(out),
            "cost_usd": float(cost),
            "events": int(events),
        }
        for pid, inp, out, cost, events in rows
    ]


def usage_totals(db: Session, workspace_id: UUID) -> dict:
    row = (
        db.query(
            func.coalesce(func.sum(UsageLedger.input_tokens), 0),
            func.coalesce(func.sum(UsageLedger.output_tokens), 0),
            func.coalesce(func.sum(UsageLedger.cost_usd), 0),
            func.count(UsageLedger.id),
        )
        .filter(UsageLedger.workspace_id == workspace_id)
        .first()
    )
    inp, out, cost, events = row or (0, 0, 0, 0)
    return {
        "input_tokens": int(inp),
        "output_tokens": int(out),
        "total_tokens": int(inp) + int(out),
        "cost_usd": float(cost),
        "events": int(events),
    }
