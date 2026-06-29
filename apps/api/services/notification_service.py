"""In-app workspace notifications."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from models.requirements import WorkspaceNotification


def notify_user(
    db: Session,
    *,
    workspace_id: UUID,
    user_id: UUID,
    notification_type: str,
    title: str,
    body: str | None = None,
    link_path: str | None = None,
    intake_id: UUID | None = None,
) -> WorkspaceNotification:
    row = WorkspaceNotification(
        workspace_id=workspace_id,
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        link_path=link_path,
        intake_id=intake_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_notifications(db: Session, user_id: UUID, *, unread_only: bool = False, limit: int = 50) -> list[WorkspaceNotification]:
    q = db.query(WorkspaceNotification).filter(WorkspaceNotification.user_id == user_id)
    if unread_only:
        q = q.filter(WorkspaceNotification.is_read.is_(False))
    return q.order_by(WorkspaceNotification.created_at.desc()).limit(limit).all()


def unread_count(db: Session, user_id: UUID) -> int:
    return (
        db.query(WorkspaceNotification)
        .filter(WorkspaceNotification.user_id == user_id, WorkspaceNotification.is_read.is_(False))
        .count()
    )


def mark_read(db: Session, user_id: UUID, notification_id: UUID) -> WorkspaceNotification | None:
    row = (
        db.query(WorkspaceNotification)
        .filter(WorkspaceNotification.id == notification_id, WorkspaceNotification.user_id == user_id)
        .first()
    )
    if not row:
        return None
    row.is_read = True
    db.commit()
    db.refresh(row)
    return row


def mark_all_read(db: Session, user_id: UUID) -> int:
    rows = db.query(WorkspaceNotification).filter(
        WorkspaceNotification.user_id == user_id, WorkspaceNotification.is_read.is_(False)
    ).all()
    for row in rows:
        row.is_read = True
    db.commit()
    return len(rows)
