from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import joinedload

from app.deps import DbDep, TeamLeadDep, WorkspaceAuthDep, WorkspaceWriterDep
from constants.roles import TEAM_LEAD
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
    AssignIntakeRequest,
    ConversationRequest,
    DocumentPatchRequest,
    EpicProgressResponse,
    EpicProgressSubtaskResponse,
    HandoffSubtasksRequest,
    IntakeCreateRequest,
    IntakeDetailResponse,
    IntakeSummaryResponse,
    LeadPlanEpicRequest,
    StartImplementationRequest,
)
from services.intake_permissions import (
    can_edit_intake,
    can_implement_intake,
    can_plan_jira_tasks,
    can_view_intake,
    is_team_lead,
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
    create_jira_subtasks_from_plan,
    create_lead_planning_intake,
    create_or_get_intake,
    epic_progress,
    fetch_jira_issue_for_user,
    get_intake_by_key,
    get_intake_or_404,
    handoff_subtasks_to_members,
    lock_requirements,
    patch_document,
    refresh_intake_from_jira,
    reject_plan,
    start_implementation,
    submit_answers_and_generate_specs,
)
from services.jira_service import JiraError, user_has_jira_assigned

router = APIRouter(prefix="/api/workspace/intakes", tags=["requirements-intake"])


def _require_view(intake: JiraTicketIntake, ctx: WorkspaceAuthDep) -> None:
    if not can_view_intake(intake, ctx.user.id, ctx.member_role):
        raise HTTPException(403, "You do not have access to this ticket intake")


def _require_edit(intake: JiraTicketIntake, ctx: WorkspaceAuthDep) -> None:
    if not can_edit_intake(intake, ctx.user.id, ctx.member_role):
        raise HTTPException(403, "You cannot edit this ticket intake")


def _require_implement(intake: JiraTicketIntake, ctx: WorkspaceAuthDep) -> None:
    if not can_implement_intake(intake, ctx.user.id, ctx.member_role):
        raise HTTPException(403, "Only the assigned member can start implementation on this ticket")


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
    q = db.query(JiraTicketIntake).filter(JiraTicketIntake.workspace_id == ctx.workspace_id)
    if not is_team_lead(ctx.member_role):
        q = q.filter(
            (JiraTicketIntake.user_id == ctx.user.id)
            | (JiraTicketIntake.assignee_user_id == ctx.user.id)
            | (JiraTicketIntake.planner_user_id == ctx.user.id)
        )
    rows = q.order_by(JiraTicketIntake.updated_at.desc()).limit(100).all()
    return [intake_to_summary(r) for r in rows]


