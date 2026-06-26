from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.deps import DbDep, WorkspaceAuthDep, WorkspaceWriterDep
from config import settings
from services.jira_service import (
    JiraError,
    get_issue,
    get_jira_connection,
    get_jira_tokens,
    get_platform_jira_config,
    list_projects,
    search_issues,
    start_jira_oauth,
    user_has_jira_assigned,
)
from services.secrets import decrypt_secrets

router = APIRouter(prefix="/api/workspace/jira", tags=["workspace-jira"])


class JiraOAuthStartResponse(BaseModel):
    authorize_url: str


class JiraConnectionStatus(BaseModel):
    is_assigned: bool
    is_connected: bool
    connection_status: str
    jira_site_name: str | None = None
    oauth_available: bool
    message: str | None = None


class JiraProjectItem(BaseModel):
    id: str | None = None
    key: str | None = None
    name: str | None = None


class JiraIssueItem(BaseModel):
    id: str | None = None
    key: str | None = None
    summary: str | None = None
    description: str | None = None
    issue_type: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    reporter: str | None = None
    project_key: str | None = None
    project_name: str | None = None
    url: str | None = None


def _jira_tokens_or_400(db, ctx) -> tuple[dict[str, str], str | None]:
    if not user_has_jira_assigned(db, ctx.workspace_id, ctx.user.id):
        raise HTTPException(400, "Jira has not been assigned to your account")
    conn = get_jira_connection(db, ctx.workspace_id, ctx.user.id)
    try:
        tokens = get_jira_tokens(conn)
    except JiraError as exc:
        raise HTTPException(400, str(exc)) from exc
    metadata = (conn.config_metadata_json or {}) if conn else {}
    site_url = metadata.get("jira_site_url")
    return tokens, site_url


@router.get("/status", response_model=JiraConnectionStatus)
def jira_status(ctx: WorkspaceAuthDep, db: DbDep):
    assigned = user_has_jira_assigned(db, ctx.workspace_id, ctx.user.id)
    conn = get_jira_connection(db, ctx.workspace_id, ctx.user.id)
    config = get_platform_jira_config(db)
    tokens = decrypt_secrets(conn.encrypted_config_ref) if conn and conn.encrypted_config_ref else {}
    is_connected = bool(conn and conn.status == "connected" and tokens.get("access_token"))
    metadata = (conn.config_metadata_json or {}) if conn else {}
    return JiraConnectionStatus(
        is_assigned=assigned,
        is_connected=is_connected,
        connection_status=conn.status if conn else "not_configured",
        jira_site_name=metadata.get("jira_site_name") or None,
        oauth_available=bool(config),
        message=None if assigned else "Jira has not been assigned to your account",
    )


@router.get("/oauth/start", response_model=JiraOAuthStartResponse)
def jira_oauth_start(
    ctx: WorkspaceWriterDep,
    db: DbDep,
    redirect_path: str | None = Query(None),
):
    path = redirect_path or f"{settings.web_base_url}/workspace/integrations/jira"
    try:
        authorize_url = start_jira_oauth(
            db,
            user_id=ctx.user.id,
            workspace_id=ctx.workspace_id,
            redirect_path=path,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JiraOAuthStartResponse(authorize_url=authorize_url)


@router.post("/disconnect", response_model=JiraConnectionStatus)
def jira_disconnect(ctx: WorkspaceWriterDep, db: DbDep):
    conn = get_jira_connection(db, ctx.workspace_id, ctx.user.id)
    if conn:
        db.delete(conn)
        db.commit()
    return jira_status(ctx, db)


@router.get("/projects", response_model=list[JiraProjectItem])
def jira_list_projects(ctx: WorkspaceAuthDep, db: DbDep):
    tokens, _ = _jira_tokens_or_400(db, ctx)
    return [
        JiraProjectItem(**row)
        for row in list_projects(tokens["access_token"], tokens["cloud_id"])
    ]


@router.get("/issues", response_model=list[JiraIssueItem])
def jira_list_issues(
    ctx: WorkspaceAuthDep,
    db: DbDep,
    project_key: str | None = Query(None),
    jql: str | None = Query(None),
    max_results: int = Query(30, ge=1, le=100),
):
    tokens, site_url = _jira_tokens_or_400(db, ctx)
    try:
        rows = search_issues(
            tokens["access_token"],
            tokens["cloud_id"],
            project_key=project_key,
            jql=jql,
            max_results=max_results,
            site_url=site_url,
        )
    except JiraError as exc:
        raise HTTPException(400, str(exc)) from exc
    return [JiraIssueItem(**row) for row in rows]


@router.get("/issues/{issue_key}", response_model=JiraIssueItem)
def jira_get_issue(issue_key: str, ctx: WorkspaceAuthDep, db: DbDep):
    tokens, site_url = _jira_tokens_or_400(db, ctx)
    try:
        row = get_issue(tokens["access_token"], tokens["cloud_id"], issue_key, site_url=site_url)
    except JiraError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JiraIssueItem(**row)
