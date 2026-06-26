from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class WorkspaceIntegrationConnection(Base, TimestampMixin):
    __tablename__ = "workspace_integration_connections"
    __table_args__ = (UniqueConstraint("workspace_id", "platform_integration_id"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    platform_integration_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_integrations.id", ondelete="CASCADE")
    )
    connection_name: Mapped[str] = mapped_column(String(255), default="Default", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="not_configured", nullable=False)
    encrypted_config_ref: Mapped[str | None] = mapped_column(String(512))
    config_metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[bool | None] = mapped_column(Boolean)
    last_error_message: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    integration: Mapped["PlatformIntegration"] = relationship()  # type: ignore[name-defined]


class MemberIntegrationAccess(Base):
    __tablename__ = "member_integration_access"

    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    platform_integration_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_integrations.id", ondelete="CASCADE"), primary_key=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    granted_by_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemberIntegrationConnection(Base, TimestampMixin):
    __tablename__ = "member_integration_connections"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", "platform_integration_id"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    platform_integration_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_integrations.id", ondelete="CASCADE")
    )
    connection_name: Mapped[str] = mapped_column(String(255), default="Default", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="not_configured", nullable=False)
    encrypted_config_ref: Mapped[str | None] = mapped_column(String(512))
    config_metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[bool | None] = mapped_column(Boolean)
    last_error_message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    integration: Mapped["PlatformIntegration"] = relationship()  # type: ignore[name-defined]
