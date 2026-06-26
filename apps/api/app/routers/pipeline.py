from fastapi import APIRouter, HTTPException

from app.deps import WorkspaceAuthDep, WorkspaceWriterDep, DbDep
from models import PipelineRun, Project
from schemas.pipeline import (
    PipelineApprovalRequest,
    PipelineRunDetailResponse,
    PipelineRunSummaryResponse,
    PipelineStartRequest,
)
from services.pipeline_service import (
    approve_pipeline_run,
    get_run_detail,
    reject_pipeline_run,
    start_pipeline_run,
    summarize_run,
)

router = APIRouter(prefix="/api/workspace", tags=["pipeline"])


def _get_project(db, workspace_id, project_id: str) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.workspace_id == workspace_id)
        .first()
    )
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _get_run(db, project: Project, run_id: str) -> PipelineRun:
    run = (
        db.query(PipelineRun)
        .filter(PipelineRun.id == run_id, PipelineRun.project_id == project.id)
        .first()
    )
    if not run:
        raise HTTPException(404, "Pipeline run not found")
    return run


@router.post("/projects/{project_id}/runs", response_model=PipelineRunSummaryResponse)
def create_pipeline_run(
    project_id: str,
    body: PipelineStartRequest,
    ctx : WorkspaceWriterDep,
    db: DbDep,
):
    from models import Workspace
    from sqlalchemy.orm import joinedload
    from services.github_service import get_github_access_token, get_github_connection
    from services.jira_service import (
        JiraError,
        build_requirements_from_issue,
        get_issue,
        get_jira_connection,
        get_jira_tokens,
        user_has_jira_assigned,
    )

    project = _get_project(db, ctx.workspace_id, project_id)
    workspace = (
        db.query(Workspace)
        .options(joinedload(Workspace.limits))
        .filter(Workspace.id == ctx.workspace_id)
        .first()
    )
    if not workspace:
        raise HTTPException(404, "Workspace not found")

    requirements_text = body.requirements_text
    additional_context = dict(body.additional_context or {})
    jira_issue_key = (body.jira_issue_key or "").strip().upper() or None

    if jira_issue_key:
        if not user_has_jira_assigned(db, ctx.workspace_id, ctx.user.id):
            raise HTTPException(400, "Jira has not been assigned to your account")
        conn = get_jira_connection(db, ctx.workspace_id, ctx.user.id)
        try:
            tokens = get_jira_tokens(conn)
            metadata = (conn.config_metadata_json or {}) if conn else {}
            issue = get_issue(
                tokens["access_token"],
                tokens["cloud_id"],
                jira_issue_key,
                site_url=metadata.get("jira_site_url"),
            )
        except JiraError as exc:
            raise HTTPException(400, str(exc)) from exc
        requirements_text = build_requirements_from_issue(issue, body.requirements_text)
        additional_context["jira_issue"] = issue
        additional_context["jira_issue_key"] = jira_issue_key

    gh_conn = get_github_connection(db, ctx.workspace_id, ctx.user.id)
    try:
        get_github_access_token(gh_conn)
    except Exception as exc:
        raise HTTPException(400, "Connect GitHub under My Integrations before starting a pipeline.") from exc
    if not project.repo_url:
        raise HTTPException(400, "Set a Git repository URL on this project before starting a pipeline.")

    try:
        run = start_pipeline_run(
            db,
            project=project,
            workspace=workspace,
            user_id=ctx.user.id,
            requirements_text=requirements_text,
            additional_context=additional_context,
            agent_keys=body.agent_keys,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return summarize_run(db, run)


@router.get("/projects/{project_id}/runs/{run_id}", response_model=PipelineRunDetailResponse)
def get_pipeline_run(project_id: str, run_id: str, ctx : WorkspaceAuthDep, db: DbDep):
    project = _get_project(db, ctx.workspace_id, project_id)
    run = _get_run(db, project, run_id)
    return get_run_detail(db, run)


@router.post("/projects/{project_id}/runs/{run_id}/approve", response_model=PipelineRunSummaryResponse)
def approve_pipeline(project_id: str, run_id: str, ctx : WorkspaceWriterDep, db: DbDep, body: PipelineApprovalRequest | None = None):
    project = _get_project(db, ctx.workspace_id, project_id)
    run = _get_run(db, project, run_id)
    try:
        run = approve_pipeline_run(db, run)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return summarize_run(db, run)


@router.post("/projects/{project_id}/runs/{run_id}/reject", response_model=PipelineRunSummaryResponse)
def reject_pipeline(project_id: str, run_id: str, ctx : WorkspaceWriterDep, db: DbDep, body: PipelineApprovalRequest | None = None):
    project = _get_project(db, ctx.workspace_id, project_id)
    run = _get_run(db, project, run_id)
    try:
        run = reject_pipeline_run(db, run, reason=body.comment if body else None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return summarize_run(db, run)
