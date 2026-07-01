"""Serialize intake ORM rows to API responses."""

from __future__ import annotations

from models.requirements import (
    ClarificationQuestion,
    IntakeApproval,
    JiraTicketIntake,
    RequirementConversation,
    RequirementDocument,
)
from schemas.requirements import (
    ClarificationAnswerResponse,
    ClarificationQuestionResponse,
    ConversationMessageResponse,
    IntakeApprovalResponse,
    IntakeDetailResponse,
    IntakeSummaryResponse,
    PendingChangesResponse,
    PendingFileResponse,
    RequirementDocumentResponse,
)
from services.intake_service import intake_summary


def _question_response(q: ClarificationQuestion) -> ClarificationQuestionResponse:
    answer = None
    if q.answer:
        answer = ClarificationAnswerResponse(
            id=q.answer.id,
            selected_option=q.answer.selected_option,
            custom_answer=q.answer.custom_answer,
            answered_by_user_id=q.answer.answered_by_user_id,
            created_at=q.answer.created_at,
        )
    opts = q.options_json if isinstance(q.options_json, list) else []
    return ClarificationQuestionResponse(
        id=q.id,
        category=q.category,
        question_text=q.question_text,
        options=[str(o) for o in opts],
        allow_custom_answer=q.allow_custom_answer,
        is_required=q.is_required,
        sort_order=q.sort_order,
        rationale=q.rationale,
        status=q.status,
        answer=answer,
    )


def intake_to_summary(intake: JiraTicketIntake, stats: dict | None = None) -> IntakeSummaryResponse:
    stats = stats or {}
    return IntakeSummaryResponse(
        id=intake.id,
        jira_issue_key=intake.jira_issue_key,
        jira_summary=intake.jira_summary,
        jira_status=intake.jira_status,
        jira_url=intake.jira_url,
        status=intake.status,
        project_id=intake.project_id,
        repo_url=intake.repo_url,
        base_branch=intake.base_branch,
        feature_branch=intake.feature_branch,
        pr_url=intake.pr_url,
        pipeline_run_id=intake.pipeline_run_id,
        locked_at=intake.locked_at,
        created_at=intake.created_at,
        updated_at=intake.updated_at,
        questions_total=stats.get("questions_total", 0),
        questions_answered=stats.get("questions_answered", 0),
        intake_mode=intake.intake_mode or "member",
        parent_jira_key=intake.parent_jira_key,
        planner_user_id=intake.planner_user_id,
        assignee_user_id=intake.assignee_user_id,
        jira_project_key=intake.jira_project_key,
    )


def _pending_changes_response(raw: dict | None) -> PendingChangesResponse | None:
    if not raw or not raw.get("files"):
        return None
    files = []
    for item in raw.get("files") or []:
        path = str(item.get("path") or "").lstrip("/")
        if not path:
            continue
        files.append(
            PendingFileResponse(
                path=path,
                content=str(item.get("content") or ""),
                message=item.get("message"),
            )
        )
    if not files:
        return None
    return PendingChangesResponse(
        branch_name=str(raw.get("branch_name") or "feature/ai-changes"),
        base_branch=str(raw.get("base_branch") or "main"),
        pr_title=str(raw.get("pr_title") or "feat: AI implementation"),
        pr_body=raw.get("pr_body"),
        summary=raw.get("summary"),
        files=files,
    )


def intake_to_detail(
    intake: JiraTicketIntake,
    questions: list[ClarificationQuestion],
    documents: list[RequirementDocument],
    conversations: list[RequirementConversation],
    approvals: list[IntakeApproval],
) -> IntakeDetailResponse:
    stats = {
        "questions_total": len(questions),
        "questions_answered": sum(1 for q in questions if q.status == "answered"),
    }
    base = intake_to_summary(intake, stats)
    return IntakeDetailResponse(
        **base.model_dump(),
        questions=[_question_response(q) for q in questions],
        documents=[
            RequirementDocumentResponse(
                id=d.id,
                doc_type=d.doc_type,
                title=d.title,
                content_json=d.content_json or {},
                version=d.version,
                status=d.status,
                updated_at=d.updated_at,
            )
            for d in documents
        ],
        conversations=[
            ConversationMessageResponse(
                id=c.id,
                author_type=c.author_type,
                author_user_id=c.author_user_id,
                message=c.message,
                document_id=c.document_id,
                created_at=c.created_at,
            )
            for c in conversations
        ],
        approvals=[
            IntakeApprovalResponse(
                id=a.id,
                approval_type=a.approval_type,
                status=a.status,
                approver_user_id=a.approver_user_id,
                comment=a.comment,
                decided_at=a.decided_at,
            )
            for a in approvals
        ],
        implementation_plan=intake.implementation_plan_json,
        pending_changes=_pending_changes_response(intake.pending_publish_json),
        jira_tasks=intake.jira_tasks_json,
    )
