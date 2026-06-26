from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from models.workspace_portal import MemberIntegrationConnection
from models.platform import PlatformIntegration
from services.platform_helpers import split_config_fields
from services.secrets import decrypt_secrets, encrypt_secrets


def get_member_connection(
    db: Session, workspace_id, user_id, platform_integration_id
) -> MemberIntegrationConnection | None:
    return (
        db.query(MemberIntegrationConnection)
        .filter(
            MemberIntegrationConnection.workspace_id == workspace_id,
            MemberIntegrationConnection.user_id == user_id,
            MemberIntegrationConnection.platform_integration_id == platform_integration_id,
        )
        .first()
    )


def member_integration_to_dict(
    integration: PlatformIntegration,
    conn: MemberIntegrationConnection | None,
    *,
    is_granted: bool,
    is_assigned: bool,
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
        "is_assigned": is_assigned,
        "is_connected": bool(conn and conn.status == "connected" and conn.encrypted_config_ref),
        "connection_status": status,
        "connection_name": conn.connection_name if conn else None,
        "config_schema": integration.config_schema_json or {},
        "config_metadata": (conn.config_metadata_json or {}) if conn else {},
        "last_tested_at": conn.last_tested_at if conn else None,
        "last_test_status": conn.last_test_status if conn else None,
        "last_error_message": conn.last_error_message if conn else None,
    }


def save_member_connection(
    db: Session,
    workspace_id,
    user_id,
    integration: PlatformIntegration,
    connection_name: str,
    config: dict[str, Any],
) -> MemberIntegrationConnection:
    secrets, metadata = split_config_fields(integration, config)
    conn = get_member_connection(db, workspace_id, user_id, integration.id)
    if not conn:
        conn = MemberIntegrationConnection(
            workspace_id=workspace_id,
            user_id=user_id,
            platform_integration_id=integration.id,
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
