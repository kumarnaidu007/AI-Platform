"""Implementation plan enrichment, validation, and post-generation consistency checks."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from agents.context import PipelineContext
from services.llm import LLMResponse, complete_json

logger = logging.getLogger(__name__)

SYSTEM = (
    "You are a senior software architect. Respond with valid JSON only, no markdown fences. "
    "Be precise about interfaces, JSON shapes, and cross-file rules so code generators cannot drift."
)


def _countries_api_contracts(plan: dict[str, Any]) -> dict[str, Any] | None:
    """Deterministic contracts for SCRUM-6-style countries endpoints — no LLM needed."""
    paths: list[str] = []
    for item in (plan.get("files_to_create") or []) + (plan.get("files_to_modify") or []):
        if isinstance(item, dict) and item.get("path"):
            paths.append(str(item["path"]).replace("\\", "/"))

    if not any("countries" in p.lower() for p in paths):
        return None

    json_path = next((p for p in paths if p.lower().endswith("countries.json")), "OrderProcessing/Resources/countries.json")
    interface_path = next((p for p in paths if "icountriesstore" in p.lower()), "OrderProcessing/Services/ICountriesStore.cs")
    store_path = next((p for p in paths if p.lower().endswith("countriesstore.cs")), "OrderProcessing/Services/CountriesStore.cs")
    dto_path = next((p for p in paths if "countryresponseminimal" in p.lower()), "OrderProcessing/Models/CountryResponseMinimal.cs")
    controller_path = next((p for p in paths if "countriescontroller" in p.lower()), "OrderProcessing/Controllers/CountriesController.cs")

    return {
        "interfaces": [
            {
                "name": "ICountriesStore",
                "file_hint": interface_path,
                "methods": [
                    "Task EnsureLoadedAsync(CancellationToken cancellationToken = default)",
                    "Task<int> CountAsync(CancellationToken cancellationToken = default)",
                    "Task<IReadOnlyList<CountryResponseMinimal>> GetAllAsync(int page, int size, CancellationToken cancellationToken = default)",
                    "Task<CountryResponseMinimal?> GetByCodeAsync(string code, CancellationToken cancellationToken = default)",
                ],
            }
        ],
        "json_resources": [
            {
                "file": json_path,
                "root_type": "object",
                "root_key": "countries",
                "item_fields": ["code", "name"],
            }
        ],
        "di_registration": [
            "Register ICountriesStore as singleton: services.AddSingleton<ICountriesStore, CountriesStore>()",
        ],
        "cross_file_rules": [
            f"{store_path} must declare ': ICountriesStore' and implement every async method",
            f"Load {json_path} as object with root key 'countries' (array of {{code, name}}), not a bare JSON array",
            f"{dto_path} uses PascalCase properties Code and Name with JsonPropertyName attributes",
            f"{controller_path} injects ICountriesStore and calls GetAllAsync/GetByCodeAsync — no reflection",
            "Do not register CountriesStore more than once in DI",
        ],
    }


def enrich_implementation_plan(
    db: Session,
    plan: dict[str, Any],
    *,
    documents: dict[str, dict] | None = None,
    stack_summary: str = "",
) -> dict[str, Any]:
    """Add technical_contracts if missing so code_writer and review share one source of truth."""
    if plan.get("technical_contracts") and (plan.get("files_to_create") or plan.get("files_to_modify")):
        return plan

    inferred = _countries_api_contracts(plan)
    if inferred:
        merged = dict(plan)
        merged["technical_contracts"] = inferred
        logger.info("Applied deterministic countries API technical contracts (no LLM enrich)")
        return merged

    prompt = f"""Expand this implementation plan with explicit technical contracts every generated file must follow.

Stack: {stack_summary or "unknown"}

Current plan:
{json.dumps(plan, indent=2)[:10000]}

Specs:
{json.dumps(documents or {}, indent=2)[:8000]}

Return the FULL plan JSON merged with these keys (keep existing keys):
{{
  "summary": "...",
  "steps": ["..."],
  "files_to_create": [{{"path": "...", "purpose": "...", "must_export": ["optional type/method names"]}}],
  "files_to_modify": [{{"path": "...", "purpose": "..."}}],
  "technical_contracts": {{
    "interfaces": [
      {{"name": "IExample", "file_hint": "Services/IExample.cs", "methods": ["Task<T> MethodAsync(...)"]}}
    ],
    "json_resources": [
      {{"file": "path/to/data.json", "root_type": "object", "root_key": "countries", "item_fields": ["code", "name"]}}
    ],
    "di_registration": ["how services are registered"],
    "cross_file_rules": [
      "Controllers must only call methods declared on interfaces",
      "JSON loaders must match the documented root shape"
    ]
  }},
  "testing_notes": "...",
  "risks": ["..."]
}}

