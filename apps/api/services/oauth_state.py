"""Shared OAuth state storage for integration callbacks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from models.oauth import OAuthState


def create_oauth_state(
    db: Session,
    *,
    user_id,
    workspace_id,
    integration_key: str,
    redirect_path: str | None = None,
) -> str:
    state = uuid4().hex
    db.add(
        OAuthState(
            state=state,
            user_id=user_id,
            workspace_id=workspace_id,
            integration_key=integration_key,
            redirect_path=redirect_path,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    db.commit()
    return state


def consume_oauth_state(db: Session, state: str, *, integration_key: str | None = None) -> OAuthState | None:
    row = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not row:
        return None
    if integration_key and row.integration_key != integration_key:
        return None
    if row.expires_at < datetime.now(UTC):
        db.delete(row)
        db.commit()
        return None
    db.delete(row)
    db.commit()
    return row
