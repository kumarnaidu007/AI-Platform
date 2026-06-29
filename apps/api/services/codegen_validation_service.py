"""Deterministic validation for generated code — no LLM required."""

from __future__ import annotations

import json
import re
from typing import Any

from agents.context import PipelineContext

# Patterns that indicate non-compilable / fragile generated C#
_REFLECTION_IN_CONTROLLER = re.compile(r"GetType\(\)\.GetMethod|\.Invoke\(", re.IGNORECASE)
_INTERFACE_IMPL = re.compile(r":\s*ICountriesStore\b|implements\s+ICountriesStore\b", re.IGNORECASE)
_PUBLIC_INTERFACE = re.compile(
    r"public\s+interface\s+ICountriesStore\b",
    re.IGNORECASE,
)
_ASYNC_STORE_METHODS = (
    "EnsureLoadedAsync",
    "GetAllAsync",
    "GetByCodeAsync",
    "CountAsync",
    "LoadAsync",
)
_DTO_PASCAL = re.compile(
    r"public\s+(string\s+)?Code\s*\{",
    re.IGNORECASE,
)
_LOWERCASE_FIELD_BUG = re.compile(r"\b(code|name)\s*=\s*[^;]+;|\.(code|name)\b", re.IGNORECASE)


def _files_by_path(files: list[dict[str, str]]) -> dict[str, str]:
    return {f["path"]: f.get("content", "") for f in files if f.get("path")}


