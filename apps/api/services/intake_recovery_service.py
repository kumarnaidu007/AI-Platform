"""Recover pending code changes for intakes that completed before local publish storage."""

from __future__ import annotations

import logging
import re
from uuid import UUID

from sqlalchemy.orm import Session

from models import AgentLog, PipelineRun, PipelineStep
from models.requirements import JiraTicketIntake
from services.github_service import (
    GitHubError,
    branch_exists,
    get_file_content,
    get_github_access_token,
    get_github_connection,
    get_pull_request,
    parse_repo_url,
)

logger = logging.getLogger(__name__)


def _latest_code_writer_output(db: Session, pipeline_run_id: UUID) -> dict | None:
    row = (
        db.query(AgentLog.output_json)
        .join(PipelineStep, PipelineStep.id == AgentLog.pipeline_step_id)
        .filter(
            PipelineStep.pipeline_run_id == pipeline_run_id,
            PipelineStep.step_name == "code_writer",
        )
        .order_by(AgentLog.created_at.desc())
        .first()
    )
    return row[0] if row and isinstance(row[0], dict) else None


def _pending_from_output(output: dict) -> dict | None:
    pending = output.get("pending_publish")
    if isinstance(pending, dict) and pending.get("files"):
        return pending
    return None


def _pr_meta_from_output(output: dict) -> dict | None:
    prs = output.get("pull_requests")
    if isinstance(prs, list) and prs and isinstance(prs[0], dict):
        return prs[0]
    return None


def _normalize_branch_name(branch: str | None) -> str | None:
    if not branch:
        return None
    return re.sub(r"-retry\d+$", "", branch)


def _fetch_files_for_paths(
    token: str,
    repo_ref,
    paths: list[str],
    *,
    git_ref: str,
) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for raw_path in paths:
        path = str(raw_path).lstrip("/")
        if not path:
            continue
        try:
            content = get_file_content(token, repo_ref, path, branch=git_ref)
        except GitHubError:
            continue
        if content:
            files.append({"path": path, "content": content, "message": f"recover: update {path}"})
    return files


def _recover_from_github_pr(token: str, repo_url: str, pr_meta: dict) -> dict | None:
    repo_ref = parse_repo_url(repo_url)
    paths = pr_meta.get("files_changed") or []
    if not paths:
        return None

    branch = _normalize_branch_name(pr_meta.get("branch_name"))
    commit_sha: str | None = None
    pr_number = pr_meta.get("number")
    if pr_number:
        try:
            pr = get_pull_request(token, repo_ref, int(pr_number))
            commit_sha = pr.get("head", {}).get("sha")
            branch = branch or pr.get("head", {}).get("ref")
        except GitHubError as exc:
            logger.warning("Could not load PR #%s for recovery: %s", pr_number, exc)

    files: list[dict[str, str]] = []
    if branch and branch_exists(token, repo_ref, branch):
        files = _fetch_files_for_paths(token, repo_ref, paths, git_ref=branch)
    if not files and commit_sha:
        files = _fetch_files_for_paths(token, repo_ref, paths, git_ref=commit_sha)

    if not files:
        return None

    return {
        "branch_name": branch or pr_meta.get("branch_name"),
        "base_branch": pr_meta.get("base_branch") or "main",
        "pr_title": pr_meta.get("title") or "feat: recovered changes",
        "pr_body": pr_meta.get("summary") or "",
        "files": files,
        "summary": pr_meta.get("summary") or "Recovered from previous pipeline run",
        "repo_url": repo_url,
        "recovered_from": "github_pr",
    }


def recover_intake_pending_changes(db: Session, intake: JiraTicketIntake, user_id: UUID) -> JiraTicketIntake:
    """Load pending file changes from DB logs or GitHub when missing on the intake row."""
    if intake.pending_publish_json and intake.pending_publish_json.get("files"):
        return intake
    if intake.status != "awaiting_pr_review" or not intake.pipeline_run_id:
        return intake

    pending: dict | None = None

    run = db.query(PipelineRun).filter(PipelineRun.id == intake.pipeline_run_id).first()
    if run and isinstance(run.graph_state_json, dict):
        graph_pending = run.graph_state_json.get("pending_publish")
        if isinstance(graph_pending, dict) and graph_pending.get("files"):
            pending = graph_pending

    output = _latest_code_writer_output(db, intake.pipeline_run_id)
    if not pending and output:
        pending = _pending_from_output(output)

    if not pending and output:
        pr_meta = _pr_meta_from_output(output)
        repo_url = intake.repo_url or (output.get("repo_url") if output else None)
        if pr_meta and repo_url:
            conn = get_github_connection(db, intake.workspace_id, user_id)
            if conn:
                token = get_github_access_token(conn)
                pending = _recover_from_github_pr(token, repo_url, pr_meta)

    if not pending and run and isinstance(run.graph_state_json, dict):
        pr_meta = _pr_meta_from_output(run.graph_state_json)
        repo_url = intake.repo_url
        if pr_meta and repo_url:
            conn = get_github_connection(db, intake.workspace_id, user_id)
            if conn:
                token = get_github_access_token(conn)
                pending = _recover_from_github_pr(token, repo_url, pr_meta)

    if not pending:
        raise ValueError(
            "Could not recover file changes. The GitHub branch may have been deleted and no local copy exists. "
            "Re-run implementation to regenerate the code."
        )

    branch = _normalize_branch_name(pending.get("branch_name"))
    if branch:
        pending = {**pending, "branch_name": branch}

    intake.pending_publish_json = pending
    intake.feature_branch = branch or intake.feature_branch
    intake.base_branch = pending.get("base_branch") or intake.base_branch
    db.commit()
    db.refresh(intake)
    return intake
