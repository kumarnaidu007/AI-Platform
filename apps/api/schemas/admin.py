from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConfigSchemaField(BaseModel):
    key: str
    label: str
    type: str
    required: bool = False
    default: str | int | None = None


class PlatformIntegrationResponse(BaseModel):
    id: UUID
    integration_key: str
    name: str
    description: str | None
    category: str
    auth_type: str
    is_enabled: bool
    config_schema: dict[str, Any]
    documentation_url: str | None
    connection_status: str
    connection_name: str | None = None
    last_tested_at: datetime | None = None
    last_test_status: bool | None = None
    last_error_message: str | None = None
    config_metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class PlatformIntegrationUpdate(BaseModel):
    is_enabled: bool | None = None


class ConnectionSaveRequest(BaseModel):
    connection_name: str = "Default"
    config: dict[str, Any] = Field(default_factory=dict)


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str


class PlatformServiceResponse(BaseModel):
    id: UUID
    service_key: str
    display_name: str
    description: str | None
    is_enabled: bool
    is_configured: bool
    config_metadata: dict[str, Any] = Field(default_factory=dict)
    last_tested_at: datetime | None = None
    last_test_status: bool | None = None
    last_error_message: str | None = None

    model_config = {"from_attributes": True}


class PlatformServiceUpdate(BaseModel):
    is_enabled: bool | None = None
    api_key: str | None = None
    config_metadata: dict[str, Any] | None = None


class PlatformSettingResponse(BaseModel):
    key: str
    label: str
    description: str | None
    type: str
    value: str | bool | int | float

    model_config = {"from_attributes": True}


class PlatformSettingsUpdate(BaseModel):
    settings: dict[str, Any]


class PlatformStatsResponse(BaseModel):
    total_integrations: int
    enabled_integrations: int
    connected_integrations: int
    error_integrations: int
    not_configured_integrations: int
    services_enabled: int
    total_services: int


class PlanResponse(BaseModel):
    id: UUID
    name: str
    max_projects: int
    max_parallel_pipelines: int
    monthly_token_budget_usd: float
    is_active: bool
    companies_count: int = 0
    integration_keys: list[str] = Field(default_factory=list)


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    plan_id: UUID
    plan_name: str
    users_count: int = 0
    projects_count: int = 0
    active_pipelines: int = 0
    monthly_usage_usd: float = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyDetailResponse(CompanyResponse):
    admin_email: str | None = None
    admin_name: str | None = None
    limits_override: dict[str, Any] = Field(default_factory=dict)
    recent_projects: list[dict[str, Any]] = Field(default_factory=list)


class CompanyCreateRequest(BaseModel):
    name: str
    slug: str
    plan_id: UUID
    status: str = "trial"
    email_domain: str | None = None
    admin_name: str | None = None
    admin_email: str | None = None
    admin_password: str | None = None


class CompanyUpdateRequest(BaseModel):
    name: str | None = None
    status: str | None = None
    plan_id: UUID | None = None


class CompanyIntegrationAccessItem(BaseModel):
    integration_key: str
    name: str
    category: str
    is_enabled: bool
    platform_enabled: bool
    platform_connected: bool
    assignable: bool
    connection_status: str


class CompanyIntegrationAccessUpdate(BaseModel):
    integration_key: str
    is_enabled: bool


class CompanyIntegrationsAccessUpdate(BaseModel):
    integrations: list[CompanyIntegrationAccessUpdate]


class CompanyServiceAccessItem(BaseModel):
    service_key: str
    display_name: str
    is_enabled: bool
    platform_enabled: bool
    platform_configured: bool
    assignable: bool


class CompanyServiceAccessUpdate(BaseModel):
    service_key: str
    is_enabled: bool


class CompanyServicesAccessUpdate(BaseModel):
    services: list[CompanyServiceAccessUpdate]


class DashboardMetricsResponse(BaseModel):
    platform_stats: PlatformStatsResponse
    total_companies: int
    active_companies: int
    trial_companies: int
    suspended_companies: int
    active_pipelines: int
    monthly_platform_cost_usd: float
    monthly_token_usage_m: float
    failed_pipelines_24h: int


class PipelineActivityItem(BaseModel):
    id: str
    company_name: str
    project_name: str
    step: str
    status: str
    started_at: datetime | None


class AuditEventResponse(BaseModel):
    id: UUID
    timestamp: datetime
    user: str
    action: str
    resource_type: str
    resource_name: str
    company_name: str | None
    ip_address: str | None


class SystemServiceResponse(BaseModel):
    name: str
    status: str
    latency_ms: int | None
    message: str


class SystemHealthResponse(BaseModel):
    healthy: int
    degraded: int
    down: int
    services: list[SystemServiceResponse]
    queue: dict[str, Any]
