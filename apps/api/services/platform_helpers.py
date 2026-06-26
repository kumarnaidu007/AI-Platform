from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from models.platform import PlatformConnection, PlatformIntegration, PlatformService, PlatformSetting
from services.secrets import decrypt_secrets, encrypt_secrets, mask_secret


def get_oauth_credentials_from_connection(
    conn: PlatformConnection | None,
) -> tuple[str | None, str | None]:
    """Read OAuth client_id/client_secret from platform connection storage.

    Non-secret fields (e.g. client_id) are stored in config_metadata_json; secrets
  are encrypted. Both must be merged for OAuth to work.
    """
    if not conn:
        return None, None
    metadata = conn.config_metadata_json or {}
    secrets = decrypt_secrets(conn.encrypted_config_ref) if conn.encrypted_config_ref else {}
    client_id = (
        secrets.get("client_id")
        or secrets.get("clientId")
        or metadata.get("client_id")
        or metadata.get("clientId")
    )
    client_secret = secrets.get("client_secret") or secrets.get("clientSecret")
    if client_id is not None:
        client_id = str(client_id).strip() or None
    if client_secret is not None:
        client_secret = str(client_secret).strip() or None
    return client_id, client_secret


def oauth_credentials_configured(conn: PlatformConnection | None) -> bool:
    client_id, client_secret = get_oauth_credentials_from_connection(conn)
    return bool(client_id and client_secret)


def _primary_connection(integration: PlatformIntegration) -> PlatformConnection | None:
    if not integration.connections:
        return None
    return integration.connections[0]


def integration_connection_status(integration: PlatformIntegration) -> str:
    if not integration.is_enabled:
        return "disabled"
    conn = _primary_connection(integration)
    if not conn:
        return "not_configured"
    return conn.status


def integration_is_assignable(integration: PlatformIntegration) -> bool:
    return integration_connection_status(integration) == "connected"


def service_is_assignable(service: PlatformService) -> bool:
    if not service.is_enabled:
        return False
    if service.service_key == "azure_foundry":
        return foundry_service_configured(service)
    return bool(service.encrypted_config_ref)


def foundry_service_configured(service: PlatformService | None) -> bool:
    if not service or not service.encrypted_config_ref:
        return False
    metadata = service.config_metadata_json or {}
    endpoint = str(metadata.get("endpoint") or metadata.get("base_url") or "").strip()
    deployment = str(metadata.get("deployment_name") or metadata.get("deployment") or "").strip()
    secrets = decrypt_secrets(service.encrypted_config_ref)
    api_key = secrets.get("api_key")
    return bool(api_key and endpoint and deployment)


def get_foundry_config_from_service(service: PlatformService | None) -> dict[str, str] | None:
    if not service or not foundry_service_configured(service):
        return None
    metadata = service.config_metadata_json or {}
    secrets = decrypt_secrets(service.encrypted_config_ref)
    raw_endpoint = str(metadata.get("endpoint") or metadata.get("base_url") or "").strip().rstrip("/")
    endpoint = raw_endpoint
    if endpoint and not endpoint.endswith("/openai/v1"):
        if "/openai/" not in endpoint:
            endpoint = f"{endpoint}/openai/v1"
    deployment = str(metadata.get("deployment_name") or metadata.get("deployment") or "").strip()
    embedding = str(
        metadata.get("embedding_deployment") or metadata.get("embedding_model") or "text-embedding-3-small"
    ).strip()
    return {
        "api_key": str(secrets.get("api_key") or ""),
        "endpoint": endpoint,
        "deployment_name": deployment,
        "embedding_deployment": embedding,
    }


def integration_to_dict(integration: PlatformIntegration) -> dict[str, Any]:
    conn = _primary_connection(integration)
    status = integration_connection_status(integration)

    metadata: dict[str, Any] = {}
    if conn and conn.config_metadata_json:
        metadata = dict(conn.config_metadata_json)

    return {
        "id": integration.id,
        "integration_key": integration.integration_key,
        "name": integration.name,
        "description": integration.description,
        "category": integration.category,
        "auth_type": integration.auth_type,
        "is_enabled": integration.is_enabled,
        "config_schema": integration.config_schema_json or {},
        "documentation_url": integration.documentation_url,
        "connection_status": status,
        "connection_name": conn.connection_name if conn else None,
        "last_tested_at": conn.last_tested_at if conn else None,
        "last_test_status": conn.last_test_status if conn else None,
        "last_error_message": conn.last_error_message if conn else None,
        "config_metadata": metadata,
    }


def split_config_fields(
    integration: PlatformIntegration, config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    schema_fields = (integration.config_schema_json or {}).get("fields", [])
    secret_keys = {f["key"] for f in schema_fields if f.get("type") == "secret"}
    secrets = {k: v for k, v in config.items() if k in secret_keys and v}
    metadata = {k: v for k, v in config.items() if k not in secret_keys}
    for k, v in config.items():
        if k in secret_keys and v:
            metadata[k] = mask_secret(str(v))
    return secrets, metadata


def save_connection(
    db: Session, integration: PlatformIntegration, connection_name: str, config: dict[str, Any]
) -> PlatformConnection:
    secrets, metadata = split_config_fields(integration, config)
    conn = _primary_connection(integration)
    if not conn:
        conn = PlatformConnection(
            platform_integration_id=integration.id,
            connection_name=connection_name,
        )
        db.add(conn)
    else:
        conn.connection_name = connection_name

    if secrets:
        existing = decrypt_secrets(conn.encrypted_config_ref) if conn.encrypted_config_ref else {}
        existing.update(secrets)
        conn.encrypted_config_ref = encrypt_secrets(existing)
        conn.status = "connected"
    conn.config_metadata_json = metadata
    conn.updated_at = datetime.now(UTC)
    integration.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)
    return conn


def service_to_dict(service: PlatformService) -> dict[str, Any]:
    configured = foundry_service_configured(service) if service.service_key == "azure_foundry" else bool(
        service.encrypted_config_ref
    )
    return {
        "id": service.id,
        "service_key": service.service_key,
        "display_name": service.display_name,
        "description": service.description,
        "is_enabled": service.is_enabled,
        "is_configured": configured,
        "config_metadata": service.config_metadata_json or {},
        "last_tested_at": service.last_tested_at,
        "last_test_status": service.last_test_status,
        "last_error_message": service.last_error_message,
    }


SETTING_LABELS: dict[str, tuple[str, str]] = {
    "platform_name": ("Platform Name", "string"),
    "default_llm_provider": ("Default LLM Provider", "string"),
    "oauth_redirect_base_url": ("OAuth Redirect Base URL", "string"),
    "max_agent_retries": ("Max Agent Retries", "number"),
    "allow_byodb": ("Allow BYODB", "boolean"),
    "maintenance_mode": ("Maintenance Mode", "boolean"),
}


def setting_to_dict(setting: PlatformSetting) -> dict[str, Any]:
    label, typ = SETTING_LABELS.get(setting.key, (setting.key.replace("_", " ").title(), "string"))
    value = setting.value_json
    if typ == "boolean":
        if isinstance(value, bool):
            pass
        elif isinstance(value, str):
            value = value.lower() == "true"
        else:
            value = bool(value)
    elif typ == "number" and not isinstance(value, (int, float)):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 0
    elif isinstance(value, str):
        value = value.strip('"')
    return {
        "key": setting.key,
        "label": label,
        "description": setting.description,
        "type": typ,
        "value": value,
    }
