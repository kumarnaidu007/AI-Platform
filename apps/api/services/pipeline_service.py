"""Pipeline run lifecycle: create, execute, approve, query."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from agents.context import PipelineContext
from agents.workflow import ApprovalRequired, run_full_pipeline
from agents.handlers import AgentRunResult
from constants.workspace import MAX_PARALLEL_PIPELINES, MAX_PROJECTS
from models import AgentLog, Workspace, PipelineRun, PipelineStep, Project, UsageLedger
from models.agents import PlatformAgent, ProjectAgent
from models.artifacts import ArchitectureDoc, PrdDocument, ValidationReport
from models.platform import PlatformSetting
from schemas.pipeline import (
    AgentLogResponse,
    PipelineRunDetailResponse,
    PipelineRunSummaryResponse,
    PipelineStepResponse,
)
from services.memory_service import append_run_memory, load_project_memory
from services.rag_service import index_project_repo
from services.tracing_service import configure_tracing, trace_agent_step
from services.usage_service import record_usage

logger = logging.getLogger(__name__)


def _maintenance_mode(db: Session) -> bool:
    row = db.query(PlatformSetting).filter(PlatformSetting.key == "maintenance_mode").first()
    if not row:
        return False
    value = row.value_json
    if isinstance(value, dict):
        return bool(value.get("value", False))
    return bool(value)


def _max_parallel(_db: Session, _workspace: Workspace) -> int:
    if _workspace.limits and _workspace.limits.max_parallel_pipelines is not None:
        return _workspace.limits.max_parallel_pipelines
    return MAX_PARALLEL_PIPELINES


def _max_projects(_db: Session, _workspace: Workspace) -> int:
    if _workspace.limits and _workspace.limits.max_projects is not None:
        return _workspace.limits.max_projects
    return MAX_PROJECTS


def _enabled_agents_for_project(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    workspace_id: UUID,
    *,
    agent_keys_filter: list[str] | None = None,
) -> list[tuple[str, int]]:
    from models.agents import WorkspacePlatformAgent, MemberAgentAccess

    granted = {
        r.platform_agent_id
        for r in db.query(WorkspacePlatformAgent)
        .filter(WorkspacePlatformAgent.workspace_id == workspace_id, WorkspacePlatformAgent.is_enabled.is_(True))
        .all()
    }
    assigned = {
        r.platform_agent_id
        for r in db.query(MemberAgentAccess)
        .filter(
            MemberAgentAccess.workspace_id == workspace_id,
            MemberAgentAccess.user_id == user_id,
            MemberAgentAccess.is_enabled.is_(True),
        )
        .all()
    }
    configs = {
        row.platform_agent_id: row
        for row in db.query(ProjectAgent).filter(ProjectAgent.project_id == project_id).all()
    }
    eligible = granted & assigned
    if not eligible:
        return []
    agents = (
        db.query(PlatformAgent)
        .filter(PlatformAgent.is_enabled.is_(True), PlatformAgent.id.in_(eligible))
        .all()
    )
    filter_set = set(agent_keys_filter) if agent_keys_filter else None
    steps: list[tuple[str, int]] = []
    for agent in agents:
        if agent.id not in granted or agent.id not in assigned:
            continue
        cfg = configs.get(agent.id)
        if filter_set is None:
            if not cfg or not cfg.is_enabled:
                continue
            steps.append((agent.agent_key, cfg.step_order))
        elif agent.agent_key in filter_set:
            step_order = cfg.step_order if cfg else agent.default_step_order
            steps.append((agent.agent_key, step_order))
    steps.sort(key=lambda x: x[1])
    return steps


def start_pipeline_run(
    db: Session,
    *,
    project: Project,
    workspace: Workspace,
    user_id: UUID,
    requirements_text: str,
    additional_context: dict | None = None,
    agent_keys: list[str] | None = None,
) -> PipelineRun:
    if _maintenance_mode(db):
        raise ValueError("Platform is in maintenance mode. New pipeline runs are disabled.")

    if project.status not in ("active", "draft"):
        raise ValueError(f"Cannot start pipeline for project in status '{project.status}'")

    agent_steps = _enabled_agents_for_project(
        db, project.id, user_id, workspace.id, agent_keys_filter=agent_keys
    )
    if not agent_steps:
        if agent_keys:
            raise ValueError(
                "None of the selected agents are enabled for this project. "
                "Enable them in project settings or pick different agents."
            )
        raise ValueError("No agents enabled for this project. Configure agents in project settings.")

    active = (
        db.query(func.count(PipelineRun.id))
        .join(Project, Project.id == PipelineRun.project_id)
        .filter(
            Project.workspace_id == workspace.id,
            PipelineRun.status.in_(["pending", "running", "awaiting_approval"]),
        )
        .scalar()
        or 0
    )
    if active >= _max_parallel(db , workspace):
        raise ValueError("Parallel pipeline limit reached.")

    current_count = db.query(func.count(Project.id)).filter(Project.workspace_id == workspace.id).scalar() or 0
    if current_count > _max_projects(db , workspace):
        raise ValueError("Project limit reached.")

    run = PipelineRun(
        project_id=project.id,
        started_by_user_id=user_id,
        status="pending",
        langgraph_thread_id=None,
    )
    db.add(run)
    db.flush()

    for agent_key, step_order in agent_steps:
        db.add(
            PipelineStep(
                pipeline_run_id=run.id,
                step_name=agent_key,
                step_order=step_order,
                status="pending",
            )
        )

    run.langgraph_thread_id = str(run.id)
    db.commit()
    db.refresh(run)
    ctx_payload = dict(additional_context or {})
    ctx_payload["user_id"] = str(user_id)
    enqueue_pipeline_execution(str(run.id), requirements_text, ctx_payload)
    return run


def approve_pipeline_run(db: Session, run: PipelineRun) -> PipelineRun:
    if run.status != "awaiting_approval":
        raise ValueError("Pipeline is not awaiting approval")
    run.status = "running"
    db.commit()
    enqueue_pipeline_execution(
        str(run.id),
        (run.graph_state_json or {}).get("requirements_text", ""),
        {
            "user_id": str(run.started_by_user_id),
            "approved": True,
            "resume": True,
        },
    )
    return run


def reject_pipeline_run(db: Session, run: PipelineRun, reason: str | None = None) -> PipelineRun:
    if run.status != "awaiting_approval":
        raise ValueError("Pipeline is not awaiting approval")
    run.status = "cancelled"
    run.finished_at = datetime.now(UTC)
    run.error_message = reason or "Rejected by user"
    db.commit()
    return run


def _mark_run_failed(
    run: PipelineRun,
    steps: list[PipelineStep],
    step_map: dict[str, PipelineStep],
    failed_agent_key: str | None,
    exc: Exception,
) -> None:
    """Mark the failing step and skip any steps that never ran."""
    failed_step = step_map.get(failed_agent_key or "")
    if failed_step:
        if failed_step.status == "running":
            failed_step.status = "failed"
            failed_step.finished_at = datetime.now(UTC)
            failed_step.error_message = str(exc)
    for step in steps:
        if step.status == "pending":
            step.status = "skipped"
            step.finished_at = datetime.now(UTC)
            step.error_message = "Skipped — pipeline stopped after earlier failure"
    run.status = "failed"
    run.error_message = str(exc)
    run.finished_at = datetime.now(UTC)


def enqueue_pipeline_execution(run_id: str, requirements_text: str, additional_context: dict) -> None:
    try:
        from workers.pipeline_tasks import execute_pipeline_run_task

        execute_pipeline_run_task.delay(run_id, requirements_text, additional_context)
        logger.info("Enqueued pipeline run %s via Celery", run_id)
    except Exception as exc:
        logger.warning("Celery unavailable (%s), running pipeline in background thread", exc)
        thread = threading.Thread(
            target=execute_pipeline_run,
            args=(run_id, requirements_text, additional_context),
            daemon=True,
        )
        thread.start()


def execute_pipeline_run(run_id: str, requirements_text: str, additional_context: dict) -> None:
    from db.session import SessionLocal

    db = SessionLocal()
    try:
        run = (
            db.query(PipelineRun)
            .options(joinedload(PipelineRun.steps))
            .filter(PipelineRun.id == run_id)
            .first()
        )
        if not run:
            logger.error("Pipeline run %s not found", run_id)
            return
        if run.status in ("completed", "failed", "cancelled"):
            return

        project = db.query(Project).filter(Project.id == run.project_id).first()
        if not project:
            run.status = "failed"
            run.error_message = "Project not found"
            run.finished_at = datetime.now(UTC)
            db.commit()
            return

        workspace = db.query(Workspace).options(joinedload(Workspace.limits)).filter(Workspace.id == project.workspace_id).first()

        if run.status == "pending":
            run.status = "running"
            run.started_at = datetime.now(UTC)
            db.commit()

        raw_user = additional_context.get("user_id") or run.started_by_user_id or project.created_by
        pipeline_user_id = UUID(str(raw_user)) if not isinstance(raw_user, UUID) else raw_user

        approved = bool(additional_context.get("approved"))
        resume = bool(additional_context.get("resume"))

        if not resume and project.repo_url:
            try:
                index_project_repo(
                    db,
                    project_id=project.id,
                    workspace_id=project.workspace_id,
                    user_id=pipeline_user_id,
                    repo_url=project.repo_url,
                )
            except Exception as exc:
                logger.warning("RAG indexing failed: %s", exc)

        memory = load_project_memory(db, project.id)
        if run.graph_state_json and resume:
            requirements_text = run.graph_state_json.get("requirements_text", requirements_text)

        ctx = PipelineContext(
            run_id=run.id,
            project_id=project.id,
            workspace_id=project.workspace_id,
            user_id=pipeline_user_id,
            project_name=project.name,
            project_description=project.description,
            frontend_stack=project.frontend_stack,
            backend_stack=project.backend_stack,
            db_type=project.db_type,
            vcs_provider=project.vcs_provider,
            repo_url=project.repo_url,
            pm_tool=project.pm_tool or ("jira" if additional_context.get("jira_issue") else None),
            requirements_text=requirements_text,
            additional_context=additional_context,
            jira_issue=additional_context.get("jira_issue"),
            memory=memory,
        )
        if run.graph_state_json:
            ctx = PipelineContext.from_checkpoint(ctx, run.graph_state_json)

        configure_tracing(db)

        steps = sorted(run.steps, key=lambda s: s.step_order)
        agent_keys = [s.step_name for s in steps]
        step_map = {s.step_name: s for s in steps}

        def before_step(agent_key: str) -> None:
            step = step_map[agent_key]
            step.status = "running"
            step.started_at = datetime.now(UTC)
            run.current_step = agent_key
            db.commit()

        def after_step(agent_key: str, result: AgentRunResult) -> None:
            step = step_map[agent_key]
            step.status = "completed"
            step.finished_at = datetime.now(UTC)
            step.retry_count = ctx.review_retry_count if agent_key == "review" else step.retry_count
            db.add(
                AgentLog(
                    pipeline_step_id=step.id,
                    agent_name=agent_key,
                    input_json={"requirements_preview": requirements_text[:500], "tools": ctx.tool_results[-3:]},
                    output_json=result.output,
                    input_tokens=result.llm.input_tokens,
                    output_tokens=result.llm.output_tokens,
                    cost_usd=result.llm.cost_usd,
                    model_name=result.llm.model_name,
                )
            )
            if workspace:
                record_usage(
                    db,
                    workspace_id=workspace.id,
                    user_id=pipeline_user_id,
                    project_id=project.id,
                    pipeline_run_id=run.id,
                    event_type=f"agent.{agent_key}",
                    input_tokens=result.llm.input_tokens,
                    output_tokens=result.llm.output_tokens,
                    cost_usd=result.llm.cost_usd,
                )
            run.graph_state_json = {**ctx.to_checkpoint(), "requirements_text": requirements_text}
            run.review_retry_count = ctx.review_retry_count
            db.commit()

        try:
            with trace_agent_step("pipeline", run_id=str(run.id)):
                run_full_pipeline(
                    db,
                    ctx,
                    agent_keys,
                    before_step=before_step,
                    after_step=after_step,
                    skip_planning=resume,
                    approved=approved or resume,
                )
            run.status = "completed"
            run.current_step = None
            run.finished_at = datetime.now(UTC)
            run.error_message = None
            append_run_memory(
                db,
                project.id,
                run.id,
                {
                    "status": "completed",
                    "tasks": ctx.tasks,
                    "pull_requests": ctx.pull_requests,
                    "validation_score": (ctx.validation or {}).get("score"),
                },
            )
        except ApprovalRequired as exc:
            run.status = "awaiting_approval"
            run.approval_plan_json = exc.plan
            run.graph_state_json = {**ctx.to_checkpoint(), "requirements_text": requirements_text}
            run.current_step = "awaiting_approval"
            db.commit()
            return
        except Exception as exc:
            logger.exception("Pipeline run %s failed at %s", run_id, run.current_step)
            _mark_run_failed(run, steps, step_map, run.current_step, exc)
        db.commit()
    finally:
        db.close()


def _step_logs(db: Session, step_id: UUID) -> list[AgentLogResponse]:
    logs = (
        db.query(AgentLog)
        .filter(AgentLog.pipeline_step_id == step_id)
        .order_by(AgentLog.created_at.asc())
        .all()
    )
    return [
        AgentLogResponse(
            id=log.id,
            agent_name=log.agent_name,
            input_json=log.input_json,
            output_json=log.output_json,
            input_tokens=log.input_tokens,
            output_tokens=log.output_tokens,
            cost_usd=float(log.cost_usd),
            model_name=log.model_name,
            created_at=log.created_at,
        )
        for log in logs
    ]


def get_run_detail(db: Session, run: PipelineRun) -> PipelineRunDetailResponse:
    steps = (
        db.query(PipelineStep)
        .filter(PipelineStep.pipeline_run_id == run.id)
        .order_by(PipelineStep.step_order.asc())
        .all()
    )
    prd = db.query(PrdDocument).filter(PrdDocument.pipeline_run_id == run.id).order_by(PrdDocument.version.desc()).first()
    arch = (
        db.query(ArchitectureDoc)
        .filter(ArchitectureDoc.pipeline_run_id == run.id)
        .order_by(ArchitectureDoc.version.desc())
        .first()
    )
    validation = db.query(ValidationReport).filter(ValidationReport.pipeline_run_id == run.id).first()
    artifacts: dict = {}
    if prd:
        artifacts["prd"] = prd.content_json
    if arch:
        artifacts["architecture"] = arch.content_json
    if validation:
        artifacts["validation"] = validation.report_json
    if run.approval_plan_json:
        artifacts["approval_plan"] = run.approval_plan_json

    return PipelineRunDetailResponse(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        current_step=run.current_step,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_message=run.error_message,
        created_at=run.created_at,
        approval_plan=run.approval_plan_json,
        steps=[
            PipelineStepResponse(
                id=s.id,
                step_name=s.step_name,
                step_order=s.step_order,
                status=s.status,
                retry_count=s.retry_count,
                started_at=s.started_at,
                finished_at=s.finished_at,
                error_message=s.error_message,
                logs=_step_logs(db, s.id),
            )
            for s in steps
        ],
        artifacts=artifacts,
    )


def summarize_run(db: Session, run: PipelineRun) -> PipelineRunSummaryResponse:
    steps = db.query(PipelineStep).filter(PipelineStep.pipeline_run_id == run.id).all()
    completed = sum(1 for s in steps if s.status == "completed")
    return PipelineRunSummaryResponse(
        id=run.id,
        status=run.status,
        current_step=run.current_step,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_message=run.error_message,
        created_at=run.created_at,
        steps_total=len(steps),
        steps_completed=completed,
        approval_plan=run.approval_plan_json,
    )
