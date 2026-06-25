from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from models.company_portal import CompanyIntegrationConnection
from models.platform import PlatformIntegration
from services.platform_helpers import split_config_fields
from services.secrets import decrypt_secrets, encrypt_secrets


def get_company_connection(
    db: Session, company_id, platform_integration_id
) -> CompanyIntegrationConnection | None:
    return (
        db.query(CompanyIntegrationConnection)
        .filter(
            CompanyIntegrationConnection.company_id == company_id,
            CompanyIntegrationConnection.platform_integration_id == platform_integration_id,
        )
        .first()
    )


def company_integration_to_dict(
    integration: PlatformIntegration,
    conn: CompanyIntegrationConnection | None,
    *,
    is_granted: bool,
) -> dict[str, Any]:
    status = "not_configured"
    if conn:
        status = conn.status
    return {
        "integration_key": integration.integration_key,
        "name": integration.name,
        "description": integration.description,
        "category": integration.category,
        "auth_type": integration.auth_type,
        "is_granted": is_granted,
        "is_connected": bool(conn and conn.status == "connected" and conn.encrypted_config_ref),
        "connection_status": status,
        "connection_name": conn.connection_name if conn else None,
        "config_schema": integration.config_schema_json or {},
        "config_metadata": (conn.config_metadata_json or {}) if conn else {},
        "last_tested_at": conn.last_tested_at if conn else None,
        "last_test_status": conn.last_test_status if conn else None,
        "last_error_message": conn.last_error_message if conn else None,
    }


def save_company_connection(
    db: Session,
    company_id,
    integration: PlatformIntegration,
    user_id,
    connection_name: str,
    config: dict[str, Any],
) -> CompanyIntegrationConnection:
    secrets, metadata = split_config_fields(integration, config)
    conn = get_company_connection(db, company_id, integration.id)
    if not conn:
        conn = CompanyIntegrationConnection(
            company_id=company_id,
            platform_integration_id=integration.id,
            created_by_user_id=user_id,
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
    db.commit()
    db.refresh(conn)
    return conn
