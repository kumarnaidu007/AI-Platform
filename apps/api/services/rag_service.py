"""RAG: chunk, embed, index and retrieve codebase context."""

from __future__ import annotations

import math
import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from models.rag import CodebaseChunk
from services.embedding_service import embed_texts
from services.github_service import (
    GitHubError,
    get_github_access_token,
    get_github_connection,
    list_repo_source_files,
)

CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200
INDEXABLE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".cs", ".rb", ".php",
    ".sql", ".md", ".yaml", ".yml", ".json", ".toml", ".rs", ".kt",
}


def _chunk_text(text: str, *, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def index_project_repo(
    db: Session,
    *,
    project_id: UUID,
    workspace_id: UUID,
    user_id: UUID,
    repo_url: str,
    max_files: int = 80,
) -> dict[str, Any]:
    conn = get_github_connection(db, workspace_id, user_id)
    token = get_github_access_token(conn)
    files = list_repo_source_files(token, repo_url, max_files=max_files, extensions=INDEXABLE_EXTENSIONS)

    db.query(CodebaseChunk).filter(CodebaseChunk.project_id == project_id).delete()
    db.flush()

    rows: list[CodebaseChunk] = []
    texts_for_embed: list[str] = []
    for file_path, content in files:
        if not content.strip():
            continue
        for idx, chunk in enumerate(_chunk_text(content)):
            row = CodebaseChunk(
                project_id=project_id,
                file_path=file_path,
                chunk_index=idx,
                content=chunk,
                token_count=max(1, len(chunk) // 4),
            )
            rows.append(row)
            texts_for_embed.append(chunk[:8000])

    if not rows:
        db.commit()
        return {"files_indexed": 0, "chunks_indexed": 0}

    batch_size = 32
    for i in range(0, len(texts_for_embed), batch_size):
        batch_texts = texts_for_embed[i : i + batch_size]
        embeddings = embed_texts(db, batch_texts)
        for j, emb in enumerate(embeddings):
            rows[i + j].embedding = emb

    db.add_all(rows)
    db.commit()
    return {"files_indexed": len(files), "chunks_indexed": len(rows)}


def retrieve_context(
    db: Session,
    *,
    project_id: UUID,
    query: str,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    chunks = db.query(CodebaseChunk).filter(CodebaseChunk.project_id == project_id).all()
    if not chunks:
        return []
    try:
        query_emb = embed_texts(db, [query[:4000]])[0]
    except Exception:
        return _keyword_fallback(chunks, query, top_k)

    scored: list[tuple[float, CodebaseChunk]] = []
    for chunk in chunks:
        if not chunk.embedding:
            continue
        scored.append((_cosine_similarity(query_emb, chunk.embedding), chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"file_path": c.file_path, "content": c.content, "score": round(score, 4)}
        for score, c in scored[:top_k]
        if score > 0.1
    ]


def _keyword_fallback(chunks: list[CodebaseChunk], query: str, top_k: int) -> list[dict[str, Any]]:
    terms = {t.lower() for t in re.findall(r"\w+", query) if len(t) > 2}
    scored: list[tuple[int, CodebaseChunk]] = []
    for chunk in chunks:
        text = chunk.content.lower()
        score = sum(1 for t in terms if t in text)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"file_path": c.file_path, "content": c.content, "score": float(score)}
        for score, c in scored[:top_k]
    ]


def format_rag_context(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "No indexed codebase context available."
    parts = []
    for hit in hits:
        parts.append(f"### {hit['file_path']}\n{hit['content'][:2500]}")
    return "\n\n".join(parts)
