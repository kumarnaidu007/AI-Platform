"""Resolve platform LLM credentials and complete chat requests."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from config import settings
from models.platform import PlatformService, PlatformSetting
from services.platform_helpers import get_foundry_config_from_service
from services.secrets import decrypt_secrets


class LLMNotConfiguredError(RuntimeError):
    """Raised when no LLM API key is configured on the platform."""


@dataclass
class LLMResponse:
    content: str
    parsed_json: dict[str, Any] | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model_name: str
    provider: str


def _get_setting(db: Session, key: str, default: Any) -> Any:
    row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
    if not row:
        return default
    value = row.value_json
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value if value is not None else default


def _normalize_foundry_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip().rstrip("/")
    if endpoint.endswith("/openai/v1"):
        return endpoint
    if "/openai/" in endpoint:
        return endpoint
    return f"{endpoint}/openai/v1"


def resolve_llm_config(db: Session) -> dict[str, Any]:
    provider = str(_get_setting(db, "default_llm_provider", "azure_foundry")).strip().strip('"')
    service = db.query(PlatformService).filter(PlatformService.service_key == provider).first()
    api_key = ""
    model = "gpt-4o-mini"
    endpoint = ""

    if provider == "azure_foundry":
        foundry = db.query(PlatformService).filter(PlatformService.service_key == "azure_foundry").first()
        config = get_foundry_config_from_service(foundry)
        if config:
            return {
                "provider": "azure_foundry",
                "api_key": config["api_key"],
                "model": config["deployment_name"],
                "endpoint": _normalize_foundry_endpoint(config["endpoint"]),
                "embedding_deployment": config["embedding_deployment"],
            }
        return {"provider": provider, "api_key": "", "model": "", "endpoint": ""}

    if provider == "anthropic":
        model = "claude-sonnet-4-20250514"
        if settings.anthropic_api_key:
            api_key = settings.anthropic_api_key
    elif provider == "openai":
        model = "gpt-4o-mini"
        if settings.openai_api_key:
            api_key = settings.openai_api_key

    if service and service.encrypted_config_ref:
        secrets = decrypt_secrets(service.encrypted_config_ref)
        api_key = secrets.get("api_key") or api_key
        metadata = service.config_metadata_json or {}
        model = metadata.get("default_model") or model

    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "endpoint": endpoint,
    }


def resolve_embedding_config(db: Session) -> dict[str, Any]:
    provider = str(_get_setting(db, "default_llm_provider", "azure_foundry")).strip().strip('"')
    if provider == "azure_foundry":
        foundry = db.query(PlatformService).filter(PlatformService.service_key == "azure_foundry").first()
        config = get_foundry_config_from_service(foundry)
        if config:
            return {
                "provider": "azure_foundry",
                "api_key": config["api_key"],
                "endpoint": _normalize_foundry_endpoint(config["endpoint"]),
                "model": config["embedding_deployment"],
            }
    llm = resolve_llm_config(db)
    return {
        "provider": llm["provider"],
        "api_key": llm["api_key"],
        "endpoint": llm.get("endpoint") or "https://api.openai.com/v1",
        "model": "text-embedding-3-small",
    }


def require_llm_config(db: Session) -> dict[str, Any]:
    config = resolve_llm_config(db)
    if not config["api_key"]:
        provider = config["provider"]
        raise LLMNotConfiguredError(
            f"No API key configured for LLM provider '{provider}'. "
            "Add your credentials under Admin → AI Services and ensure the service is enabled."
        )
    if config["provider"] == "azure_foundry" and not config.get("endpoint"):
        raise LLMNotConfiguredError(
            "Microsoft Foundry endpoint is not configured. "
            "Set the project endpoint under Admin → AI Services → Microsoft Foundry."
        )
    return config


def _repair_truncated_json(text: str) -> dict[str, Any] | None:
    """Best-effort repair when the model hits the output token limit mid-JSON."""
    start = text.find("{")
    if start < 0:
        return None
    fragment = text[start:]
    for _ in range(12):
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            fragment = fragment.rstrip().rstrip(",")
            if fragment.endswith('"'):
                fragment += '"}'
            elif fragment.count('"') % 2 == 1:
                fragment += '"'
            open_braces = fragment.count("{") - fragment.count("}")
            open_brackets = fragment.count("[") - fragment.count("]")
            fragment += "]" * max(open_brackets, 0)
            fragment += "}" * max(open_braces, 0)
    return None


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            repaired = _repair_truncated_json(text)
            if repaired:
                return repaired
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return _repair_truncated_json(match.group())
    return None


def _estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    if provider == "anthropic":
        return round((input_tokens * 3 + output_tokens * 15) / 1_000_000, 6)
    return round((input_tokens * 0.15 + output_tokens * 0.6) / 1_000_000, 6)


def _is_transient_http_error(exc: BaseException) -> bool:
    """True when the LLM call may succeed on retry (network blip, gateway timeout)."""
    if isinstance(exc, (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (408, 429, 500, 502, 503, 504):
        return True
    msg = str(exc).lower()
    return any(
        phrase in msg
        for phrase in (
            "server disconnected",
            "connection reset",
            "connection aborted",
            "broken pipe",
            "temporarily unavailable",
            "rate limit",
        )
    )


def complete_json(
    db: Session,
    *,
    system: str,
    user: str,
    max_completion_tokens: int | None = None,
    retries: int = 2,
) -> LLMResponse:
    config = require_llm_config(db)
    provider = config["provider"]
    model = config["model"]
    api_key = config["api_key"]
    last: LLMResponse | None = None
    prompt = user
    attempts = max(1, retries)

    for attempt in range(attempts):
        try:
            if provider == "azure_foundry":
                last = _call_openai_compatible(
                    api_key,
                    model,
                    system,
                    prompt,
                    base_url=config["endpoint"],
                    provider_label="azure_foundry",
                    use_max_completion_tokens=True,
                    max_completion_tokens=max_completion_tokens or 8192,
                )
            elif provider == "openai":
                last = _call_openai_compatible(
                    api_key,
                    model,
                    system,
                    prompt,
                    base_url="https://api.openai.com/v1",
                    provider_label="openai",
                    max_completion_tokens=max_completion_tokens or 8192,
                )
            else:
                last = _call_anthropic(api_key, model, system, prompt)
        except Exception as exc:
            if _is_transient_http_error(exc) and attempt < attempts - 1:
                time.sleep(min(2 ** attempt * 2, 30))
                continue
            raise

        if last.parsed_json:
            return last
        if attempt < attempts - 1:
            prompt = (
                f"{user}\n\n"
                "Your previous response was not valid JSON. Return a single valid JSON object only. "
                "Do not include markdown fences or commentary."
            )
    return last  # type: ignore[return-value]


def _call_anthropic(api_key: str, model: str, system: str, user: str) -> LLMResponse:
    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    with httpx.Client(timeout=120) as client:
        resp = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    usage = data.get("usage", {})
    input_tokens = int(usage.get("input_tokens", 0))
    output_tokens = int(usage.get("output_tokens", 0))
    return LLMResponse(
        content=text,
        parsed_json=_extract_json(text),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=_estimate_cost("anthropic", model, input_tokens, output_tokens),
        model_name=model,
        provider="anthropic",
    )


def _http_error_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    except Exception:
        pass
    return resp.text[:300]


def _call_openai_compatible(
    api_key: str,
    model: str,
    system: str,
    user: str,
    *,
    base_url: str,
    provider_label: str,
    use_max_completion_tokens: bool = False,
    max_completion_tokens: int = 8192,
) -> LLMResponse:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    if use_max_completion_tokens:
        payload["max_completion_tokens"] = max_completion_tokens
    else:
        payload["max_tokens"] = max_completion_tokens
    url = f"{base_url.rstrip('/')}/chat/completions"
    # Long timeout — Azure Foundry can be slow on large JSON codegen responses.
    timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=30.0)
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"LLM request failed ({resp.status_code}): {_http_error_detail(resp)}")
        data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    input_tokens = int(usage.get("prompt_tokens", 0))
    output_tokens = int(usage.get("completion_tokens", 0))
    return LLMResponse(
        content=text,
        parsed_json=_extract_json(text),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=_estimate_cost(provider_label, model, input_tokens, output_tokens),
        model_name=model,
        provider=provider_label,
    )


def test_foundry_connection(config: dict[str, str]) -> str:
    """Verify Foundry using the same chat/completions path agents use."""
    url = f"{config['endpoint'].rstrip('/')}/chat/completions"
    payload = {
        "model": config["deployment_name"],
        "messages": [
            {"role": "system", "content": "Respond with valid JSON only."},
            {"role": "user", "content": 'Return JSON: {"status":"ok"}'},
        ],
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Foundry test failed ({resp.status_code}): {_http_error_detail(resp)}")
        data = resp.json()
    reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    model = config["deployment_name"]
    return f"Connected to deployment '{model}'" + (f" — model replied: {reply[:40].strip()}" if reply else "")
