from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import joinedload

from app.deps import DbDep, WorkspaceAuthDep, WorkspaceWriterDep
from models.requirements import (
    ClarificationQuestion,
    IntakeApproval,
    JiraTicketIntake,
    RequirementConversation,
    RequirementDocument,
)
from schemas.requirements import (
    AnswerQuestionRequest,
    ApprovalRequest,
    ApprovePrRequest,
    ConversationRequest,
    DocumentPatchRequest,
    IntakeCreateRequest,
    IntakeDetailResponse,
    IntakeSummaryResponse,
    StartImplementationRequest,
)
from services.intake_recovery_service import recover_intake_pending_changes
from services.intake_service import reconcile_intake_pipeline_status
from services.intake_serializers import intake_to_detail, intake_to_summary
from services.intake_service import (
    add_conversation,
    analyze_intake,
    answer_question,
    approve_plan,
    approve_pr_review,
    create_or_get_intake,
    fetch_jira_issue_for_user,
    get_intake_by_key,
    get_intake_or_404,
    lock_requirements,
    patch_document,
    reject_plan,
    start_implementation,
    submit_answers_and_generate_specs,
)
from services.jira_service import JiraError, user_has_jira_assigned

router = APIRouter(prefix="/api/workspace/intakes", tags=["requirements-intake"])


def _ensure_intake_owner(intake: JiraTicketIntake, user_id) -> None:
    if intake.user_id != user_id:
        raise HTTPException(403, "Only the assigned user can perform this action on this ticket")


def _load_detail(db, intake: JiraTicketIntake, user_id: UUID | None = None) -> IntakeDetailResponse:
    intake = reconcile_intake_pipeline_status(db, intake)
    if (
        user_id
        and intake.status == "awaiting_pr_review"
        and not (intake.pending_publish_json and intake.pending_publish_json.get("files"))
    ):
        try:
            intake = recover_intake_pending_changes(db, intake, user_id)
        except ValueError:
            pass
    questions = (
        db.query(ClarificationQuestion)
        .options(joinedload(ClarificationQuestion.answer))
        .filter(ClarificationQuestion.intake_id == intake.id)
        .order_by(ClarificationQuestion.sort_order.asc())
        .all()
    )
    documents = (
        db.query(RequirementDocument)
        .filter(RequirementDocument.intake_id == intake.id)
        .order_by(RequirementDocument.doc_type.asc())
        .all()
    )
    conversations = (
        db.query(RequirementConversation)
        .filter(RequirementConversation.intake_id == intake.id)
        .order_by(RequirementConversation.created_at.asc())
        .all()
    )
    approvals = db.query(IntakeApproval).filter(IntakeApproval.intake_id == intake.id).all()
    return intake_to_detail(intake, questions, documents, conversations, approvals)


@router.get("", response_model=list[IntakeSummaryResponse])
def list_intakes(ctx: WorkspaceAuthDep, db: DbDep):
    rows = (
        db.query(JiraTicketIntake)
        .filter(JiraTicketIntake.workspace_id == ctx.workspace_id)
        .order_by(JiraTicketIntake.updated_at.desc())
        .limit(100)
        .all()
    )
    return [intake_to_summary(r) for r in rows]


@router.post("", response_model=IntakeDetailResponse)
def create_intake(body: IntakeCreateRequest, ctx: WorkspaceWriterDep, db: DbDep):
    if not user_has_jira_assigned(db, ctx.workspace_id, ctx.user.id):
        raise HTTPException(400, "Jira has not been assigned to your account")
    try:
        issue = fetch_jira_issue_for_user(db, ctx.workspace_id, ctx.user.id, body.jira_issue_key)
    except JiraError as exc:
        raise HTTPException(400, str(exc)) from exc
    intake = create_or_get_intake(
        db,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
        jira_issue_key=body.jira_issue_key,
        project_id=body.project_id,
        issue_row=issue,
    )
    if intake.status == "synced" and not db.query(ClarificationQuestion).filter(ClarificationQuestion.intake_id == intake.id).count():
        try:
            intake = analyze_intake(db, intake, ctx.user.id)
        except Exception:
            pass
    return _load_detail(db, intake, ctx.user.id)


