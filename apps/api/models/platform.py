from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class PlatformIntegration(Base, TimestampMixin):
    __tablename__ = "platform_integrations"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    integration_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_schema_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    documentation_url: Mapped[str | None] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    connections: Mapped[list["PlatformConnection"]] = relationship(back_populates="integration")
    plan_links: Mapped[list["PlanPlatformIntegration"]] = relationship(back_populates="integration")
    company_links: Mapped[list["CompanyPlatformIntegration"]] = relationship(back_populates="integration")


class PlatformConnection(Base, TimestampMixin):
    __tablename__ = "platform_connections"
    __table_args__ = (UniqueConstraint("platform_integration_id", "connection_name"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
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
    created_by: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    integration: Mapped["PlatformIntegration"] = relationship(back_populates="connections")


class PlatformService(Base, TimestampMixin):
    __tablename__ = "platform_services"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    service_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    encrypted_config_ref: Mapped[str | None] = mapped_column(String(512))
    config_metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[bool | None] = mapped_column(Boolean)
    last_error_message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    plan_links: Mapped[list["PlanPlatformService"]] = relationship(back_populates="service")
    company_links: Mapped[list["CompanyPlatformService"]] = relationship(back_populates="service")

    plan_links: Mapped[list["PlanPlatformService"]] = relationship(back_populates="service")
    company_links: Mapped[list["CompanyPlatformService"]] = relationship(back_populates="service")


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlanPlatformIntegration(Base):
    __tablename__ = "plan_platform_integrations"

    plan_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True)
    platform_integration_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_integrations.id", ondelete="CASCADE"), primary_key=True
    )

    integration: Mapped["PlatformIntegration"] = relationship(back_populates="plan_links")


class PlanPlatformService(Base):
    __tablename__ = "plan_platform_services"

    plan_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True)
    platform_service_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_services.id", ondelete="CASCADE"), primary_key=True
    )

    service: Mapped["PlatformService"] = relationship(back_populates="plan_links")


class CompanyPlatformIntegration(Base):
    __tablename__ = "company_platform_integrations"

    company_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    platform_integration_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_integrations.id", ondelete="CASCADE"), primary_key=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    integration: Mapped["PlatformIntegration"] = relationship(back_populates="company_links")


class CompanyPlatformService(Base):
    __tablename__ = "company_platform_services"

    company_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    platform_service_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_services.id", ondelete="CASCADE"), primary_key=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    service: Mapped["PlatformService"] = relationship(back_populates="company_links")
