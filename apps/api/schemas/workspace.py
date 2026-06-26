from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CompanyDashboardResponse(BaseModel):
    company_name: str
    company_slug: str
    role: str
    email_domain: str | None = None
    projects_count: int
    integrations_enabled: int
    services_enabled: int
    team_count: int = 0


class WorkspaceSettingsResponse(BaseModel):
    email_domain: str | None = None
    timezone: str = "UTC"


class WorkspaceSettingsUpdateRequest(BaseModel):
    email_domain: str


class CompanyIntegrationCatalogItem(BaseModel):
    integration_key: str
    name: str
    description: str | None = None
    category: str
    auth_type: str = ""
    is_granted: bool = True


class MyIntegrationItem(BaseModel):
    integration_key: str
    name: str
    description: str | None = None
    category: str
    auth_type: str = ""
    is_assigned: bool
    is_connected: bool = False
    connection_status: str = "not_configured"
    connection_name: str | None = None
    config_schema: dict = Field(default_factory=dict)
    config_metadata: dict = Field(default_factory=dict)
    last_tested_at: datetime | None = None
    last_test_status: bool | None = None
    last_error_message: str | None = None


class CompanyIntegrationConnectRequest(BaseModel):
    connection_name: str = "Default"
    config: dict = Field(default_factory=dict)


class CompanyIntegrationTestResponse(BaseModel):
    success: bool
    message: str


class CompanyServiceItem(BaseModel):
    service_key: str
    display_name: str
    is_granted: bool


class WorkspaceMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    integrations_assigned: int = 0
    agents_assigned: int = 0
    joined_at: datetime


class WorkspaceMemberCreateRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "team_member"


class WorkspaceMemberUpdateRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class MemberIntegrationAccessItem(BaseModel):
    integration_key: str
    name: str
    category: str
    is_connected: bool
    is_assigned: bool


class MemberIntegrationAccessUpdate(BaseModel):
    integration_key: str
    is_assigned: bool


class MemberIntegrationsAccessUpdate(BaseModel):
    integrations: list[MemberIntegrationAccessUpdate]


class UserProfileResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    joined_at: datetime
    integrations_assigned: int = 0
    integrations_connected: int = 0


class UserProfileUpdateRequest(BaseModel):
    full_name: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserDashboardResponse(BaseModel):
    company_name: str
    company_slug: str
    role: str
    email_domain: str | None = None
    my_projects_count: int = 0
    company_projects_count: int = 0
    integrations_assigned: int = 0
    integrations_connected: int = 0
    services_enabled: int = 0
    recent_projects: list["ProjectSummary"] = Field(default_factory=list)
    integration_status: list["IntegrationStatusSummary"] = Field(default_factory=list)


class IntegrationStatusSummary(BaseModel):
    integration_key: str
    name: str
    is_connected: bool
    connection_status: str


class ProjectSummary(BaseModel):
    id: UUID
    name: str
    status: str
    frontend_stack: str | None = None
    backend_stack: str | None = None
    created_at: datetime
    created_by_name: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    status: str
    frontend_stack: str | None = None
    backend_stack: str | None = None
    db_type: str | None = None
    vcs_provider: str | None = None
    repo_url: str | None = None
    pm_tool: str | None = None
    notification_channels: list[str] = Field(default_factory=list)
    monthly_token_budget_usd: float | None = None
    created_by: UUID
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    pipeline_runs_count: int = 0
    active_pipeline_runs: int = 0


class ProjectCreateRequest(BaseModel):
    name: str
    description: str | None = None
    frontend_stack: str | None = None
    backend_stack: str | None = None
    db_type: str | None = None
    vcs_provider: str | None = None
    repo_url: str | None = None
    pm_tool: str | None = None
    notification_channels: list[str] = Field(default_factory=list)
    monthly_token_budget_usd: float | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    frontend_stack: str | None = None
    backend_stack: str | None = None
    db_type: str | None = None
    vcs_provider: str | None = None
    repo_url: str | None = None
    pm_tool: str | None = None
    notification_channels: list[str] | None = None
    monthly_token_budget_usd: float | None = None


class PipelineRunSummary(BaseModel):
    id: UUID
    status: str
    current_step: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