@router.get("/by-key/{issue_key}", response_model=IntakeDetailResponse)
def get_intake_by_issue_key(issue_key: str, ctx: WorkspaceAuthDep, db: DbDep):
    intake = get_intake_by_key(db, ctx.workspace_id, issue_key)
    if not intake:
        raise HTTPException(404, "Intake not found")
    return _load_detail(db, intake, ctx.user.id)


@router.get("/{intake_id}", response_model=IntakeDetailResponse)
def get_intake(intake_id: UUID, ctx: WorkspaceAuthDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _load_detail(db, intake, ctx.user.id)


@router.post("/{intake_id}/analyze", response_model=IntakeDetailResponse)
def run_analyze(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        intake = analyze_intake(db, intake, ctx.user.id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/questions/{question_id}/answer", response_model=IntakeDetailResponse)
def post_answer(
    intake_id: UUID,
    question_id: UUID,
    body: AnswerQuestionRequest,
    ctx: WorkspaceWriterDep,
    db: DbDep,
):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        answer_question(
            db,
            intake,
            question_id,
            ctx.user.id,
            selected_option=body.selected_option,
            custom_answer=body.custom_answer,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/submit-answers", response_model=IntakeDetailResponse)
def submit_answers(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        intake = submit_answers_and_generate_specs(db, intake)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    return _load_detail(db, intake)


@router.patch("/{intake_id}/documents/{doc_type}", response_model=IntakeDetailResponse)
def update_document(
    intake_id: UUID,
    doc_type: str,
    body: DocumentPatchRequest,
    ctx: WorkspaceWriterDep,
    db: DbDep,
):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        patch_document(db, intake, doc_type, body.content_json)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/conversations", response_model=IntakeDetailResponse)
def post_conversation(intake_id: UUID, body: ConversationRequest, ctx: WorkspaceWriterDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        add_conversation(db, intake, ctx.user.id, body.message, body.document_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/lock", response_model=IntakeDetailResponse)
def lock_intake(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _ensure_intake_owner(intake, ctx.user.id)
        intake = lock_requirements(db, intake, ctx.user.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/approve-plan", response_model=IntakeDetailResponse)
def approve_plan_endpoint(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep, body: ApprovalRequest | None = None):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _ensure_intake_owner(intake, ctx.user.id)
        intake = approve_plan(db, intake, ctx.user.id, body.comment if body else None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/reject-plan", response_model=IntakeDetailResponse)
def reject_plan_endpoint(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep, body: ApprovalRequest | None = None):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _ensure_intake_owner(intake, ctx.user.id)
        intake = reject_plan(db, intake, ctx.user.id, body.comment if body else None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/start-implementation", response_model=IntakeDetailResponse)
def start_impl(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep, body: StartImplementationRequest | None = None):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _ensure_intake_owner(intake, ctx.user.id)
        intake = start_implementation(
            db,
            intake,
            ctx.user.id,
            agent_keys=body.agent_keys if body else None,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/approve-pr", response_model=IntakeDetailResponse)
def approve_pr(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep, body: ApprovePrRequest | None = None):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _ensure_intake_owner(intake, ctx.user.id)
        payload = body or ApprovePrRequest()
        intake = approve_pr_review(
            db,
            intake,
            ctx.user.id,
            comment=payload.comment,
            branch_name=payload.branch_name,
            base_branch=payload.base_branch,
            pr_title=payload.pr_title,
            reviewers=payload.reviewers,
            merge=payload.merge,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake, ctx.user.id)


@router.post("/{intake_id}/recover-pending-changes", response_model=IntakeDetailResponse)
def recover_pending_changes(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _ensure_intake_owner(intake, ctx.user.id)
        intake = recover_intake_pending_changes(db, intake, ctx.user.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake, ctx.user.id)


@router.post("/{intake_id}/reset-for-reimplementation", response_model=IntakeDetailResponse)
def reset_for_reimplementation(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep):
    """Send ticket back to approved so the member can start implementation again."""
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _ensure_intake_owner(intake, ctx.user.id)
        if intake.status not in ("awaiting_pr_review", "completed", "implementation_failed"):
            raise ValueError("Only tickets awaiting PR review, failed, or completed can be reset")
        intake.status = "approved"
        intake.pending_publish_json = None
        intake.pr_url = None
        db.commit()
        db.refresh(intake)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake, ctx.user.id)
