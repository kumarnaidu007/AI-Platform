from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class PlatformAgent(Base, TimestampMixin):
    __tablename__ = "platform_agents"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    default_step_order: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    plan_links: Mapped[list["PlanPlatformAgent"]] = relationship(back_populates="agent")
    workspace_links: Mapped[list["WorkspacePlatformAgent"]] = relationship(back_populates="agent")


class PlanPlatformAgent(Base):
    __tablename__ = "plan_platform_agents"

    plan_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True)
    platform_agent_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_agents.id", ondelete="CASCADE"), primary_key=True
    )

    agent: Mapped["PlatformAgent"] = relationship(back_populates="plan_links")


class WorkspacePlatformAgent(Base):
    __tablename__ = "workspace_platform_agents"

    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    platform_agent_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_agents.id", ondelete="CASCADE"), primary_key=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent: Mapped["PlatformAgent"] = relationship(back_populates="workspace_links")


class MemberAgentAccess(Base):
    __tablename__ = "member_agent_access"

    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    platform_agent_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_agents.id", ondelete="CASCADE"), primary_key=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    granted_by_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectAgent(Base, TimestampMixin):
    __tablename__ = "project_agents"
    __table_args__ = (UniqueConstraint("project_id", "platform_agent_id"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))
    platform_agent_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_agents.id", ondelete="CASCADE")
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    step_order: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agent: Mapped["PlatformAgent"] = relationship()
