from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.deps import WorkspaceAuthDep, WorkspaceWriterDep, DbDep
from config import settings
from services.github_service import (
    get_github_access_token,
    get_github_connection,
    get_platform_github_config,
    list_user_repos,
    start_github_oauth,
    user_has_github_assigned,
    verify_repo_access,
)
from services.secrets import decrypt_secrets

router = APIRouter(prefix="/api/workspace/github", tags=["workspace-github"])


class GitHubOAuthStartResponse(BaseModel):
    authorize_url: str


class GitHubConnectionStatus(BaseModel):
    is_assigned: bool
    is_connected: bool
    connection_status: str
    github_login: str | None = None
    oauth_available: bool
    message: str | None = None


class GitHubRepoItem(BaseModel):
    full_name: str
    html_url: str
    default_branch: str
    private: bool


class GitHubRepoVerifyResponse(BaseModel):
    owner: str
    repo: str
    full_name: str
    default_branch: str
    private: bool
    html_url: str | None = None


@router.get("/status", response_model=GitHubConnectionStatus)
def github_status(ctx : WorkspaceAuthDep, db: DbDep):
    assigned = user_has_github_assigned(db, ctx.workspace_id, ctx.user.id)
    conn = get_github_connection(db, ctx.workspace_id, ctx.user.id)
    config = get_platform_github_config(db)
    tokens = decrypt_secrets(conn.encrypted_config_ref) if conn and conn.encrypted_config_ref else {}
    is_connected = bool(conn and conn.status == "connected" and tokens.get("access_token"))
    metadata = (conn.config_metadata_json or {}) if conn else {}
    return GitHubConnectionStatus(
        is_assigned=assigned,
        is_connected=is_connected,
        connection_status=conn.status if conn else "not_configured",
        github_login=metadata.get("github_login") or None,
        oauth_available=bool(config),
        message=None if assigned else "GitHub has not been assigned to your account",
    )


@router.get("/oauth/start", response_model=GitHubOAuthStartResponse)
def github_oauth_start(
    ctx : WorkspaceWriterDep,
    db: DbDep,
    redirect_path: str | None = Query(None),
):
    path = redirect_path or f"{settings.web_base_url}/workspace/integrations/github"
    try:
        authorize_url = start_github_oauth(
            db,
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
            redirect_path=path,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return GitHubOAuthStartResponse(authorize_url=authorize_url)


@router.post("/disconnect", response_model=GitHubConnectionStatus)
def github_disconnect(ctx : WorkspaceWriterDep, db: DbDep):
    conn = get_github_connection(db, ctx.workspace_id, ctx.user.id)
    if conn:
        db.delete(conn)
        db.commit()
    return github_status(ctx, db)


@router.get("/repos", response_model=list[GitHubRepoItem])
def github_list_repos(ctx : WorkspaceAuthDep, db: DbDep):
    conn = get_github_connection(db, ctx.workspace_id, ctx.user.id)
    token = get_github_access_token(conn)
    return [GitHubRepoItem(**row) for row in list_user_repos(token)]


@router.get("/repos/verify", response_model=GitHubRepoVerifyResponse)
def github_verify_repo(ctx : WorkspaceAuthDep, db: DbDep, repo_url: str = Query(..., min_length=3)):
    conn = get_github_connection(db, ctx.workspace_id, ctx.user.id)
    token = get_github_access_token(conn)
    try:
        info = verify_repo_access(token, repo_url)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return GitHubRepoVerifyResponse(**info)