Rules:
- List EVERY file from files_to_create/files_to_modify.
- cross_file_rules must prevent compile errors (async/sync mismatch, wrong JSON shape, duplicate DI registration).
- For embedded JSON with a wrapper object, document root_key explicitly."""
    result = complete_json(db, system=SYSTEM, user=prompt, max_completion_tokens=8192)
    enriched = result.parsed_json if result.parsed_json else plan
    for key in ("summary", "steps", "files_to_create", "files_to_modify", "testing_notes", "risks"):
        if key in plan and key not in enriched:
            enriched[key] = plan[key]
    if not enriched.get("technical_contracts"):
        enriched["technical_contracts"] = _default_contracts_from_plan(plan)
    return enriched


def _default_contracts_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    files = [
        *(plan.get("files_to_create") or []),
        *(plan.get("files_to_modify") or []),
    ]
    json_resources: list[dict[str, Any]] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if path.endswith(".json"):
            entry: dict[str, Any] = {
                "file": path,
                "root_type": "object",
            }
            if "countries.json" in path.lower():
                entry["root_key"] = "countries"
                entry["item_fields"] = ["code", "name"]
            json_resources.append(entry)
    return {
        "interfaces": [],
        "json_resources": json_resources,
        "di_registration": [],
        "cross_file_rules": [
            "All public types referenced across files must use identical method names and signatures",
            "Prefer async Task-based methods on interfaces when controllers use async actions",
        ],
    }


def validate_plan_for_codegen(plan: dict[str, Any]) -> list[str]:
    """Return human-readable blockers if the plan is not ready for code generation."""
    issues: list[str] = []
    creates = plan.get("files_to_create") or []
    modifies = plan.get("files_to_modify") or []
    if not creates and not modifies:
        issues.append("Plan has no files_to_create or files_to_modify")
    if not plan.get("summary"):
        issues.append("Plan missing summary")
    contracts = plan.get("technical_contracts") or {}
    if not contracts.get("cross_file_rules"):
        issues.append("Plan missing technical_contracts.cross_file_rules")
    return issues


def contracts_block(plan: dict[str, Any]) -> str:
    contracts = plan.get("technical_contracts")
    if not contracts:
        return ""
    return (
        "\n## MANDATORY TECHNICAL CONTRACTS — every file MUST comply exactly:\n"
        + json.dumps(contracts, indent=2)[:7000]
    )


def review_feedback_block(ctx: PipelineContext) -> str:
    if not ctx.review_feedback:
        return ""
    lines = ["\n## PRIOR REVIEW FEEDBACK — fix ALL items before resubmitting:"]
    for fb in ctx.review_feedback[-3:]:
        attempt = int(fb.get("attempt", 0)) + 1
        lines.append(f"\n### Review attempt {attempt}")
        if fb.get("summary"):
            lines.append(str(fb["summary"]))
        for comment in fb.get("comments") or []:
            lines.append(f"- {comment}")
    return "\n".join(lines)[:4000]


def prior_file_signatures(prior_files: list[dict[str, str]], *, max_files: int = 8) -> str:
    """Extract public API surface from already-generated files for cross-file consistency."""
    lines: list[str] = []
    for item in prior_files[-max_files:]:
        path = item.get("path", "")
        content = item.get("content", "")
        if not content:
            continue
        sigs: list[str] = []
        for raw in content.splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("#"):
                continue
            if re.match(
                r"^(public |internal |export |interface |class |record |def |async def |func )",
                stripped,
            ):
                sigs.append(stripped[:180])
            elif stripped.startswith(("[JsonPropertyName", "[HttpGet", "[Route", "Task<", "IActionResult")):
                sigs.append(stripped[:180])
        if sigs:
            lines.append(f"\n### {path}\n" + "\n".join(sigs[:12]))
    if not lines:
        return ""
    return "\n## ALREADY GENERATED — match these signatures in dependent files:\n" + "\n".join(lines)[:5000]


def _check_json_resources(plan: dict[str, Any], files: list[dict[str, str]]) -> list[dict[str, str]]:
    """Deterministic JSON shape checks from plan contracts."""
    issues: list[dict[str, str]] = []
    contracts = plan.get("technical_contracts") or {}
    resources = contracts.get("json_resources") or []
    by_path = {f["path"]: f.get("content", "") for f in files if f.get("path")}

    for spec in resources:
        if not isinstance(spec, dict):
            continue
        path = str(spec.get("file") or "")
        content = by_path.get(path)
        if not content:
            continue
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            issues.append({"file": path, "issue": f"Invalid JSON: {exc}"})
            continue
        root_key = spec.get("root_key")
        if root_key and isinstance(data, dict):
            if root_key not in data:
                issues.append(
                    {
                        "file": path,
                        "issue": f"JSON root must contain key '{root_key}' per plan contract",
                    }
                )
        elif spec.get("root_type") == "object" and isinstance(data, list):
            issues.append(
                {
                    "file": path,
                    "issue": "JSON root must be an object per plan, not a bare array",
                }
            )
    return issues


def check_generated_consistency(
    db: Session,
    ctx: PipelineContext,
    files: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Return blocking issues via fast deterministic rules (no LLM)."""
    from services.codegen_validation_service import validate_pending_publish

    blocking = validate_pending_publish(ctx, files)
    blocking.extend(_check_json_resources(ctx.additional_context.get("implementation_plan") or {}, files))

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in blocking:
        key = f"{item.get('file')}::{item.get('issue')}"
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def fix_generation_issues(
    db: Session,
    ctx: PipelineContext,
    files: list[dict[str, str]],
    issues: list[dict[str, str]],
) -> tuple[list[dict[str, str]], LLMResponse | None]:
    """Re-generate only files with blocking issues using explicit fix instructions."""
    if not issues:
        return files, None

    plan = ctx.additional_context.get("implementation_plan") or {}
    by_path = {f["path"]: dict(f) for f in files}
    responses: list[LLMResponse] = []

    for issue in issues[:8]:
        path = issue["file"]
        if path not in by_path:
            continue
        current = by_path[path]
        prompt = f"""Fix ONE file to resolve a blocking consistency issue.

File: {path}
Blocking issue: {issue['issue']}

{contracts_block(plan if isinstance(plan, dict) else {})}

Current content:
{(current.get('content') or '')[:10000]}

{prior_file_signatures([f for p, f in by_path.items() if p != path])}

Return JSON: {{ "path": "{path}", "content": "full fixed file", "message": "fix: ..." }}"""
        llm = complete_json(db, system=SYSTEM, user=prompt, max_completion_tokens=16384, retries=2)
        responses.append(llm)
        if llm.parsed_json and llm.parsed_json.get("content"):
            by_path[path] = {
                "path": path,
                "content": str(llm.parsed_json["content"]),
                "message": str(llm.parsed_json.get("message") or f"fix: {issue['issue'][:80]}"),
            }
            logger.info("Auto-fixed blocking issue in %s: %s", path, issue["issue"][:120])

    merged = _merge_llm_responses(responses) if responses else None
    order = [f["path"] for f in files]
    return [by_path[p] for p in order if p in by_path], merged


