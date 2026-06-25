"""Bootstrap platform-level Microsoft Teams OAuth app from environment."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, joinedload

from config import settings
from models.platform import PlatformConnection, PlatformIntegration
from services.secrets import encrypt_secrets, mask_secret


def teams_config_from_env() -> dict[str, str] | None:
    client_id = (settings.teams_client_id or "").strip()
    client_secret = (settings.teams_client_secret or "").strip()
    if not client_id or not client_secret:
        return None
    tenant_id = (settings.teams_tenant_id or "common").strip() or "common"
    return {
        "tenant_id": tenant_id,
        "client_id": client_id,
        "client_secret": client_secret,
    }


def ensure_teams_platform_config(db: Session) -> bool:
    """Persist Teams Azure app credentials from env into platform_connections."""
    env_config = teams_config_from_env()
    if not env_config:
        return False

    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == "teams")
        .first()
    )
    if not integration:
        return False

    conn = integration.connections[0] if integration.connections else None
    if not conn:
        conn = PlatformConnection(
            platform_integration_id=integration.id,
            connection_name="Microsoft Graph App",
        )
        db.add(conn)

    conn.encrypted_config_ref = encrypt_secrets(
        {
            "client_id": env_config["client_id"],
            "client_secret": env_config["client_secret"],
            "tenant_id": env_config["tenant_id"],
        }
    )
    conn.status = "connected"
    conn.connection_name = "Microsoft Graph App"
    conn.config_metadata_json = {
        "tenant_id": env_config["tenant_id"],
        "client_id": env_config["client_id"],
        "client_secret": mask_secret(env_config["client_secret"]),
        "redirect_uri": f"{settings.api_public_url.rstrip('/')}/api/oauth/teams/callback",
        "source": "environment",
    }
    conn.last_test_status = True
    conn.last_tested_at = datetime.now(UTC)
    conn.last_error_message = None
    integration.is_enabled = True
    integration.updated_at = datetime.now(UTC)
    db.commit()
    return True
