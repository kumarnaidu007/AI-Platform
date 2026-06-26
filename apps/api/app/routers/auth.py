from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import joinedload

from app.deps import AuthContext, DbDep, get_auth_context
from models import AuditEvent, User, Workspace, WorkspaceMember
from schemas.auth import (
    AuthMeResponse,
    LoginRequest,
    LogoutResponse,
    TokenResponse,
    UserResponse,
    WorkspaceContextResponse,
    WorkspaceLoginRequest,
)
from services.auth import create_access_token, revoke_token, verify_password
from services.workspace_helpers import require_default_workspace

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


def _workspace_context(workspace: Workspace, role: str) -> WorkspaceContextResponse:
    domain = workspace.settings.email_domain if workspace.settings else None
    return WorkspaceContextResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        status=workspace.status,
        plan_name=workspace.plan.name if workspace.plan else "",
        role=role,
        email_domain=domain,
    )


def _audit(db, user: User, action: str, request: Request, workspace_id=None) -> None:
    db.add(
        AuditEvent(
            user_id=user.id,
            workspace_id=workspace_id,
            action=action,
            resource_type="user",
            resource_id=user.id,
            ip_address=request.client.host if request.client else None,
        )
    )


@router.post("/admin/login", response_model=TokenResponse)
def admin_login(body: LoginRequest, request: Request, db: DbDep):
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    if not user.is_super_admin:
        raise HTTPException(403, "Super admin access required")

    user.last_login_at = datetime.now(UTC)
    token, _, _ = create_access_token(str(user.id), extra={"portal": "admin"})
    _audit(db, user, "login", request)
    db.commit()
    db.refresh(user)

    return TokenResponse(portal="admin", access_token=token, user=_user_response(user))


@router.post("/workspace/login", response_model=TokenResponse)
def workspace_login(body: WorkspaceLoginRequest, request: Request, db: DbDep):
    workspace = require_default_workspace(db)
    if workspace.status == "suspended":
        raise HTTPException(403, "Workspace is suspended")

    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    if user.is_super_admin:
        raise HTTPException(403, "Use the super admin sign-in for platform administration")

    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace.id, WorkspaceMember.user_id == user.id)
        .first()
    )
    if not membership:
        raise HTTPException(403, "You are not a member of this workspace")

    user.last_login_at = datetime.now(UTC)
    token, _, _ = create_access_token(
        str(user.id),
        extra={
            "portal": "workspace",
            "workspace_id": str(workspace.id),
            "workspace_slug": workspace.slug,
            "role": membership.role,
        },
    )
    _audit(db, user, "login", request, workspace_id=workspace.id)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        portal="workspace",
        access_token=token,
        user=_user_response(user),
        workspace=_workspace_context(workspace, membership.role),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    db: DbDep,
    ctx: AuthContext = Depends(get_auth_context),
):
    if ctx.jti and ctx.token_exp:
        expires_at = datetime.fromtimestamp(ctx.token_exp, tz=UTC)
        revoke_token(db, ctx.jti, expires_at)

    workspace_id = ctx.workspace_id if ctx.portal == "workspace" else None
    _audit(db, ctx.user, "logout", request, workspace_id=workspace_id)
    db.commit()
    return LogoutResponse()


@router.get("/me", response_model=AuthMeResponse)
def me(db: DbDep, ctx: AuthContext = Depends(get_auth_context)):
    workspace_ctx = None
    if ctx.portal == "workspace" and ctx.workspace_id:
        workspace = (
            db.query(Workspace)
            .options(joinedload(Workspace.plan), joinedload(Workspace.settings))
            .filter(Workspace.id == ctx.workspace_id)
            .first()
        )
        if workspace:
            membership = (
                db.query(WorkspaceMember)
                .filter(WorkspaceMember.workspace_id == workspace.id, WorkspaceMember.user_id == ctx.user.id)
                .first()
            )
            if membership:
                workspace_ctx = _workspace_context(workspace, membership.role)

    return AuthMeResponse(
        portal=ctx.portal,
        user=_user_response(ctx.user),
        workspace=workspace_ctx,
    )
