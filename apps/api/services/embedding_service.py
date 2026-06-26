"""OpenAI-compatible embedding generation for RAG."""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from services.llm import require_llm_config, resolve_embedding_config


def embed_texts(db: Session, texts: list[str], *, model: str | None = None) -> list[list[float]]:
    if not texts:
        return []
    require_llm_config(db)
    config = resolve_embedding_config(db)
    api_key = config["api_key"]
    embed_model = model or config["model"]
    base_url = config.get("endpoint") or "https://api.openai.com/v1"
    payload = {"model": embed_model, "input": texts}
    url = f"{base_url.rstrip('/')}/embeddings"
    with httpx.Client(timeout=120) as client:
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    return [row["embedding"] for row in sorted(data["data"], key=lambda r: r["index"])]
