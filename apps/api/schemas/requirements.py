from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IntakeCreateRequest(BaseModel):
    jira_issue_key: str = Field(..., min_length=3, max_length=32)
    project_id: UUID | None = None
    lead_planning: bool = False


class LeadPlanEpicRequest(BaseModel):
    jira_issue_key: str = Field(..., min_length=3, max_length=32)
    project_id: UUID | None = None


class AssignIntakeRequest(BaseModel):
    assignee_user_id: UUID


class HandoffSubtasksRequest(BaseModel):
    comment: str | None = None


class AnswerQuestionRequest(BaseModel):
    selected_option: str | None = None
    custom_answer: str | None = None


class ConversationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    document_id: UUID | None = None


class DocumentPatchRequest(BaseModel):
    content_json: dict


class ApprovalRequest(BaseModel):
    comment: str | None = None


class ApprovePrRequest(BaseModel):
    comment: str | None = None
    branch_name: str | None = Field(default=None, max_length=256)
    base_branch: str | None = Field(default=None, max_length=128)
    pr_title: str | None = Field(default=None, max_length=512)
    reviewers: list[str] = Field(default_factory=list)
    merge: bool = False


class StartImplementationRequest(BaseModel):
    agent_keys: list[str] | None = None


class ClarificationAnswerResponse(BaseModel):
    id: UUID
    selected_option: str | None
    custom_answer: str | None
    answered_by_user_id: UUID
    created_at: datetime


class ClarificationQuestionResponse(BaseModel):
    id: UUID
    category: str
    question_text: str
    options: list[str]
    allow_custom_answer: bool
    is_required: bool
    sort_order: int
    rationale: str | None
    status: str
    answer: ClarificationAnswerResponse | None = None


class RequirementDocumentResponse(BaseModel):
    id: UUID
    doc_type: str
    title: str
    content_json: dict
    version: int
    status: str
    updated_at: datetime


class ConversationMessageResponse(BaseModel):
    id: UUID
    author_type: str
    author_user_id: UUID | None
    message: str
    document_id: UUID | None
    created_at: datetime


class IntakeApprovalResponse(BaseModel):
    id: UUID
    approval_type: str
    status: str
    approver_user_id: UUID | None
    comment: str | None
    decided_at: datetime | None


class PendingFileResponse(BaseModel):
    path: str
    content: str
    message: str | None = None


class PendingChangesResponse(BaseModel):
    branch_name: str
    base_branch: str
    pr_title: str
    pr_body: str | None = None
    summary: str | None = None
    files: list[PendingFileResponse] = Field(default_factory=list)


class IntakeSummaryResponse(BaseModel):
    id: UUID
    jira_issue_key: str
    jira_summary: str | None
    jira_status: str | None
    jira_url: str | None
    status: str
    project_id: UUID | None
    repo_url: str | None
    base_branch: str | None
    feature_branch: str | None
    pr_url: str | None = None
    pipeline_run_id: UUID | None
    locked_at: datetime | None
    created_at: datetime
    updated_at: datetime
    questions_total: int = 0
    questions_answered: int = 0
    intake_mode: str = "member"
    parent_jira_key: str | None = None
    planner_user_id: UUID | None = None
    assignee_user_id: UUID | None = None
    jira_project_key: str | None = None


class IntakeDetailResponse(IntakeSummaryResponse):
    questions: list[ClarificationQuestionResponse] = Field(default_factory=list)
    documents: list[RequirementDocumentResponse] = Field(default_factory=list)
    conversations: list[ConversationMessageResponse] = Field(default_factory=list)
    approvals: list[IntakeApprovalResponse] = Field(default_factory=list)
    implementation_plan: dict | None = None
    pending_changes: PendingChangesResponse | None = None
    jira_tasks: dict | None = None


class EpicProgressSubtaskResponse(BaseModel):
    intake_id: UUID | None = None
    jira_issue_key: str
    jira_summary: str | None = None
    status: str
    assignee_user_id: UUID | None = None
    jira_status: str | None = None
    pr_url: str | None = None


class EpicProgressResponse(BaseModel):
    parent_jira_key: str
    parent_intake_id: UUID | None = None
    parent_status: str | None = None
    total_subtasks: int = 0
    completed_subtasks: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    subtasks: list[EpicProgressSubtaskResponse] = Field(default_factory=list)


class JiraPortalIssueResponse(BaseModel):
    id: str | None
    key: str | None
    summary: str | None
    description: str | None
    issue_type: str | None
    status: str | None
    priority: str | None
    assignee: str | None
    reporter: str | None
    project_key: str | None
    project_name: str | None
    url: str | None
    intake_id: UUID | None = None
    intake_status: str | None = None


class NotificationResponse(BaseModel):
    id: UUID
    notification_type: str
    title: str
    body: str | None
    link_path: str | None
    intake_id: UUID | None
    is_read: bool
    created_at: datetime
