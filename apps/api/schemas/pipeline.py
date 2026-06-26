from datetime import datetime

from uuid import UUID



from pydantic import BaseModel, Field, model_validator





class PipelineStartRequest(BaseModel):

    requirements_text: str = Field(default="", max_length=50000)
    jira_issue_key: str | None = Field(default=None, max_length=50)
    agent_keys: list[str] | None = None
    additional_context: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_requirements(self):
        prompt = self.requirements_text.strip()
        if self.jira_issue_key:
            self.requirements_text = prompt
            return self
        if len(prompt) < 10:
            raise ValueError("requirements_text must be at least 10 characters when no Jira issue is selected")
        self.requirements_text = prompt
        return self





class PipelineApprovalRequest(BaseModel):

    comment: str | None = None





class AgentLogResponse(BaseModel):

    id: UUID

    agent_name: str

    input_json: dict | None = None

    output_json: dict | None = None

    input_tokens: int = 0

    output_tokens: int = 0

    cost_usd: float = 0

    model_name: str | None = None

    created_at: datetime





class PipelineStepResponse(BaseModel):

    id: UUID

    step_name: str

    step_order: int

    status: str

    retry_count: int = 0

    started_at: datetime | None = None

    finished_at: datetime | None = None

    error_message: str | None = None

    logs: list[AgentLogResponse] = Field(default_factory=list)





class PipelineRunDetailResponse(BaseModel):

    id: UUID

    project_id: UUID

    status: str

    current_step: str | None = None

    started_at: datetime | None = None

    finished_at: datetime | None = None

    error_message: str | None = None

    created_at: datetime

    approval_plan: dict | None = None

    steps: list[PipelineStepResponse] = Field(default_factory=list)

    artifacts: dict = Field(default_factory=dict)





class PipelineRunSummaryResponse(BaseModel):

    id: UUID

    status: str

    current_step: str | None = None

    started_at: datetime | None = None

    finished_at: datetime | None = None

    error_message: str | None = None

    created_at: datetime

    steps_total: int = 0

    steps_completed: int = 0

    approval_plan: dict | None = None


