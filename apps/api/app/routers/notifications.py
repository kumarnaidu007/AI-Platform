from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.deps import DbDep, WorkspaceAuthDep, WorkspaceWriterDep
from schemas.requirements import NotificationResponse
from services.notification_service import list_notifications, mark_all_read, mark_read, unread_count

router = APIRouter(prefix="/api/workspace/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def get_notifications(ctx: WorkspaceAuthDep, db: DbDep, unread_only: bool = False):
    rows = list_notifications(db, ctx.user.id, unread_only=unread_only)
    return [
        NotificationResponse(
            id=r.id,
            notification_type=r.notification_type,
            title=r.title,
            body=r.body,
            link_path=r.link_path,
            intake_id=r.intake_id,
            is_read=r.is_read,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/unread-count")
def get_unread_count(ctx: WorkspaceAuthDep, db: DbDep):
    return {"count": unread_count(db, ctx.user.id)}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(notification_id: UUID, ctx: WorkspaceWriterDep, db: DbDep):
    row = mark_read(db, ctx.user.id, notification_id)
    if not row:
        raise HTTPException(404, "Notification not found")
    return NotificationResponse(
        id=row.id,
        notification_type=row.notification_type,
        title=row.title,
        body=row.body,
        link_path=row.link_path,
        intake_id=row.intake_id,
        is_read=row.is_read,
        created_at=row.created_at,
    )


@router.post("/read-all")
def read_all(ctx: WorkspaceWriterDep, db: DbDep):
    return {"updated": mark_all_read(db, ctx.user.id)}
