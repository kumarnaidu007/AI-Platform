"""Shared pipeline execution context passed between agents."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class PipelineContext:
    run_id: UUID
    project_id: UUID
    workspace_id: UUID
    user_id: UUID
    project_name: str
    project_description: str | None
    frontend_stack: str | None
    backend_stack: str | None
    db_type: str | None
    vcs_provider: str | None
    repo_url: str | None
    pm_tool: str | None
    requirements_text: str
    additional_context: dict[str, Any] = field(default_factory=dict)
    jira_issue: dict[str, Any] | None = None
    prd: dict[str, Any] | None = None
    architecture: dict[str, Any] | None = None
    tasks: list[dict[str, Any]] = field(default_factory=list)
    pull_requests: list[dict[str, Any]] = field(default_factory=list)
    pending_publish: dict[str, Any] | None = None
    tests: dict[str, Any] | None = None
    test_results: dict[str, Any] | None = None
    deployment: dict[str, Any] | None = None
    smoke_test: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    rag_hits: list[dict[str, Any]] = field(default_factory=list)
    files_read: dict[str, str] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    review_retry_count: int = 0
    review_feedback: list[dict[str, Any]] = field(default_factory=list)
    last_review_output: dict[str, Any] | None = None
    last_validation_issues: list[dict[str, str]] = field(default_factory=list)
    progress_callback: Callable[[str, dict[str, Any]], None] | None = field(
        default=None, repr=False, compare=False
    )

    def project_stack_summary(self) -> str:
        parts = [p for p in [self.frontend_stack, self.backend_stack, self.db_type] if p]
        return " + ".join(parts) if parts else "TypeScript/React + Python/FastAPI + PostgreSQL"

    def rag_context_block(self) -> str:
        if not self.rag_hits:
            return ""
        from services.rag_service import format_rag_context

        return "\n\nRelevant codebase context:\n" + format_rag_context(self.rag_hits)

    def memory_block(self) -> str:
        if not self.memory:
            return ""
        return f"\n\nProject memory from prior runs:\n{self.memory}"

    def to_checkpoint(self) -> dict[str, Any]:
        return {
            "prd": self.prd,
            "architecture": self.architecture,
            "tasks": self.tasks,
            "pull_requests": self.pull_requests,
            "pending_publish": self.pending_publish,
            "tests": self.tests,
            "test_results": self.test_results,
            "deployment": self.deployment,
            "smoke_test": self.smoke_test,
            "validation": self.validation,
            "rag_hits": self.rag_hits,
            "files_read": self.files_read,
            "review_retry_count": self.review_retry_count,
            "review_feedback": self.review_feedback,
            "last_review_output": self.last_review_output,
            "last_validation_issues": self.last_validation_issues,
            "jira_issue": self.jira_issue,
        }

    @classmethod
    def from_checkpoint(cls, base: "PipelineContext", data: dict[str, Any]) -> "PipelineContext":
        base.prd = data.get("prd")
        base.architecture = data.get("architecture")
        base.tasks = data.get("tasks") or []
        base.pull_requests = data.get("pull_requests") or []
        base.pending_publish = data.get("pending_publish")
        base.tests = data.get("tests")
        base.test_results = data.get("test_results")
        base.deployment = data.get("deployment")
        base.smoke_test = data.get("smoke_test")
        base.validation = data.get("validation")
        base.rag_hits = data.get("rag_hits") or []
        base.files_read = data.get("files_read") or {}
        base.review_retry_count = int(data.get("review_retry_count") or 0)
        base.review_feedback = list(data.get("review_feedback") or [])
        base.last_review_output = data.get("last_review_output")
        base.last_validation_issues = list(data.get("last_validation_issues") or [])
        base.jira_issue = data.get("jira_issue")
        return base
