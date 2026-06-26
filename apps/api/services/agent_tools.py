"""ReAct-style tools available to pipeline agents."""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from agents.context import PipelineContext
from services.github_service import (
    get_github_access_token,
    get_github_connection,
    get_file_content,
    parse_repo_url,
)
from services.rag_service import format_rag_context, retrieve_context

ToolFn = Callable[[Session, PipelineContext, dict[str, Any]], Any]


def tool_search_codebase(db: Session, ctx: PipelineContext, args: dict[str, Any]) -> str:
    query = str(args.get("query", ctx.requirements_text))
    hits = retrieve_context(db, project_id=ctx.project_id, query=query, top_k=int(args.get("top_k", 8)))
    ctx.rag_hits = hits
    return format_rag_context(hits)


def tool_read_repo_file(db: Session, ctx: PipelineContext, args: dict[str, Any]) -> str:
    if not ctx.repo_url:
        return "No repository linked to this project."
    path = str(args.get("path", "")).lstrip("/")
    if not path:
        return "path argument required"
    conn = get_github_connection(db, ctx.workspace_id, ctx.user_id)
    token = get_github_access_token(conn)
    ref = parse_repo_url(ctx.repo_url)
    branch = str(args.get("branch", "develop"))
    try:
        content = get_file_content(token, ref, path, branch=branch)
    except Exception:
        content = get_file_content(token, ref, path)
    ctx.files_read[path] = content[:12000]
    return content[:12000]


def tool_list_repo_files(db: Session, ctx: PipelineContext, args: dict[str, Any]) -> list[str]:
    from services.github_service import list_repo_source_files

    if not ctx.repo_url:
        return []
    conn = get_github_connection(db, ctx.workspace_id, ctx.user_id)
    token = get_github_access_token(conn)
    files = list_repo_source_files(token, ctx.repo_url, max_files=int(args.get("limit", 50)))
    return [f[0] for f in files]


AGENT_TOOLS: dict[str, ToolFn] = {
    "search_codebase": tool_search_codebase,
    "read_repo_file": tool_read_repo_file,
    "list_repo_files": tool_list_repo_files,
}


def run_tools(db: Session, ctx: PipelineContext, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for call in tool_calls:
        name = call.get("tool")
        args = call.get("args") or {}
        fn = AGENT_TOOLS.get(name)
        if not fn:
            results.append({"tool": name, "error": f"Unknown tool: {name}"})
            continue
        try:
            output = fn(db, ctx, args)
            results.append({"tool": name, "output": output})
        except Exception as exc:
            results.append({"tool": name, "error": str(exc)})
    return results
