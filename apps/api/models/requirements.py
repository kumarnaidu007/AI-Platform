from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class JiraTicketIntake(Base, TimestampMixin):
    __tablename__ = "jira_ticket_intakes"
    __table_args__ = (UniqueConstraint("workspace_id", "jira_issue_key"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    project_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"))
    jira_issue_key: Mapped[str] = mapped_column(String(32), nullable=False)
    jira_issue_id: Mapped[str | None] = mapped_column(String(64))
    jira_summary: Mapped[str | None] = mapped_column(Text)
    jira_status: Mapped[str | None] = mapped_column(String(64))
    jira_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), default="synced", nullable=False)
    repo_url: Mapped[str | None] = mapped_column(Text)
    base_branch: Mapped[str | None] = mapped_column(String(128))
    feature_branch: Mapped[str | None] = mapped_column(String(256))
    pending_publish_json: Mapped[dict | None] = mapped_column(JSONB)
    pr_url: Mapped[str | None] = mapped_column(Text)
    implementation_plan_json: Mapped[dict | None] = mapped_column(JSONB)
    pipeline_run_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by_user_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    questions: Mapped[list["ClarificationQuestion"]] = relationship(back_populates="intake", cascade="all, delete-orphan")
    documents: Mapped[list["RequirementDocument"]] = relationship(back_populates="intake", cascade="all, delete-orphan")
    conversations: Mapped[list["RequirementConversation"]] = relationship(back_populates="intake", cascade="all, delete-orphan")
    approvals: Mapped[list["IntakeApproval"]] = relationship(back_populates="intake", cascade="all, delete-orphan")


class ClarificationQuestion(Base):
    __tablename__ = "clarification_questions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    intake_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jira_ticket_intakes.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    allow_custom_answer: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    intake: Mapped["JiraTicketIntake"] = relationship(back_populates="questions")
    answer: Mapped["ClarificationAnswer | None"] = relationship(back_populates="question", uselist=False, cascade="all, delete-orphan")


class ClarificationAnswer(Base):
    __tablename__ = "clarification_answers"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clarification_questions.id", ondelete="CASCADE"), unique=True)
    selected_option: Mapped[str | None] = mapped_column(Text)
    custom_answer: Mapped[str | None] = mapped_column(Text)
    answered_by_user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    question: Mapped["ClarificationQuestion"] = relationship(back_populates="answer")


class RequirementDocument(Base):
    __tablename__ = "requirement_documents"
    __table_args__ = (UniqueConstraint("intake_id", "doc_type"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    intake_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jira_ticket_intakes.id", ondelete="CASCADE"))
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    intake: Mapped["JiraTicketIntake"] = relationship(back_populates="documents")


class RequirementConversation(Base):
    __tablename__ = "requirement_conversations"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    intake_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jira_ticket_intakes.id", ondelete="CASCADE"))
    document_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("requirement_documents.id", ondelete="SET NULL"))
    author_type: Mapped[str] = mapped_column(String(16), nullable=False)
    author_user_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    intake: Mapped["JiraTicketIntake"] = relationship(back_populates="conversations")


class IntakeApproval(Base):
    __tablename__ = "intake_approvals"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    intake_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jira_ticket_intakes.id", ondelete="CASCADE"))
    approval_type: Mapped[str] = mapped_column(String(32), nullable=False)
    approver_user_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    intake: Mapped["JiraTicketIntake"] = relationship(back_populates="approvals")


class WorkspaceNotification(Base):
    __tablename__ = "workspace_notifications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    link_path: Mapped[str | None] = mapped_column(String(512))
    intake_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jira_ticket_intakes.id", ondelete="CASCADE"))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