@router.post("/plan-epic", response_model=IntakeDetailResponse)
def plan_epic(body: LeadPlanEpicRequest, ctx: TeamLeadDep, db: DbDep):
    """Team lead: start AI-assisted planning on an epic/story (no implementation)."""
    if not user_has_jira_assigned(db, ctx.workspace_id, ctx.user.id):
        raise HTTPException(400, "Jira has not been assigned to your account")
    try:
        issue = fetch_jira_issue_for_user(db, ctx.workspace_id, ctx.user.id, body.jira_issue_key)
    except JiraError as exc:
        raise HTTPException(400, str(exc)) from exc
    intake = create_lead_planning_intake(
        db,
        workspace_id=ctx.workspace_id,
        planner_user_id=ctx.user.id,
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


@router.get("/epic/{parent_key}/progress", response_model=EpicProgressResponse)
def get_epic_progress(parent_key: str, ctx: WorkspaceAuthDep, db: DbDep):
    data = epic_progress(db, ctx.workspace_id, parent_key)
    subtasks = []
    for row in data.get("subtasks") or []:
        aid = row.get("assignee_user_id")
        iid = row.get("intake_id")
        subtasks.append(
            EpicProgressSubtaskResponse(
                intake_id=UUID(iid) if iid else None,
                jira_issue_key=row["jira_issue_key"],
                jira_summary=row.get("jira_summary"),
                status=row["status"],
                assignee_user_id=UUID(aid) if aid else None,
                jira_status=row.get("jira_status"),
                pr_url=row.get("pr_url"),
            )
        )
    pid = data.get("parent_intake_id")
    return EpicProgressResponse(
        parent_jira_key=data["parent_jira_key"],
        parent_intake_id=UUID(pid) if pid else None,
        parent_status=data.get("parent_status"),
        total_subtasks=data.get("total_subtasks", 0),
        completed_subtasks=data.get("completed_subtasks", 0),
        status_counts=data.get("status_counts") or {},
        subtasks=subtasks,
    )


@router.post("", response_model=IntakeDetailResponse)
def create_intake(body: IntakeCreateRequest, ctx: WorkspaceWriterDep, db: DbDep):
    if not user_has_jira_assigned(db, ctx.workspace_id, ctx.user.id):
        raise HTTPException(400, "Jira has not been assigned to your account")
    try:
        issue = fetch_jira_issue_for_user(db, ctx.workspace_id, ctx.user.id, body.jira_issue_key)
    except JiraError as exc:
        raise HTTPException(400, str(exc)) from exc

    if body.lead_planning:
        if ctx.member_role != TEAM_LEAD:
            raise HTTPException(403, "Only team leads can create lead planning intakes")
        intake = create_lead_planning_intake(
            db,
            workspace_id=ctx.workspace_id,
            planner_user_id=ctx.user.id,
            jira_issue_key=body.jira_issue_key,
            project_id=body.project_id,
            issue_row=issue,
        )
    else:
        intake = create_or_get_intake(
            db,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user.id,
            jira_issue_key=body.jira_issue_key,
            project_id=body.project_id,
            issue_row=issue,
        )
        intake.assignee_user_id = intake.assignee_user_id or ctx.user.id

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
    _require_view(intake, ctx)
    try:
        refresh_intake_from_jira(db, intake, ctx.user.id)
    except Exception:
        pass
    return _load_detail(db, intake, ctx.user.id)


@router.get("/{intake_id}", response_model=IntakeDetailResponse)
def get_intake(intake_id: UUID, ctx: WorkspaceAuthDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    _require_view(intake, ctx)
    return _load_detail(db, intake, ctx.user.id)


@router.post("/{intake_id}/analyze", response_model=IntakeDetailResponse)
def run_analyze(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _require_edit(intake, ctx)
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
        _require_edit(intake, ctx)
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
        _require_edit(intake, ctx)
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
        _require_edit(intake, ctx)
        patch_document(db, intake, doc_type, body.content_json)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/conversations", response_model=IntakeDetailResponse)
def post_conversation(intake_id: UUID, body: ConversationRequest, ctx: WorkspaceWriterDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _require_edit(intake, ctx)
        add_conversation(db, intake, ctx.user.id, body.message, body.document_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/lock", response_model=IntakeDetailResponse)
def lock_intake(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _require_edit(intake, ctx)
        intake = lock_requirements(db, intake, ctx.user.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/approve-plan", response_model=IntakeDetailResponse)
def approve_plan_endpoint(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep, body: ApprovalRequest | None = None):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _require_edit(intake, ctx)
        intake = approve_plan(db, intake, ctx.user.id, body.comment if body else None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/reject-plan", response_model=IntakeDetailResponse)
def reject_plan_endpoint(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep, body: ApprovalRequest | None = None):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _require_edit(intake, ctx)
        intake = reject_plan(db, intake, ctx.user.id, body.comment if body else None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/create-jira-tasks", response_model=IntakeDetailResponse)
def create_jira_tasks(intake_id: UUID, ctx: TeamLeadDep, db: DbDep):
    """Team lead: AI breakdown + create Jira subtasks under the epic."""
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        if not can_plan_jira_tasks(intake, ctx.user.id, ctx.member_role):
            raise HTTPException(403, "Only team lead can create Jira subtasks for this epic")
        intake = create_jira_subtasks_from_plan(db, intake, ctx.user.id)
    except JiraError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/handoff", response_model=list[IntakeSummaryResponse])
def handoff_to_members(intake_id: UUID, ctx: TeamLeadDep, db: DbDep, body: HandoffSubtasksRequest | None = None):
    """Team lead: create member intakes for each subtask and notify assignees."""
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        if not can_plan_jira_tasks(intake, ctx.user.id, ctx.member_role):
            raise HTTPException(403, "Only team lead can hand off subtasks")
        children = handoff_subtasks_to_members(db, intake, ctx.user.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return [intake_to_summary(c) for c in children]


@router.patch("/{intake_id}/assign", response_model=IntakeDetailResponse)
def assign_intake(intake_id: UUID, body: AssignIntakeRequest, ctx: TeamLeadDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        intake.assignee_user_id = body.assignee_user_id
        db.commit()
        db.refresh(intake)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _load_detail(db, intake)


@router.post("/{intake_id}/start-implementation", response_model=IntakeDetailResponse)
def start_impl(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep, body: StartImplementationRequest | None = None):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _require_implement(intake, ctx)
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
        _require_implement(intake, ctx)
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
        _require_implement(intake, ctx)
        intake = recover_intake_pending_changes(db, intake, ctx.user.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _load_detail(db, intake, ctx.user.id)


@router.post("/{intake_id}/reset-for-reimplementation", response_model=IntakeDetailResponse)
def reset_for_reimplementation(intake_id: UUID, ctx: WorkspaceWriterDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _require_implement(intake, ctx)
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


@router.post("/{intake_id}/refresh-jira", response_model=IntakeDetailResponse)
def refresh_jira(intake_id: UUID, ctx: WorkspaceAuthDep, db: DbDep):
    try:
        intake = get_intake_or_404(db, ctx.workspace_id, intake_id)
        _require_view(intake, ctx)
        intake = refresh_intake_from_jira(db, intake, ctx.user.id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _load_detail(db, intake)
