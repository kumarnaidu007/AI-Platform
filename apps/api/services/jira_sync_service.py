"""Sync platform intake lifecycle events to Jira issue status and comments."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from services.jira_service import (
    JiraError,
    add_issue_comment,
    call_with_jira_tokens,
    get_issue,
    get_jira_connection,
    transition_issue_by_names,
)

logger = logging.getLogger(__name__)

# Fuzzy transition name groups (first match wins per Jira workflow)
TRANSITION_IN_PROGRESS = ("In Progress", "In Development", "Start Progress", "Implementing")
TRANSITION_CODE_REVIEW = ("Code Review", "In Review", "Review", "Ready for Review")
TRANSITION_DONE = ("Done", "Closed", "Resolved", "Complete")


def _jira_actor_user_id(intake) -> UUID:
    """User whose Jira OAuth token to use for sync."""
    return intake.assignee_user_id or intake.user_id


def refresh_intake_jira_status(
    db: Session,
    *,
    workspace_id: UUID,
    user_id: UUID,
    issue_key: str,
) -> str | None:
    """Pull latest status name from Jira and return it."""
    conn = get_jira_connection(db, workspace_id, user_id)
    if not conn:
        return None
    metadata = conn.config_metadata_json or {}
    site_url = metadata.get("jira_site_url")

    def _fetch(tokens: dict[str, str]) -> dict[str, Any]:
        return get_issue(tokens["access_token"], tokens["cloud_id"], issue_key, site_url=site_url)

    try:
        issue = call_with_jira_tokens(db, conn, _fetch)
        return issue.get("status")
    except JiraError as exc:
        logger.warning("Failed to refresh Jira status for %s: %s", issue_key, exc)
        return None


def sync_intake_jira_status(db: Session, intake, *, transition_names: tuple[str, ...], comment: str | None = None) -> bool:
    """Transition Jira issue and optionally add a comment. Returns True if transition succeeded."""
    issue_key = intake.jira_issue_key
    if not issue_key:
        return False
    actor_id = _jira_actor_user_id(intake)
    conn = get_jira_connection(db, intake.workspace_id, actor_id)
    if not conn:
        logger.info("No Jira connection for user %s — skip sync for %s", actor_id, issue_key)
        return False

    def _sync(tokens: dict[str, str]) -> bool:
        token = tokens["access_token"]
        cloud_id = tokens["cloud_id"]
        transitioned = transition_issue_by_names(token, cloud_id, issue_key, transition_names)
        if comment:
            add_issue_comment(token, cloud_id, issue_key, comment)
        return transitioned

    try:
        ok = call_with_jira_tokens(db, conn, _sync)
        if ok:
            fresh = refresh_intake_jira_status(db, workspace_id=intake.workspace_id, user_id=actor_id, issue_key=issue_key)
            if fresh:
                intake.jira_status = fresh
                db.commit()
        return ok
    except JiraError as exc:
        logger.warning("Jira sync failed for %s: %s", issue_key, exc)
        return False


def on_implementation_started(db: Session, intake) -> None:
    sync_intake_jira_status(
        db,
        intake,
        transition_names=TRANSITION_IN_PROGRESS,
        comment="AI implementation pipeline started from the development platform.",
    )


def on_implementation_ready_for_review(db: Session, intake) -> None:
    sync_intake_jira_status(
        db,
        intake,
        transition_names=TRANSITION_CODE_REVIEW,
        comment="AI agents finished code generation. Review proposed changes in the platform before PR push.",
    )


def on_implementation_failed(db: Session, intake, *, error_message: str | None = None) -> None:
    body = "AI implementation pipeline failed."
    if error_message:
        body += f"\n\nError: {error_message[:1500]}"
    actor_id = _jira_actor_user_id(intake)
    conn = get_jira_connection(db, intake.workspace_id, actor_id)
    if not conn:
        return

    def _comment(tokens: dict[str, str]) -> None:
        add_issue_comment(tokens["access_token"], tokens["cloud_id"], intake.jira_issue_key, body)

    try:
        call_with_jira_tokens(db, conn, _comment)
    except JiraError as exc:
        logger.warning("Failed to comment on %s: %s", intake.jira_issue_key, exc)


def on_pr_completed(db: Session, intake, *, pr_url: str, merged: bool = False) -> None:
    comment = f"Pull request created: {pr_url}"
    if merged:
        comment += "\nPull request was merged."
    sync_intake_jira_status(
        db,
        intake,
        transition_names=TRANSITION_DONE,
        comment=comment,
    )


def on_plan_handoff(db: Session, intake, *, subtask_keys: list[str]) -> None:
    keys = ", ".join(subtask_keys[:20])
    sync_intake_jira_status(
        db,
        intake,
        transition_names=TRANSITION_IN_PROGRESS,
        comment=f"Implementation plan approved. Subtasks created and assigned: {keys}",
    )


def maybe_refresh_parent_epic(db: Session, intake) -> None:
    """If all child intakes under parent are completed, comment on parent epic."""
    parent_key = intake.parent_jira_key
    if not parent_key:
        return
    from models.requirements import JiraTicketIntake

    siblings = (
        db.query(JiraTicketIntake)
        .filter(
            JiraTicketIntake.workspace_id == intake.workspace_id,
            JiraTicketIntake.parent_jira_key == parent_key,
        )
        .all()
    )
    if not siblings:
        return
    if not all(s.status == "completed" for s in siblings):
        return
    parent = (
        db.query(JiraTicketIntake)
        .filter(
            JiraTicketIntake.workspace_id == intake.workspace_id,
            JiraTicketIntake.jira_issue_key == parent_key,
        )
        .first()
    )
    if not parent:
        return
    sync_intake_jira_status(
        db,
        parent,
        transition_names=TRANSITION_DONE,
        comment=f"All subtasks under {parent_key} are completed ({len(siblings)} tickets).",
    )