def ensure_plan_ready_for_codegen(
    db: Session,
    ctx: PipelineContext,
) -> dict[str, Any]:
    """Enrich and validate plan before code_writer runs (once per pipeline run)."""
    if ctx.additional_context.get("_plan_codegen_ready"):
        plan = ctx.additional_context.get("implementation_plan")
        return plan if isinstance(plan, dict) else {}

    plan = ctx.additional_context.get("implementation_plan")
    if not isinstance(plan, dict):
        plan = {}

    specs = ctx.additional_context.get("spec_documents")
    enriched = enrich_implementation_plan(
        db,
        plan,
        documents=specs if isinstance(specs, dict) else None,
        stack_summary=ctx.project_stack_summary(),
    )
    blockers = validate_plan_for_codegen(enriched)
    if blockers:
        logger.warning("Implementation plan validation warnings: %s", "; ".join(blockers))

    ctx.additional_context["implementation_plan"] = enriched
    ctx.additional_context["_plan_codegen_ready"] = True
    return enriched


def _merge_llm_responses(responses: list[LLMResponse]) -> LLMResponse:
    if not responses:
        return LLMResponse("", None, 0, 0, 0.0, "none", "none")
    if len(responses) == 1:
        return responses[0]
    return LLMResponse(
        content=responses[-1].content,
        parsed_json=responses[-1].parsed_json,
        input_tokens=sum(r.input_tokens for r in responses),
        output_tokens=sum(r.output_tokens for r in responses),
        cost_usd=round(sum(r.cost_usd for r in responses), 6),
        model_name=responses[-1].model_name,
        provider=responses[-1].provider,
    )
