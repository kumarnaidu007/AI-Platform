from typing import Annotated
from collections.abc import Generator
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from constants.roles import TEAM_LEAD
from db.session import SessionLocal
from models import User, Workspace, WorkspaceMember
from services.auth import decode_access_token, is_token_revoked

security = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    portal: str
    workspace_id: UUID | None = None
    workspace_slug: str | None = None
    member_role: str | None = None
    jti: str | None = None
    token_exp: int | None = None


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbDep = Annotated[Session, Depends(get_db)]


def get_auth_context(
    db: DbDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> AuthContext:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
        portal = payload.get("portal", "admin")
        jti = payload.get("jti")
        token_exp = payload.get("exp")
    except (ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from None

    if is_token_revoked(db, jti):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has been revoked")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    workspace_id = payload.get("workspace_id") or payload.get("company_id")
    workspace_slug = payload.get("workspace_slug") or payload.get("company_slug")
    return AuthContext(
        user=user,
        portal=portal,
        workspace_id=UUID(workspace_id) if workspace_id else None,
        workspace_slug=workspace_slug,
        member_role=payload.get("role"),
        jti=jti,
        token_exp=token_exp,
    )


def get_current_user(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> User:
    return ctx.user


def require_super_admin(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> User:
    if ctx.portal != "admin" or not ctx.user.is_super_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin access required")
    return ctx.user


def require_workspace_member(
    db: DbDep,
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthContext:
    if ctx.portal == "admin" and ctx.user.is_super_admin:
        from services.workspace_helpers import require_default_workspace

        workspace = require_default_workspace(db)
        ctx.workspace_id = workspace.id
        ctx.workspace_slug = workspace.slug
        ctx.member_role = TEAM_LEAD
        return ctx

    if ctx.portal != "workspace" or not ctx.workspace_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Workspace access required")

    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == ctx.user.id, WorkspaceMember.workspace_id == ctx.workspace_id)
        .first()
    )
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this workspace")

    workspace = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    if not workspace or workspace.status == "suspended":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Workspace is suspended or not found")

    ctx.member_role = membership.role
    return ctx


CurrentUserDep = Annotated[User, Depends(get_current_user)]
SuperAdminDep = Annotated[User, Depends(require_super_admin)]
WorkspaceAuthDep = Annotated[AuthContext, Depends(require_workspace_member)]


def require_team_lead(ctx: WorkspaceAuthDep) -> AuthContext:
    if ctx.member_role != TEAM_LEAD:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Team lead access required")
    return ctx


TeamLeadDep = Annotated[AuthContext, Depends(require_team_lead)]
WorkspaceAdminDep = TeamLeadDep


def require_workspace_writer(ctx: WorkspaceAuthDep) -> AuthContext:
    return ctx


WorkspaceWriterDep = Annotated[AuthContext, Depends(require_workspace_writer)]
