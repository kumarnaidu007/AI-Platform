"""Jira ticket intake lifecycle: clarify → spec → approve → implement."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from agents.requirements_agents import (
    DOC_TYPES,
    agent_reply_to_conversation,
    generate_clarification_questions,
    generate_domain_documents,
    generate_implementation_plan,
    generate_jira_task_breakdown,
    review_spec_consistency,
)
from models import Project, User, Workspace, WorkspaceMember
from models.requirements import (
    ClarificationAnswer,
    ClarificationQuestion,
    IntakeApproval,
    JiraTicketIntake,
    RequirementConversation,
    RequirementDocument,
)
from services.github_service import get_github_access_token, get_github_connection, list_repo_source_files
from services.jira_service import (
    JiraError,
    call_with_jira_tokens,
    create_subtask,
    get_issue,
    get_jira_connection,
    get_member_jira_account_id,
)
from services.jira_sync_service import (
    on_implementation_started,
    on_pr_completed,
    refresh_intake_jira_status,
)
from services.notification_service import notify_user
from services.intake_permissions import effective_assignee_id
from services.pipeline_service import start_pipeline_run


def _intake_link(issue_key: str) -> str:
    return f"/workspace/jira/{issue_key}"


def get_intake_or_404(db: Session, workspace_id: UUID, intake_id: UUID) -> JiraTicketIntake:
    row = (
        db.query(JiraTicketIntake)
        .filter(JiraTicketIntake.id == intake_id, JiraTicketIntake.workspace_id == workspace_id)
        .first()
    )
    if not row:
        raise ValueError("Intake not found")
    return row


def get_intake_by_key(db: Session, workspace_id: UUID, issue_key: str) -> JiraTicketIntake | None:
    return (
        db.query(JiraTicketIntake)
        .filter(
            JiraTicketIntake.workspace_id == workspace_id,
            JiraTicketIntake.jira_issue_key == issue_key.upper(),
        )
        .first()
    )


def _repo_context(db: Session, workspace_id: UUID, user_id: UUID, repo_url: str | None) -> str:
    if not repo_url:
        return "No repository linked yet."
    conn = get_github_connection(db, workspace_id, user_id)
    try:
        token = get_github_access_token(conn)
        files = list_repo_source_files(token, repo_url, max_files=40, extensions={".cs", ".json", ".sql"})
        lines = [f"- {path}" for path, _ in files[:40]]
        return "\n".join(lines) or "Repository has no matching source files."
    except Exception as exc:
        return f"Could not read repository: {exc}"


def create_or_get_intake(
    db: Session,
    *,
    workspace_id: UUID,
    user_id: UUID,
    jira_issue_key: str,
    project_id: UUID | None,
    issue_row: dict,
) -> JiraTicketIntake:
    key = jira_issue_key.strip().upper()
    existing = get_intake_by_key(db, workspace_id, key)
    if existing:
        existing.jira_summary = issue_row.get("summary")
        existing.jira_status = issue_row.get("status")
        existing.jira_url = issue_row.get("url")
        existing.jira_issue_id = issue_row.get("id")
        if issue_row.get("project_key"):
            existing.jira_project_key = issue_row.get("project_key")
        if project_id:
            existing.project_id = project_id
        db.commit()
        db.refresh(existing)
        return existing

    repo_url = None
    base_branch = "main"
    if project_id:
        project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace_id).first()
        if project:
            repo_url = project.repo_url
            base_branch = "main"

    intake = JiraTicketIntake(
        workspace_id=workspace_id,
        user_id=user_id,
        project_id=project_id,
        jira_issue_key=key,
        jira_issue_id=issue_row.get("id"),
        jira_summary=issue_row.get("summary"),
        jira_status=issue_row.get("status"),
        jira_url=issue_row.get("url"),
        jira_project_key=issue_row.get("project_key"),
        status="synced",
        repo_url=repo_url,
        base_branch=base_branch,
    )
    db.add(intake)
    db.commit()
    db.refresh(intake)
    return intake


def analyze_intake(db: Session, intake: JiraTicketIntake, user_id: UUID) -> JiraTicketIntake:
    if intake.status not in ("synced", "awaiting_answers"):
        return intake

    project_stack = "dotnet"
    if intake.project_id:
        p = db.query(Project).filter(Project.id == intake.project_id).first()
        if p:
            project_stack = f"{p.backend_stack or 'dotnet'} / {p.frontend_stack or 'n/a'} / {p.db_type or 'sql'}"

    intake.status = "analyzing"
    db.commit()

    db.query(ClarificationQuestion).filter(ClarificationQuestion.intake_id == intake.id).delete()
    db.commit()

    repo_ctx = _repo_context(db, intake.workspace_id, user_id, intake.repo_url)
    questions = generate_clarification_questions(
        db,
        issue_key=intake.jira_issue_key,
        summary=intake.jira_summary or "",
        description="",
        repo_context=repo_ctx,
        project_stack=project_stack,
    )
    if not questions:
        raise RuntimeError("Clarifier agent did not return any questions")

    for q in questions:
        db.add(
            ClarificationQuestion(
                intake_id=intake.id,
                category=q["category"],
                question_text=q["question_text"],
                options_json=q["options_json"],
                allow_custom_answer=q["allow_custom_answer"],
                is_required=q["is_required"],
                sort_order=q["sort_order"],
                rationale=q.get("rationale"),
            )
        )
    intake.status = "awaiting_answers"
    db.commit()
    db.refresh(intake)

    notify_user(
        db,
        workspace_id=intake.workspace_id,
        user_id=intake.user_id,
        notification_type="questions_ready",
        title=f"{intake.jira_issue_key}: clarification questions ready",
        body="Answer the questions to generate requirement documents.",
        link_path=_intake_link(intake.jira_issue_key),
        intake_id=intake.id,
    )
    return intake


def answer_question(
    db: Session,
    intake: JiraTicketIntake,
    question_id: UUID,
    user_id: UUID,
    *,
    selected_option: str | None,
    custom_answer: str | None,
) -> ClarificationQuestion:
    question = (
        db.query(ClarificationQuestion)
        .filter(ClarificationQuestion.id == question_id, ClarificationQuestion.intake_id == intake.id)
        .first()
    )
    if not question:
        raise ValueError("Question not found")
    if not selected_option and not (custom_answer or "").strip():
        raise ValueError("Provide a selected option or custom answer")

    existing = db.query(ClarificationAnswer).filter(ClarificationAnswer.question_id == question.id).first()
    if existing:
        existing.selected_option = selected_option
        existing.custom_answer = (custom_answer or "").strip() or None
        existing.answered_by_user_id = user_id
        existing.updated_at = datetime.now(UTC)
    else:
        db.add(
            ClarificationAnswer(
                question_id=question.id,
                selected_option=selected_option,
                custom_answer=(custom_answer or "").strip() or None,
                answered_by_user_id=user_id,
            )
        )
    question.status = "answered"
    db.commit()
    db.refresh(question)
    return question


def _answers_text(db: Session, intake_id: UUID) -> str:
    rows = (
        db.query(ClarificationQuestion, ClarificationAnswer)
        .outerjoin(ClarificationAnswer, ClarificationAnswer.question_id == ClarificationQuestion.id)
        .filter(ClarificationQuestion.intake_id == intake_id)
        .order_by(ClarificationQuestion.sort_order.asc())
        .all()
    )
    lines: list[str] = []
    for q, a in rows:
        ans = ""
        if a:
            ans = a.custom_answer or a.selected_option or ""
        lines.append(f"[{q.category}] Q: {q.question_text}\nA: {ans}")
    return "\n\n".join(lines)


def _unanswered_required(db: Session, intake_id: UUID) -> int:
    rows = (
        db.query(ClarificationQuestion)
        .filter(
            ClarificationQuestion.intake_id == intake_id,
            ClarificationQuestion.is_required.is_(True),
            ClarificationQuestion.status != "answered",
        )
        .count()
    )
    return rows


def submit_answers_and_generate_specs(db: Session, intake: JiraTicketIntake) -> JiraTicketIntake:
    missing = _unanswered_required(db, intake.id)
    if missing:
        raise ValueError(f"{missing} required question(s) still unanswered")

    intake.status = "drafting_specs"
    db.commit()

    project_stack = "dotnet"
    if intake.project_id:
        p = db.query(Project).filter(Project.id == intake.project_id).first()
        if p:
            project_stack = f"{p.backend_stack or 'dotnet'} / {p.db_type or 'sql'}"

    answers = _answers_text(db, intake.id)
    docs = generate_domain_documents(
        db,
        issue_key=intake.jira_issue_key,
        summary=intake.jira_summary or "",
        description="",
        answers_text=answers,
        project_stack=project_stack,
    )

    for doc_type in DOC_TYPES:
        block = docs.get(doc_type)
        if not block:
            continue
        existing = (
            db.query(RequirementDocument)
            .filter(RequirementDocument.intake_id == intake.id, RequirementDocument.doc_type == doc_type)
            .first()
        )
        content = block.get("content_json") or block
        title = block.get("title") or f"{doc_type} — {intake.jira_issue_key}"
        if existing:
            existing.title = title
            existing.content_json = content if isinstance(content, dict) else {"sections": content}
            existing.version += 1
            existing.status = "draft"
        else:
            db.add(
                RequirementDocument(
                    intake_id=intake.id,
                    doc_type=doc_type,
                    title=title,
                    content_json=content if isinstance(content, dict) else {"sections": content},
                )
            )

    issues = review_spec_consistency(
        db,
        documents={k: v.get("content_json", v) for k, v in docs.items()},
    )
    if issues:
        db.add(
            RequirementConversation(
                intake_id=intake.id,
                author_type="agent",
                message="Spec review notes: " + "; ".join(i.get("message", "") for i in issues[:5]),
            )
        )

    intake.status = "awaiting_review"
    db.commit()
    db.refresh(intake)

    notify_user(
        db,
        workspace_id=intake.workspace_id,
        user_id=intake.user_id,
        notification_type="specs_ready",
        title=f"{intake.jira_issue_key}: requirement documents ready",
        body="Review DB, API, Auth, Validation, and Exception specs.",
        link_path=_intake_link(intake.jira_issue_key),
        intake_id=intake.id,
    )
    return intake


def patch_document(
    db: Session, intake: JiraTicketIntake, doc_type: str, content_json: dict
) -> RequirementDocument:
    doc = (
        db.query(RequirementDocument)
        .filter(RequirementDocument.intake_id == intake.id, RequirementDocument.doc_type == doc_type)
        .first()
    )
    if not doc:
        raise ValueError("Document not found")
    doc.content_json = content_json
    doc.version += 1
    doc.status = "draft"
    db.commit()
    db.refresh(doc)
    return doc


def add_conversation(
    db: Session,
    intake: JiraTicketIntake,
    user_id: UUID,
    message: str,
    document_id: UUID | None = None,
) -> list[RequirementConversation]:
    db.add(
        RequirementConversation(
            intake_id=intake.id,
            document_id=document_id,
            author_type="user",
            author_user_id=user_id,
            message=message,
        )
    )
    db.commit()

    docs = {
        d.doc_type: {"title": d.title, "content": d.content_json}
        for d in db.query(RequirementDocument).filter(RequirementDocument.intake_id == intake.id).all()
    }
    history = [
        c.message
        for c in db.query(RequirementConversation)
        .filter(RequirementConversation.intake_id == intake.id)
        .order_by(RequirementConversation.created_at.asc())
        .all()
    ]
    reply = agent_reply_to_conversation(
        db,
        issue_key=intake.jira_issue_key,
        message=message,
        documents=docs,
        history=history,
    )
    agent_msg = RequirementConversation(
        intake_id=intake.id,
        document_id=document_id,
        author_type="agent",
        message=reply,
    )
    db.add(agent_msg)
    db.commit()
    return (
        db.query(RequirementConversation)
        .filter(RequirementConversation.intake_id == intake.id)
        .order_by(RequirementConversation.created_at.asc())
        .all()
    )


def lock_requirements(db: Session, intake: JiraTicketIntake, user_id: UUID) -> JiraTicketIntake:
    if intake.status != "awaiting_review":
        raise ValueError("Specs must be in review before locking")
    if not db.query(RequirementDocument).filter(RequirementDocument.intake_id == intake.id).count():
        raise ValueError("No requirement documents generated")

    for doc in db.query(RequirementDocument).filter(RequirementDocument.intake_id == intake.id).all():
        doc.status = "confirmed"

    intake.status = "locked"
    intake.locked_at = datetime.now(UTC)
    intake.locked_by_user_id = user_id
    db.commit()

    plan = generate_implementation_plan(
        db,
        issue_key=intake.jira_issue_key,
        documents={
            d.doc_type: d.content_json
            for d in db.query(RequirementDocument).filter(RequirementDocument.intake_id == intake.id).all()
        },
    )
    intake.implementation_plan_json = plan
    intake.status = "awaiting_plan_approval"
    db.add(
        IntakeApproval(
            intake_id=intake.id,
            approval_type="implementation_plan",
            status="pending",
        )
    )
    db.commit()
    db.refresh(intake)

    notify_user(
        db,
        workspace_id=intake.workspace_id,
        user_id=intake.user_id,
        notification_type="plan_approval_needed",
        title=f"{intake.jira_issue_key}: confirm your implementation plan",
        body=plan.get("summary", "Review and confirm the plan to start implementation."),
        link_path=_intake_link(intake.jira_issue_key),
        intake_id=intake.id,
    )
    return intake


def approve_plan(
    db: Session, intake: JiraTicketIntake, approver_id: UUID, comment: str | None = None
) -> JiraTicketIntake:
    if intake.status != "awaiting_plan_approval":
        raise ValueError("Intake is not awaiting plan approval")
    approval = (
        db.query(IntakeApproval)
        .filter(
            IntakeApproval.intake_id == intake.id,
            IntakeApproval.approval_type == "implementation_plan",
            IntakeApproval.status == "pending",
        )
        .first()
    )
    if not approval:
        raise ValueError("No pending approval")
    approval.status = "approved"
    approval.approver_user_id = approver_id
    approval.comment = comment
    approval.decided_at = datetime.now(UTC)
    intake.status = "approved"
    db.commit()
    db.refresh(intake)

    notify_user(
        db,
        workspace_id=intake.workspace_id,
        user_id=intake.user_id,
        notification_type="plan_approved",
        title=f"{intake.jira_issue_key}: plan confirmed",
        body="Click Start implementation when you are ready.",
        link_path=_intake_link(intake.jira_issue_key),
        intake_id=intake.id,
    )
    return intake


def reject_plan(
    db: Session, intake: JiraTicketIntake, approver_id: UUID, comment: str | None = None
) -> JiraTicketIntake:
    if intake.status != "awaiting_plan_approval":
        raise ValueError("Intake is not awaiting plan approval")
    approval = (
        db.query(IntakeApproval)
        .filter(
            IntakeApproval.intake_id == intake.id,
            IntakeApproval.approval_type == "implementation_plan",
            IntakeApproval.status == "pending",
        )
        .first()
    )
    if approval:
        approval.status = "rejected"
        approval.approver_user_id = approver_id
        approval.comment = comment
        approval.decided_at = datetime.now(UTC)
    intake.status = "awaiting_review"
    db.commit()
    db.refresh(intake)
    notify_user(
        db,
        workspace_id=intake.workspace_id,
        user_id=intake.user_id,
        notification_type="plan_rejected",
        title=f"{intake.jira_issue_key}: plan rejected",
        body=comment or "Revise requirements and lock again.",
        link_path=_intake_link(intake.jira_issue_key),
        intake_id=intake.id,
    )
    return intake


PLANNING_AGENT_KEYS = frozenset({"requirements", "architecture", "task_planner"})
DEFAULT_IMPLEMENTATION_AGENT_KEYS = ("code_writer", "review", "deploy")


def _default_implementation_agent_keys(
    db: Session,
    *,
    project_id: UUID,
    user_id: UUID,
    workspace_id: UUID,
) -> list[str]:
    from services.pipeline_service import _enabled_agents_for_project

    steps = _enabled_agents_for_project(db, project_id, user_id, workspace_id)
    impl_keys = [key for key, _ in steps if key not in PLANNING_AGENT_KEYS]
    if impl_keys:
        return impl_keys
    all_keys = [key for key, _ in steps]
    if all_keys:
        return all_keys
    return list(DEFAULT_IMPLEMENTATION_AGENT_KEYS)


def reconcile_intake_pipeline_status(db: Session, intake: JiraTicketIntake) -> JiraTicketIntake:
    """Fix intakes stuck on implementing when the linked pipeline already failed."""
    if intake.status != "implementing" or not intake.pipeline_run_id:
        return intake
    from models import PipelineRun
    from services.pipeline_service import reconcile_stuck_pipeline_run

    run = db.query(PipelineRun).filter(PipelineRun.id == intake.pipeline_run_id).first()
    if not run:
        return intake
    run = reconcile_stuck_pipeline_run(db, run)
    if run.status == "failed":
        intake.status = "implementation_failed"
        db.commit()
        db.refresh(intake)
    elif run.status == "completed":
        intake.status = "awaiting_pr_review"
        db.commit()
        db.refresh(intake)
    return intake


def build_requirements_text(intake: JiraTicketIntake, documents: list[RequirementDocument]) -> str:
    parts = [f"Jira: {intake.jira_issue_key} — {intake.jira_summary or ''}"]
    for doc in documents:
        parts.append(f"\n## {doc.doc_type.upper()} SPEC\n{doc.content_json}")
    if intake.implementation_plan_json:
        parts.append(f"\n## IMPLEMENTATION PLAN\n{intake.implementation_plan_json}")
    return "\n".join(parts)[:50000]


def start_implementation(
    db: Session,
    intake: JiraTicketIntake,
    user_id: UUID,
    agent_keys: list[str] | None = None,
) -> JiraTicketIntake:
    if intake.status not in ("approved", "implementation_failed"):
        raise ValueError("Plan must be approved before implementation")
    if not intake.project_id:
        raise ValueError("Link a project with a repository before implementation")

    project = db.query(Project).filter(Project.id == intake.project_id).first()
    workspace = (
        db.query(Workspace).options(joinedload(Workspace.limits)).filter(Workspace.id == intake.workspace_id).first()
    )
    if not project or not workspace:
        raise ValueError("Project or workspace not found")

    documents = db.query(RequirementDocument).filter(RequirementDocument.intake_id == intake.id).all()
    requirements_text = build_requirements_text(intake, documents)

    keys = agent_keys or _default_implementation_agent_keys(
        db,
        project_id=project.id,
        user_id=user_id,
        workspace_id=workspace.id,
    )
    if not intake.feature_branch and intake.jira_issue_key:
        intake.feature_branch = f"feature/{intake.jira_issue_key.lower()}"
    run = start_pipeline_run(
        db,
        project=project,
        workspace=workspace,
        user_id=user_id,
        requirements_text=requirements_text,
        additional_context={
            "intake_id": str(intake.id),
            "jira_issue_key": intake.jira_issue_key,
            "spec_documents": {d.doc_type: d.content_json for d in documents},
            "implementation_plan": intake.implementation_plan_json,
            "approved": True,
            "skip_planning": True,
            **({"feature_branch": intake.feature_branch} if intake.feature_branch else {}),
        },
        agent_keys=keys,
    )
    intake.pipeline_run_id = run.id
    intake.status = "implementing"
    db.commit()
    db.refresh(intake)

    try:
        on_implementation_started(db, intake)
    except Exception:
        pass

    notify_target = effective_assignee_id(intake)
    notify_user(
        db,
        workspace_id=intake.workspace_id,
        user_id=notify_target,
        notification_type="implementation_started",
        title=f"{intake.jira_issue_key}: implementation started",
        body="Pipeline is running. You will be notified when code is ready for your review.",
        link_path=f"/workspace/jira/{intake.jira_issue_key}",
        intake_id=intake.id,
    )
    return intake


def approve_pr_review(
    db: Session,
    intake: JiraTicketIntake,
    user_id: UUID,
    *,
    comment: str | None = None,
    branch_name: str | None = None,
    base_branch: str | None = None,
    pr_title: str | None = None,
    reviewers: list[str] | None = None,
    merge: bool = False,
) -> JiraTicketIntake:
    if intake.status != "awaiting_pr_review":
        raise ValueError("No code changes awaiting approval")
    pending = intake.pending_publish_json
    if not pending or not pending.get("files"):
        raise ValueError("No pending code changes to publish")

    project = db.query(Project).filter(Project.id == intake.project_id).first() if intake.project_id else None
    repo_url = intake.repo_url or (project.repo_url if project else None) or pending.get("repo_url")
    if not repo_url:
        raise ValueError("No repository linked for this ticket")

    conn = get_github_connection(db, intake.workspace_id, user_id)
    if not conn:
        raise ValueError("GitHub is not connected. Connect GitHub in integrations first.")
    token = get_github_access_token(conn)

    from services import artifact_service
    from services.github_service import (
        apply_code_changes,
        merge_pull_request,
        parse_repo_url,
        request_pr_reviewers,
    )

    publish_branch = branch_name or pending.get("branch_name") or intake.feature_branch
    publish_base = base_branch or intake.base_branch or pending.get("base_branch") or "main"
    publish_title = pr_title or pending.get("pr_title") or f"feat: {intake.jira_issue_key}"
    publish_body = pending.get("pr_body") or pending.get("summary") or comment or ""

    if not publish_branch:
        raise ValueError("Branch name is required")

    pr_data = apply_code_changes(
        token,
        repo_url,
        base_branch=publish_base,
        branch_name=publish_branch,
        files=pending.get("files") or [],
        pr_title=publish_title,
        pr_body=publish_body,
    )

    repo_ref = parse_repo_url(repo_url)
    pr_number = pr_data.get("number")
    if pr_number and reviewers:
        try:
            request_pr_reviewers(token, repo_ref, int(pr_number), reviewers)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Failed to request PR reviewers: %s", exc)

    merged = False
    if merge and pr_number:
        try:
            merge_pull_request(token, repo_ref, int(pr_number))
            merged = True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Failed to merge PR #%s: %s", pr_number, exc)

    if intake.project_id:
        artifact_service.save_pull_request(db, intake.project_id, pr_data)

    jira_key = intake.jira_issue_key
    if jira_key and pr_data.get("url"):
        try:
            from services.jira_service import notify_jira_pr_created

            notify_jira_pr_created(
                db,
                workspace_id=intake.workspace_id,
                user_id=user_id,
                issue_key=jira_key,
                pr_title=pr_data.get("title") or publish_title,
                pr_url=str(pr_data.get("url")),
                summary=pending.get("summary"),
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Failed to update Jira issue %s: %s", jira_key, exc)

    intake.pending_publish_json = None
    intake.feature_branch = publish_branch
    intake.base_branch = publish_base
    intake.pr_url = pr_data.get("url")
    intake.status = "completed"
    db.commit()
    db.refresh(intake)

    try:
        on_pr_completed(db, intake, pr_url=str(pr_data.get("url")), merged=merged)
        from services.jira_sync_service import maybe_refresh_parent_epic

        maybe_refresh_parent_epic(db, intake)
    except Exception:
        pass

    body_parts = [f"PR created: {pr_data.get('url')}"]
    if merged:
        body_parts.append("Pull request merged.")
    if comment:
        body_parts.append(comment)
    notify_user(
        db,
        workspace_id=intake.workspace_id,
        user_id=intake.user_id,
        notification_type="pr_approved",
        title=f"{intake.jira_issue_key}: changes pushed to GitHub",
        body=" ".join(body_parts),
        link_path=_intake_link(intake.jira_issue_key),
        intake_id=intake.id,
    )
    return intake


def intake_summary(db: Session, intake: JiraTicketIntake) -> dict:
    q_total = db.query(ClarificationQuestion).filter(ClarificationQuestion.intake_id == intake.id).count()
    q_answered = (
        db.query(ClarificationQuestion)
        .filter(ClarificationQuestion.intake_id == intake.id, ClarificationQuestion.status == "answered")
        .count()
    )
    return {
        "questions_total": q_total,
        "questions_answered": q_answered,
    }


def fetch_jira_issue_for_user(db: Session, workspace_id: UUID, user_id: UUID, issue_key: str) -> dict:
    from services.jira_service import call_with_jira_tokens, get_jira_connection

    conn = get_jira_connection(db, workspace_id, user_id)
    if not conn:
        raise JiraError("Jira not connected")
    metadata = (conn.config_metadata_json or {}) if conn else {}
    site_url = metadata.get("jira_site_url")
    return call_with_jira_tokens(
        db,
        conn,
        lambda t: get_issue(t["access_token"], t["cloud_id"], issue_key.upper(), site_url=site_url),
    )


def _workspace_member_directory(db: Session, workspace_id: UUID) -> list[dict]:
    rows = (
        db.query(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .filter(WorkspaceMember.workspace_id == workspace_id)
        .all()
    )
    out: list[dict] = []
    for member, user in rows:
        jira_name = None
        conn = get_jira_connection(db, workspace_id, user.id)
        if conn and conn.config_metadata_json:
            jira_name = conn.config_metadata_json.get("jira_display_name")
        out.append(
            {
                "user_id": user.id,
                "full_name": user.full_name or user.email,
                "email": user.email,
                "role": member.role,
                "jira_display_name": jira_name,
                "jira_account_id": get_member_jira_account_id(db, workspace_id, user.id),
            }
        )
    return out


def _match_assignee_user_id(directory: list[dict], suggested_name: str | None) -> UUID | None:
    if not suggested_name:
        return None
    needle = suggested_name.strip().lower()
    for row in directory:
        for field in ("full_name", "jira_display_name", "email"):
            val = row.get(field)
            if val and needle in str(val).lower():
                return row["user_id"]
    return None


def create_lead_planning_intake(
    db: Session,
    *,
    workspace_id: UUID,
    planner_user_id: UUID,
    jira_issue_key: str,
    project_id: UUID | None,
    issue_row: dict,
) -> JiraTicketIntake:
    """Team lead starts planning on an epic/story — no implementation on this intake."""
    key = jira_issue_key.strip().upper()
    existing = get_intake_by_key(db, workspace_id, key)
    if existing:
        if existing.intake_mode != "lead_planning":
            existing.intake_mode = "lead_planning"
            existing.planner_user_id = planner_user_id
            db.commit()
            db.refresh(existing)
        return existing

    repo_url = None
    base_branch = "main"
    if project_id:
        project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace_id).first()
        if project:
            repo_url = project.repo_url

    intake = JiraTicketIntake(
        workspace_id=workspace_id,
        user_id=planner_user_id,
        planner_user_id=planner_user_id,
        project_id=project_id,
        jira_issue_key=key,
        jira_issue_id=issue_row.get("id"),
        jira_summary=issue_row.get("summary"),
        jira_status=issue_row.get("status"),
        jira_url=issue_row.get("url"),
        jira_project_key=issue_row.get("project_key"),
        status="synced",
        repo_url=repo_url,
        base_branch=base_branch,
        intake_mode="lead_planning",
    )
    db.add(intake)
    db.commit()
    db.refresh(intake)
    return intake


def create_jira_subtasks_from_plan(
    db: Session,
    intake: JiraTicketIntake,
    planner_user_id: UUID,
) -> JiraTicketIntake:
    if intake.intake_mode != "lead_planning":
        raise ValueError("Jira task creation is only for lead planning intakes")
    if intake.status not in ("awaiting_plan_approval", "approved", "locked"):
        raise ValueError("Lock requirements and generate a plan before creating Jira subtasks")

    documents = {
        d.doc_type: d.content_json
        for d in db.query(RequirementDocument).filter(RequirementDocument.intake_id == intake.id).all()
    }
    directory = _workspace_member_directory(db, intake.workspace_id)
    breakdown = generate_jira_task_breakdown(
        db,
        epic_key=intake.jira_issue_key,
        epic_summary=intake.jira_summary or "",
        epic_description="",
        documents=documents,
        implementation_plan=intake.implementation_plan_json,
        team_member_names=[r["full_name"] for r in directory if r["role"] != "team_lead"],
    )

    conn = get_jira_connection(db, intake.workspace_id, planner_user_id)
    if not conn:
        raise JiraError("Jira not connected for team lead")
    project_key = intake.jira_project_key or intake.jira_issue_key.split("-")[0]
    metadata = conn.config_metadata_json or {}
    site_url = metadata.get("jira_site_url")

    created_tasks: list[dict] = []

    def _create_all(tokens: dict[str, str]) -> list[dict]:
        token = tokens["access_token"]
        cloud_id = tokens["cloud_id"]
        results: list[dict] = []
        for task in breakdown.get("tasks") or []:
            title = str(task.get("title") or "Subtask").strip()
            if not title:
                continue
            assignee_id = _match_assignee_user_id(directory, task.get("suggested_assignee_name"))
            account_id = None
            if assignee_id:
                account_id = get_member_jira_account_id(db, intake.workspace_id, assignee_id)
            desc = str(task.get("description") or "")
            row = create_subtask(
                token,
                cloud_id,
                project_key=project_key,
                parent_key=intake.jira_issue_key,
                summary=title,
                description=desc,
                assignee_account_id=account_id,
            )
            issue = get_issue(token, cloud_id, row["key"], site_url=site_url)
            results.append(
                {
                    "key": row["key"],
                    "id": row.get("id"),
                    "summary": title,
                    "description": desc,
                    "assignee_user_id": str(assignee_id) if assignee_id else None,
                    "url": issue.get("url"),
                    "status": issue.get("status"),
                }
            )
        return results

    created_tasks = call_with_jira_tokens(db, conn, _create_all)
    intake.jira_tasks_json = {"breakdown": breakdown, "created": created_tasks}
    if intake.status == "awaiting_plan_approval":
        intake.status = "approved"
    db.commit()
    db.refresh(intake)
    return intake


def handoff_subtasks_to_members(
    db: Session,
    intake: JiraTicketIntake,
    planner_user_id: UUID,
) -> list[JiraTicketIntake]:
    """Create member intakes for each Jira subtask and notify assignees."""
    if intake.intake_mode != "lead_planning":
        raise ValueError("Handoff is only for lead planning intakes")
    tasks = (intake.jira_tasks_json or {}).get("created") or []
    if not tasks:
        raise ValueError("Create Jira subtasks first")

    parent_docs = db.query(RequirementDocument).filter(RequirementDocument.intake_id == intake.id).all()
    parent_plan = intake.implementation_plan_json
    member_intakes: list[JiraTicketIntake] = []

    for task in tasks:
        key = str(task.get("key") or "").upper()
        if not key:
            continue
        assignee_raw = task.get("assignee_user_id")
        assignee_id = UUID(str(assignee_raw)) if assignee_raw else None
        if not assignee_id:
            continue

        issue_row = {
            "id": task.get("id"),
            "key": key,
            "summary": task.get("summary"),
            "status": task.get("status"),
            "url": task.get("url"),
            "project_key": intake.jira_project_key,
        }
        child = get_intake_by_key(db, intake.workspace_id, key)
        if not child:
            child = JiraTicketIntake(
                workspace_id=intake.workspace_id,
                user_id=assignee_id,
                assignee_user_id=assignee_id,
                planner_user_id=planner_user_id,
                project_id=intake.project_id,
                jira_issue_key=key,
                jira_issue_id=issue_row.get("id"),
                jira_summary=issue_row.get("summary"),
                jira_status=issue_row.get("status"),
                jira_url=issue_row.get("url"),
                jira_project_key=intake.jira_project_key,
                parent_jira_key=intake.jira_issue_key,
                status="approved",
                repo_url=intake.repo_url,
                base_branch=intake.base_branch,
                intake_mode="member",
                implementation_plan_json=parent_plan,
            )
            db.add(child)
            db.flush()
            for doc in parent_docs:
                db.add(
                    RequirementDocument(
                        intake_id=child.id,
                        doc_type=doc.doc_type,
                        title=f"{doc.title} (from {intake.jira_issue_key})",
                        content_json=doc.content_json,
                        version=doc.version,
                        status="confirmed",
                    )
                )
        else:
            child.assignee_user_id = assignee_id
            child.parent_jira_key = intake.jira_issue_key
            child.implementation_plan_json = parent_plan
            child.status = "approved"
        member_intakes.append(child)

        notify_user(
            db,
            workspace_id=intake.workspace_id,
            user_id=assignee_id,
            notification_type="task_assigned",
            title=f"{key}: ready to implement",
            body=f"Your team lead assigned subtask from {intake.jira_issue_key}. Review the plan and start implementation.",
            link_path=f"/workspace/jira/{key}",
            intake_id=child.id,
        )

    db.commit()
    for child in member_intakes:
        db.refresh(child)

    from services.jira_sync_service import on_plan_handoff

    try:
        on_plan_handoff(db, intake, subtask_keys=[t["key"] for t in tasks if t.get("key")])
    except Exception:
        pass

    return member_intakes


def epic_progress(db: Session, workspace_id: UUID, parent_jira_key: str) -> dict:
    parent_key = parent_jira_key.strip().upper()
    parent = get_intake_by_key(db, workspace_id, parent_key)
    children = (
        db.query(JiraTicketIntake)
        .filter(
            JiraTicketIntake.workspace_id == workspace_id,
            JiraTicketIntake.parent_jira_key == parent_key,
        )
        .order_by(JiraTicketIntake.jira_issue_key.asc())
        .all()
    )
    jira_created = (parent.jira_tasks_json or {}).get("created") if parent else []

    status_counts: dict[str, int] = {}
    items = []
    for child in children:
        status_counts[child.status] = status_counts.get(child.status, 0) + 1
        items.append(
            {
                "intake_id": str(child.id),
                "jira_issue_key": child.jira_issue_key,
                "jira_summary": child.jira_summary,
                "status": child.status,
                "assignee_user_id": str(child.assignee_user_id) if child.assignee_user_id else None,
                "jira_status": child.jira_status,
                "pr_url": child.pr_url,
            }
        )

    for task in jira_created:
        key = str(task.get("key") or "").upper()
        if key and not any(i["jira_issue_key"] == key for i in items):
            items.append(
                {
                    "intake_id": None,
                    "jira_issue_key": key,
                    "jira_summary": task.get("summary"),
                    "status": "not_started",
                    "assignee_user_id": task.get("assignee_user_id"),
                    "jira_status": task.get("status"),
                    "pr_url": None,
                }
            )

    total = len(items) or len(jira_created)
    completed = sum(1 for i in items if i["status"] == "completed")
    return {
        "parent_jira_key": parent_key,
        "parent_intake_id": str(parent.id) if parent else None,
        "parent_status": parent.status if parent else None,
        "total_subtasks": total,
        "completed_subtasks": completed,
        "status_counts": status_counts,
        "subtasks": items,
    }


def refresh_intake_from_jira(db: Session, intake: JiraTicketIntake, user_id: UUID) -> JiraTicketIntake:
    status = refresh_intake_jira_status(
        db,
        workspace_id=intake.workspace_id,
        user_id=user_id,
        issue_key=intake.jira_issue_key,
    )
    if status:
        intake.jira_status = status
        db.commit()
        db.refresh(intake)
    return intake
