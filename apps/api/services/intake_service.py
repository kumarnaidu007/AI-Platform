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
    review_spec_consistency,
)
from models import Project, Workspace
from models.requirements import (
    ClarificationAnswer,
    ClarificationQuestion,
    IntakeApproval,
    JiraTicketIntake,
    RequirementConversation,
    RequirementDocument,
)
from services.github_service import get_github_access_token, get_github_connection, list_repo_source_files
from services.jira_service import get_issue, JiraError
from services.notification_service import notify_user
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

    notify_user(
        db,
        workspace_id=intake.workspace_id,
        user_id=intake.user_id,
        notification_type="implementation_started",
        title=f"{intake.jira_issue_key}: implementation started",
        body="Pipeline is running. You will be notified when code is ready for your review.",
        link_path=f"/workspace/projects/{intake.project_id}",
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
