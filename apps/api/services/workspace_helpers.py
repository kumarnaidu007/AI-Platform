"""Single-workspace helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from models import Workspace

DEFAULT_WORKSPACE_SLUG = "workspace"


def get_default_workspace(db: Session) -> Workspace | None:
    return (
        db.query(Workspace)
        .options(joinedload(Workspace.plan), joinedload(Workspace.settings))
        .filter(Workspace.slug == DEFAULT_WORKSPACE_SLUG)
        .first()
    )


def require_default_workspace(db: Session) -> Workspace:
    workspace = get_default_workspace(db)
    if not workspace:
        raise RuntimeError("Default workspace is not configured. Run database migrations.")
    return workspace