def _json_root_issues(path: str, content: str, plan: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    contracts = (plan.get("technical_contracts") or {}).get("json_resources") or []
    spec = next((r for r in contracts if isinstance(r, dict) and r.get("file") == path), None)

    # Strip block comments for JSON parse attempt (common LLM mistake)
    stripped = content.strip()
    if stripped.startswith("/*"):
        brace = stripped.find("{")
        if brace >= 0:
            stripped = stripped[brace:]

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        issues.append({"file": path, "issue": f"Invalid JSON: {exc}"})
        return issues

    root_key = (spec or {}).get("root_key")
    if root_key and isinstance(data, dict):
        if root_key not in data:
            issues.append(
                {
                    "file": path,
                    "issue": f"JSON must have root key '{root_key}' (object wrapper, not bare array)",
                }
            )
        items = data.get(root_key)
        if items is not None and not isinstance(items, list):
            issues.append({"file": path, "issue": f"Key '{root_key}' must be an array"})
    elif isinstance(data, list) and root_key:
        issues.append(
            {
                "file": path,
                "issue": f"JSON must be object with '{root_key}' array per plan contract, not bare array",
            }
        )
    return issues


def _csharp_cross_file_issues(files_by_path: dict[str, str], plan: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    interface_content = ""
    for path, content in files_by_path.items():
        if path.endswith("ICountriesStore.cs"):
            interface_content = content
            break

    store_path = next((p for p in files_by_path if p.endswith("CountriesStore.cs")), None)
    controller_path = next((p for p in files_by_path if p.endswith("CountriesController.cs")), None)

    if interface_content and store_path:
        store_content = files_by_path[store_path]
        if not _INTERFACE_IMPL.search(store_content):
            issues.append(
                {
                    "file": store_path,
                    "issue": "CountriesStore must implement ICountriesStore (add ': ICountriesStore' to class declaration)",
                }
            )
        for method in _ASYNC_STORE_METHODS:
            if method in interface_content and method not in store_content:
                issues.append(
                    {
                        "file": store_path,
                        "issue": f"CountriesStore must implement {method} declared on ICountriesStore",
                    }
                )

    if controller_path:
        ctrl = files_by_path[controller_path]
        if _REFLECTION_IN_CONTROLLER.search(ctrl):
            issues.append(
                {
                    "file": controller_path,
                    "issue": "Controller must call ICountriesStore methods directly — remove reflection (GetType/GetMethod/Invoke)",
                }
            )
        if "GetAll()" in ctrl and "GetAllAsync" in interface_content:
            issues.append(
                {
                    "file": controller_path,
                    "issue": "Controller must use await _store.GetAllAsync(...) not sync GetAll()",
                }
            )
        if "TryGetByCode" in ctrl and "GetByCodeAsync" in interface_content:
            issues.append(
                {
                    "file": controller_path,
                    "issue": "Controller must use await _store.GetByCodeAsync(...) not TryGetByCode/GetByCode",
                }
            )
        if ".name" in ctrl or "c.name" in ctrl.lower():
            issues.append(
                {
                    "file": controller_path,
                    "issue": "Use DTO property 'Name' (PascalCase), not lowercase 'name'",
                }
            )

    dto_path = next((p for p in files_by_path if p.endswith("CountryResponseMinimal.cs")), None)
    if dto_path:
        dto = files_by_path[dto_path]
        if not _DTO_PASCAL.search(dto):
            issues.append(
                {
                    "file": dto_path,
                    "issue": "CountryResponseMinimal must expose PascalCase properties Code and Name with [JsonPropertyName]",
                }
            )

    if store_path:
        store = files_by_path[store_path]
        json_path = next((p for p in files_by_path if p.endswith("countries.json")), None)
        if json_path:
            json_issues = _json_root_issues(json_path, files_by_path[json_path], plan)
            if json_issues:
                for ji in json_issues:
                    issues.append(ji)
                if 'RootElement.ValueKind != JsonValueKind.Array' in store:
                    issues.append(
                        {
                            "file": store_path,
                            "issue": "CountriesStore must load JSON object with 'countries' array, not expect root array",
                        }
                    )
                if "Deserialize<List<" in store and '"countries"' in files_by_path.get(json_path, ""):
                    issues.append(
                        {
                            "file": store_path,
                            "issue": "Deserialize wrapper object and read .countries array, not List<> at root",
                        }
                    )

        if _LOWERCASE_FIELD_BUG.search(store) and "CountryResponseMinimal" in store:
            if re.search(r"\bcode\s*=", store) or re.search(r"\.code\b", store):
                issues.append(
                    {
                        "file": store_path,
                        "issue": "Use DTO properties Code and Name (PascalCase), not lowercase code/name fields",
                    }
                )

    return issues


def validate_pending_publish(
    ctx: PipelineContext,
    files: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Return blocking issues found by deterministic rules (no LLM)."""
    plan = ctx.additional_context.get("implementation_plan") or {}
    if not isinstance(plan, dict):
        plan = {}

    by_path = _files_by_path(files)
    issues: list[dict[str, str]] = []

    for path, content in by_path.items():
        if path.endswith(".json"):
            issues.extend(_json_root_issues(path, content, plan))

    issues.extend(_csharp_cross_file_issues(by_path, plan))

    # Deduplicate by file+issue
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in issues:
        key = f"{item['file']}::{item['issue']}"
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def paths_from_issues(issues: list[dict[str, str]]) -> list[str]:
    return list(dict.fromkeys(i["file"] for i in issues if i.get("file")))


def generation_priority(path: str) -> tuple[int, str]:
    """Lower sorts first — contracts before dependents."""
    p = path.replace("\\", "/").lower()
    if p.endswith(".json"):
        return (0, path)
    if "/models/" in p or p.endswith("icountriesstore.cs"):
        return (1, path)
    if "/services/" in p and "icountries" not in p.lower():
        return (2, path)
    if "/helpers/" in p or "/extensions/" in p or "/middleware/" in p:
        return (3, path)
    if "/controllers/" in p:
        return (4, path)
    if p.endswith("program.cs") or p.endswith(".csproj"):
        return (5, path)
    if p.endswith("readme.md") or p.endswith("appsettings.json"):
        return (9, path)
    return (6, path)


def sort_entries_for_generation(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(entries, key=lambda e: generation_priority(e.get("path", "")))


def should_skip_rag_indexing(ctx: PipelineContext) -> bool:
    """Planned intake runs already have specs — skip expensive repo indexing."""
    if ctx.additional_context.get("skip_planning") and ctx.additional_context.get("implementation_plan"):
        return True
    if ctx.additional_context.get("intake_id") and ctx.additional_context.get("implementation_plan"):
        return True
    return False


def should_skip_llm_review(ctx: PipelineContext) -> bool:
    """Intake implementation: human reviews at PR approval — deterministic check is enough."""
    return bool(ctx.additional_context.get("intake_id"))


def expand_regen_dependents(paths: set[str], all_paths: list[str]) -> set[str]:
    """When one contract file is wrong, regenerate tightly coupled dependents."""
    expanded = set(paths)
    lower_map = {p: p.replace("\\", "/").lower() for p in all_paths}

    def has_fragment(fragment: str) -> bool:
        return any(fragment in lower_map[p] for p in paths)

    if has_fragment("countries.json"):
        for p in all_paths:
            lp = lower_map[p]
            if "countriesstore" in lp or "icountriesstore" in lp:
                expanded.add(p)

    if has_fragment("icountriesstore"):
        for p in all_paths:
            if "countriesstore" in lower_map[p]:
                expanded.add(p)

    if has_fragment("countriesstore"):
        for p in all_paths:
            lp = lower_map[p]
            if "countriescontroller" in lp or "countryresponseminimal" in lp:
                expanded.add(p)

    return expanded


def file_specific_rules(path: str) -> str:
    """Hard rules injected per file type to prevent recurring LLM mistakes."""
    lp = path.replace("\\", "/").lower()
    rules: list[str] = []
    if lp.endswith("countries.json"):
        rules.append(
            "JSON MUST be a valid object with a 'countries' array: "
            '{"countries": [{"code": "US", "name": "United States"}, ...]}. '
            "No comments, no bare array root, no wrapper metadata keys."
        )
    if lp.endswith("icountriesstore.cs"):
        rules.append(
            "Declare async methods: EnsureLoadedAsync, GetAllAsync(int page, int size, ...), "
            "GetByCodeAsync(string code, ...), CountAsync. Use Task<> return types."
        )
    if lp.endswith("countriesstore.cs"):
        rules.append(
            "Class MUST declare ': ICountriesStore' and implement every interface method. "
            "Load JSON object root key 'countries' (not a bare array). "
            "Use CountryResponseMinimal with PascalCase Code and Name properties."
        )
    if lp.endswith("countryresponseminimal.cs"):
        rules.append(
            "Use PascalCase properties Code and Name with [JsonPropertyName(\"code\")] and "
            '[JsonPropertyName("name")]. No lowercase field names.'
        )
    if lp.endswith("countriescontroller.cs"):
        rules.append(
            "Inject ICountriesStore only. Call await _store.GetAllAsync(...) and "
            "await _store.GetByCodeAsync(...). NEVER use reflection (GetType/GetMethod/Invoke). "
            "Reference c.Name not c.name."
        )
    return "\n".join(rules)
