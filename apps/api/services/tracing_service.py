"""Optional LangSmith tracing for agent steps."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy.orm import Session

from models.platform import PlatformService
from services.secrets import decrypt_secrets


def configure_tracing(db: Session) -> bool:
    service = db.query(PlatformService).filter(PlatformService.service_key == "langsmith").first()
    if not service or not service.is_enabled or not service.encrypted_config_ref:
        return False
    secrets = decrypt_secrets(service.encrypted_config_ref)
    api_key = secrets.get("api_key")
    if not api_key:
        return False
    metadata = service.config_metadata_json or {}
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_PROJECT"] = str(metadata.get("project_name", "ai-dev-platform"))
    return True


@contextmanager
def trace_agent_step(agent_key: str, *, run_id: str, metadata: dict[str, Any] | None = None) -> Iterator[None]:
    if os.environ.get("LANGCHAIN_TRACING_V2") != "true":
        yield
        return
    try:
        from langsmith import traceable

        @traceable(name=f"agent.{agent_key}", metadata={"run_id": run_id, **(metadata or {})})
        def _noop() -> None:
            return None

        _noop()
        yield
    except Exception:
        yield
