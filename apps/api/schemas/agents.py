from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PlatformAgentResponse(BaseModel):
    id: UUID
    agent_key: str
    name: str
    description: str | None = None
    category: str
    default_step_order: int
    is_enabled: bool
    group: str | None = None
    artifact: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class PlatformAgentUpdate(BaseModel):
    is_enabled: bool | None = None


class CompanyAgentAccessItem(BaseModel):
    agent_key: str
    name: str
    category: str
    group: str | None = None
    default_step_order: int
    is_enabled: bool
    platform_enabled: bool
    assignable: bool


class CompanyAgentAccessUpdate(BaseModel):
    agent_key: str
    is_enabled: bool


class CompanyAgentsAccessUpdate(BaseModel):
    agents: list[CompanyAgentAccessUpdate]


class CompanyAgentCatalogItem(BaseModel):
    agent_key: str
    name: str
    description: str | None = None
    category: str
    group: str | None = None
    default_step_order: int
    is_granted: bool = True


class MyAgentItem(BaseModel):
    agent_key: str
    name: str
    description: str | None = None
    category: str
    group: str | None = None
    default_step_order: int
    is_assigned: bool
    is_enabled_on_platform: bool = True


class MemberAgentAccessItem(BaseModel):
    agent_key: str
    name: str
    category: str
    group: str | None = None
    default_step_order: int
    is_assigned: bool


class MemberAgentAccessUpdate(BaseModel):
    agent_key: str
    is_assigned: bool


class MemberAgentsAccessUpdate(BaseModel):
    agents: list[MemberAgentAccessUpdate]


class ProjectAgentItem(BaseModel):
    agent_key: str
    name: str
    category: str
    group: str | None = None
    step_order: int
    is_enabled: bool
    is_assigned: bool
    default_step_order: int


class ProjectAgentsUpdate(BaseModel):
    agents: list["ProjectAgentConfigItem"]


class ProjectAgentConfigItem(BaseModel):
    agent_key: str
    is_enabled: bool
    step_order: int | None = None
