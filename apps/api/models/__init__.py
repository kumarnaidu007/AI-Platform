from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["WorkspaceMember"]] = relationship(back_populates="user")
    projects_created: Mapped[list["Project"]] = relationship(back_populates="creator")


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    max_projects: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_parallel_pipelines: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    monthly_token_budget_usd: Mapped[float] = mapped_column(Numeric(12, 4), default=100.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="plan")


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="trial", nullable=False)
    plan_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    plan: Mapped["Plan"] = relationship(back_populates="workspaces")
    members: Mapped[list["WorkspaceMember"]] = relationship(back_populates="workspace")
    limits: Mapped["WorkspaceLimits | None"] = relationship(back_populates="workspace", uselist=False)
    settings: Mapped["WorkspaceSettings | None"] = relationship(back_populates="workspace", uselist=False)
    integrations: Mapped[list["IntegrationConfig"]] = relationship(back_populates="workspace")
    projects: Mapped[list["Project"]] = relationship(back_populates="workspace")


class WorkspaceLimits(Base):
    __tablename__ = "workspace_limits"

    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    max_projects: Mapped[int | None] = mapped_column(Integer)
    max_parallel_pipelines: Mapped[int | None] = mapped_column(Integer)
    monthly_token_budget_usd: Mapped[float | None] = mapped_column(Numeric(12, 4))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="limits")


class WorkspaceMember(Base, TimestampMixin):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), default="team_member", nullable=False)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped["Workspace"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")


class WorkspaceSettings(Base):
    __tablename__ = "workspace_settings"

    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    default_notification_channels: Mapped[list[str] | None] = mapped_column(ARRAY(Text), default=list)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    email_domain: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="settings")


class IntegrationConfig(Base, TimestampMixin):
    __tablename__ = "integration_configs"
    __table_args__ = (UniqueConstraint("workspace_id", "integration_type", "display_name"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    integration_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    encrypted_config_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[bool | None] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="integrations")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    created_by: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    frontend_stack: Mapped[str | None] = mapped_column(String(64))
    backend_stack: Mapped[str | None] = mapped_column(String(64))
    db_type: Mapped[str | None] = mapped_column(String(64))
    vcs_provider: Mapped[str | None] = mapped_column(String(64))
    repo_url: Mapped[str | None] = mapped_column(String(512))
    pm_tool: Mapped[str | None] = mapped_column(String(64))
    notification_channels: Mapped[list[str] | None] = mapped_column(ARRAY(Text), default=list)
    monthly_token_budget_usd: Mapped[float | None] = mapped_column(Numeric(12, 4))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="projects")
    creator: Mapped["User"] = relationship(back_populates="projects_created")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(back_populates="project")


class PipelineRun(Base, TimestampMixin):
    __tablename__ = "pipeline_runs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    started_by_user_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(64))
    langgraph_thread_id: Mapped[str | None] = mapped_column(String(255))
    approval_plan_json: Mapped[dict | None] = mapped_column(JSONB)
    graph_state_json: Mapped[dict | None] = mapped_column(JSONB)
    review_retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    project: Mapped["Project"] = relationship(back_populates="pipeline_runs")
    steps: Mapped[list["PipelineStep"]] = relationship(back_populates="pipeline_run")


class PipelineStep(Base, TimestampMixin):
    __tablename__ = "pipeline_steps"
    __table_args__ = (UniqueConstraint("pipeline_run_id", "step_name"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pipeline_run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE")
    )
    step_name: Mapped[str] = mapped_column(String(64), nullable=False)
    step_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="steps")
    agent_logs: Mapped[list["AgentLog"]] = relationship(back_populates="pipeline_step")


class AgentLog(Base, TimestampMixin):
    __tablename__ = "agent_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pipeline_step_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_steps.id", ondelete="CASCADE")
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    input_json: Mapped[dict | None] = mapped_column(JSONB)
    output_json: Mapped[dict | None] = mapped_column(JSONB)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128))

    pipeline_step: Mapped["PipelineStep"] = relationship(back_populates="agent_logs")


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"))
    user_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(INET)


class UsageLedger(Base, TimestampMixin):
    __tablename__ = "usage_ledger"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    project_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"))
    pipeline_run_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0, nullable=False)


from models.requirements import (  # noqa: E402
    ClarificationAnswer,
    ClarificationQuestion,
    IntakeApproval,
    JiraTicketIntake,
    RequirementConversation,
    RequirementDocument,
    WorkspaceNotification,
)
