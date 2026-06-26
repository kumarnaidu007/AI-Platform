"""Persist agent outputs to artifact tables."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.artifacts import (
    ArchitectureDoc,
    Deployment,
    ExternalTask,
    PrdDocument,
    PullRequest,
    ValidationReport,
)

def save_prd(db: Session, project_id: UUID, run_id: UUID, content: dict) -> PrdDocument:
    version = (
        db.query(func.max(PrdDocument.version))
        .filter(PrdDocument.project_id == project_id)
        .scalar()
        or 0
    ) + 1
    row = PrdDocument(project_id=project_id, pipeline_run_id=run_id, content_json=content, version=version)
    db.add(row)
    db.flush()
    return row


def save_architecture(db: Session, project_id: UUID, run_id: UUID, content: dict) -> ArchitectureDoc:
    version = (
        db.query(func.max(ArchitectureDoc.version))
        .filter(ArchitectureDoc.project_id == project_id)
        .scalar()
        or 0
    ) + 1
    row = ArchitectureDoc(project_id=project_id, pipeline_run_id=run_id, content_json=content, version=version)
    db.add(row)
    db.flush()
    return row


def save_tasks(db: Session, project_id: UUID, tasks: list[dict], pm_tool: str | None) -> list[ExternalTask]:
    saved: list[ExternalTask] = []
    for task in tasks:
        external_id = str(task.get("id") or task.get("external_id") or f"task-{len(saved)+1}")
        row = ExternalTask(
            project_id=project_id,
            external_id=external_id,
            external_url=task.get("url"),
            title=str(task.get("title", "Untitled task")),
            status=task.get("status", "todo"),
            pm_tool=pm_tool,
        )
        db.add(row)
        saved.append(row)
    db.flush()
    return saved


def save_pull_request(db: Session, project_id: UUID, pr: dict, task_id: UUID | None = None) -> PullRequest:
    row = PullRequest(
        project_id=project_id,
        external_task_id=task_id,
        url=str(pr.get("url", f"https://github.com/example/{project_id}/pull/1")),
        title=pr.get("title"),
        status=pr.get("status", "open"),
        branch_name=pr.get("branch_name"),
    )
    db.add(row)
    db.flush()
    return row


def save_deployment(db: Session, project_id: UUID, run_id: UUID, deployment: dict) -> Deployment:
    row = Deployment(
        project_id=project_id,
        pipeline_run_id=run_id,
        environment=deployment.get("environment", "staging"),
        url=deployment.get("url"),
        status=deployment.get("status", "deployed"),
    )
    db.add(row)
    db.flush()
    return row


def save_validation(db: Session, project_id: UUID, run_id: UUID, report: dict) -> ValidationReport:
    row = ValidationReport(
        project_id=project_id,
        pipeline_run_id=run_id,
        passed=bool(report.get("passed", True)),
        report_json=report,
    )
    db.add(row)
    db.flush()
    return row
