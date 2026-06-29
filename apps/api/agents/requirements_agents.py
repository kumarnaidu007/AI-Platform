"""LLM agents for Jira ticket requirements discovery."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from services.llm import complete_json

SYSTEM = (
    "You are a senior software requirements analyst for enterprise .NET projects. "
    "Respond with valid JSON only, no markdown."
)

DOC_TYPES = ("overview", "db", "api", "auth", "validation", "exception")
CATEGORIES = ("repo", "api", "db", "auth", "validation", "exception", "scope", "general")


def generate_clarification_questions(
    db: Session,
    *,
    issue_key: str,
    summary: str,
    description: str,
    repo_context: str,
    project_stack: str,
) -> list[dict[str, Any]]:
    prompt = f"""Analyze Jira ticket {issue_key} and generate clarification questions BEFORE any implementation.

Ticket summary: {summary}
Ticket description: {description or 'No description'}
Project stack: {project_stack}
Repository context (file paths / snippets):
{repo_context[:8000]}

Generate 12-18 questions across categories: repo, api, db, auth, validation, exception, scope, general.

Each question must help clarify:
- repository URL, base branch, feature branch naming
- new vs existing controller/component
- API routes, methods, request/response
- database tables, migrations, stored procedures
- authentication/authorization approach
- input validation rules
- exception handling and error responses

Return JSON: {{
  "questions": [
    {{
      "category": "repo",
      "question_text": "...",
      "options": ["option1", "option2", "I'll specify"],
      "allow_custom_answer": true,
      "is_required": true,
      "rationale": "why this matters"
    }}
  ]
}}"""
    result = complete_json(db, system=SYSTEM, user=prompt)
    data = result.parsed_json or {}
    questions = data.get("questions") or []
    normalized: list[dict[str, Any]] = []
    for i, q in enumerate(questions):
        cat = str(q.get("category") or "general").lower()
        if cat not in CATEGORIES:
            cat = "general"
        opts = q.get("options") or []
        if not isinstance(opts, list):
            opts = []
        opts = [str(o) for o in opts[:6]]
        if "I'll specify" not in opts and "Other" not in opts:
            opts.append("I'll specify")
        normalized.append(
            {
                "category": cat,
                "question_text": str(q.get("question_text") or "").strip(),
                "options_json": opts,
                "allow_custom_answer": bool(q.get("allow_custom_answer", True)),
                "is_required": bool(q.get("is_required", True)),
                "sort_order": i,
                "rationale": q.get("rationale"),
            }
        )
    return [q for q in normalized if q["question_text"]]


def generate_domain_documents(
    db: Session,
    *,
    issue_key: str,
    summary: str,
    description: str,
    answers_text: str,
    project_stack: str,
) -> dict[str, dict[str, Any]]:
    prompt = f"""Based on confirmed answers for Jira {issue_key}, produce SEPARATE structured specification documents.
Do NOT merge everything into one document.

Ticket: {summary}
Description: {description or ''}
Stack: {project_stack}

Confirmed answers:
{answers_text[:12000]}

Return JSON with keys overview, db, api, auth, validation, exception.
Each value: {{ "title": "...", "sections": {{ ... structured fields ... }} }}

overview: brief summary + links to other docs (max 200 words in summary)
db: tables, columns, migrations, stored_procedures, indexes
api: endpoints (method, route, controller new|existing, request, response), branch name
auth: mechanism, roles, attributes, public routes
validation: rules per endpoint/field
exception: error codes, HTTP status, global handler notes"""
    result = complete_json(db, system=SYSTEM, user=prompt)
    data = result.parsed_json or {}
    out: dict[str, dict[str, Any]] = {}
    for doc_type in DOC_TYPES:
        block = data.get(doc_type)
        if isinstance(block, dict):
            out[doc_type] = {
                "title": block.get("title") or f"{doc_type.upper()} specification — {issue_key}",
                "content_json": block.get("sections") if "sections" in block else block,
            }
    return out


def review_spec_consistency(db: Session, *, documents: dict[str, dict]) -> list[dict[str, str]]:
    prompt = f"""Review these requirement documents for conflicts or gaps.
Return JSON: {{ "issues": [{{ "doc_type": "api", "message": "..." }}] }}

Documents:
{json.dumps(documents, indent=2)[:14000]}"""
    result = complete_json(db, system=SYSTEM, user=prompt)
    data = result.parsed_json or {}
    return data.get("issues") or []


def generate_implementation_plan(
    db: Session,
    *,
    issue_key: str,
    documents: dict[str, dict],
) -> dict[str, Any]:
    prompt = f"""Create a detailed implementation plan for {issue_key} from locked specifications.
Every file listed must be implementable without cross-file conflicts.

Return JSON: {{
  "summary": "...",
  "steps": ["step1", "step2"],
  "files_to_create": [{{"path": "...", "purpose": "...", "must_export": ["TypeOrMethodName"]}}],
  "files_to_modify": [{{"path": "...", "purpose": "..."}}],
  "technical_contracts": {{
    "interfaces": [
      {{"name": "IExample", "file_hint": "path/to/IExample.cs", "methods": ["Task<T> GetAsync(...)"]}}
    ],
    "json_resources": [
      {{"file": "path/data.json", "root_type": "object", "root_key": "items", "item_fields": ["id", "name"]}}
    ],
    "di_registration": ["Service registration rules"],
    "cross_file_rules": [
      "Controllers must only call methods on declared interfaces",
      "JSON loaders must match documented root_key shape"
    ]
  }},
  "testing_notes": "...",
  "risks": ["..."]
}}

Specs:
{json.dumps(documents, indent=2)[:12000]}"""
    result = complete_json(db, system=SYSTEM, user=prompt)
    plan = result.parsed_json or {"summary": "Implementation plan generated"}
    from services.implementation_plan_service import enrich_implementation_plan

    return enrich_implementation_plan(db, plan, documents=documents)


def agent_reply_to_conversation(
    db: Session,
    *,
    issue_key: str,
    message: str,
    documents: dict[str, dict],
    history: list[str],
) -> str:
    prompt = f"""You are helping refine requirements for {issue_key}.
User message: {message}
Recent history: {history[-6:]}
Current specs summary keys: {list(documents.keys())}

Reply helpfully in plain text (2-4 sentences). If they request a spec change, describe what section to update."""
    result = complete_json(db, system=SYSTEM, user=f'Return JSON: {{"reply": "your message"}}')
    data = result.parsed_json or {}
    return str(data.get("reply") or result.content[:500])
