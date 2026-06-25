"""Teams integration helpers — assignment, connection, display."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session, joinedload

from config import settings
from models.company_portal import MemberIntegrationAccess, MemberIntegrationConnection
from models.platform import CompanyPlatformIntegration, PlatformIntegration
from models.teams import OAuthState, TeamsSyncState
from services.microsoft_graph import (
    TeamsAppConfig,
    build_authorize_url,
    exchange_code_for_tokens,
    fetch_me,
    get_platform_teams_config,
    tokens_from_oauth_response,
    tokens_to_secrets,
)
from services.member_integrations import get_member_connection
from services.secrets import decrypt_secrets, encrypt_secrets


def get_teams_integration(db: Session, company_id) -> PlatformIntegration | None:
    granted_ids = {
        row.platform_integration_id
        for row in db.query(CompanyPlatformIntegration)
        .filter(
            CompanyPlatformIntegration.company_id == company_id,
            CompanyPlatformIntegration.is_enabled.is_(True),
        )
        .all()
    }
    integration = (
        db.query(PlatformIntegration)
        .filter(PlatformIntegration.integration_key == "teams")
        .first()
    )
    if not integration or integration.id not in granted_ids:
        return None
    return integration


def user_has_teams_assigned(db: Session, company_id, user_id) -> bool:
    integration = get_teams_integration(db, company_id)
    if not integration:
        return False
    row = (
        db.query(MemberIntegrationAccess)
        .filter(
            MemberIntegrationAccess.company_id == company_id,
            MemberIntegrationAccess.user_id == user_id,
            MemberIntegrationAccess.platform_integration_id == integration.id,
            MemberIntegrationAccess.is_enabled.is_(True),
        )
        .first()
    )
    return row is not None


def get_teams_connection(db: Session, company_id, user_id) -> MemberIntegrationConnection | None:
    integration = get_teams_integration(db, company_id)
    if not integration:
        return None
    return get_member_connection(db, company_id, user_id, integration.id)


def create_oauth_state(
    db: Session, *, user_id, company_id, redirect_path: str | None = None
) -> str:
    state = uuid4().hex
    db.add(
        OAuthState(
            state=state,
            user_id=user_id,
            company_id=company_id,
            integration_key="teams",
            redirect_path=redirect_path,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    db.commit()
    return state


def consume_oauth_state(db: Session, state: str) -> OAuthState | None:
    row = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not row:
        return None
    if row.expires_at < datetime.now(UTC):
        db.delete(row)
        db.commit()
        return None
    db.delete(row)
    db.commit()
    return row


def save_user_teams_tokens(
    db: Session,
    *,
    company_id,
    user_id,
    integration: PlatformIntegration,
    token_data: dict,
) -> MemberIntegrationConnection:
    tokens = tokens_from_oauth_response(token_data)
    try:
        me = fetch_me(tokens.access_token)
        tokens.microsoft_email = me.get("mail") or me.get("userPrincipalName")
    except Exception:
        pass

    conn = get_member_connection(db, company_id, user_id, integration.id)
    if not conn:
        conn = MemberIntegrationConnection(
            company_id=company_id,
            user_id=user_id,
            platform_integration_id=integration.id,
        )
        db.add(conn)
    conn.encrypted_config_ref = encrypt_secrets(tokens_to_secrets(tokens))
    conn.status = "connected"
    conn.connection_name = "Microsoft Teams"
    conn.config_metadata_json = {
        "microsoft_email": tokens.microsoft_email or "",
        "connected_via": "oauth2",
    }
    conn.last_test_status = True
    conn.last_tested_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)
    return conn


def chat_display_name(chat) -> str:
    if chat.chat_type == "channel" and chat.team_name and chat.channel_name:
        return f"{chat.team_name} / {chat.channel_name}"
    if chat.topic:
        return chat.topic
    if chat.channel_name:
        return chat.channel_name
    return "Teams chat"


def get_last_sync(db: Session, company_id, user_id) -> datetime | None:
    state = (
        db.query(TeamsSyncState)
        .filter(
            TeamsSyncState.company_id == company_id,
            TeamsSyncState.user_id == user_id,
            TeamsSyncState.resource_type == "chats",
        )
        .first()
    )
    return state.last_synced_at if state else None


def connect_teams_mock(db: Session, *, company_id, user_id) -> MemberIntegrationConnection:
    """Mark Teams connected for local demo when Graph OAuth is unavailable."""
    if not settings.teams_mock_mode:
        raise ValueError("Demo connect is only available in development mock mode")
    if not user_has_teams_assigned(db, company_id, user_id):
        raise ValueError("Microsoft Teams has not been assigned to your account")
    integration = get_teams_integration(db, company_id)
    if not integration:
        raise ValueError("Teams integration not available for this company")
    conn = get_member_connection(db, company_id, user_id, integration.id)
    if not conn:
        conn = MemberIntegrationConnection(
            company_id=company_id,
            user_id=user_id,
            platform_integration_id=integration.id,
        )
        db.add(conn)
    conn.encrypted_config_ref = encrypt_secrets({})
    conn.status = "connected"
    conn.connection_name = "Microsoft Teams (demo)"
    conn.config_metadata_json = {
        "microsoft_email": "demo@local.dev",
        "connected_via": "mock",
    }
    conn.last_test_status = True
    conn.last_tested_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)
    return conn


def start_teams_oauth(db: Session, *, user_id, company_id, redirect_path: str) -> tuple[str, TeamsAppConfig]:
    if not user_has_teams_assigned(db, company_id, user_id):
        raise ValueError("Microsoft Teams has not been assigned to your account")
    config = get_platform_teams_config(db)
    if not config:
        raise ValueError("Platform Teams app is not configured. Contact your administrator.")
    state = create_oauth_state(db, user_id=user_id, company_id=company_id, redirect_path=redirect_path)
    return build_authorize_url(config, state), config


def complete_teams_oauth(db: Session, *, state: str, code: str) -> str:
    oauth_row = consume_oauth_state(db, state)
    if not oauth_row:
        raise ValueError("Invalid or expired OAuth state")
    integration = get_teams_integration(db, oauth_row.company_id)
    if not integration:
        raise ValueError("Teams integration not available for this company")
    config = get_platform_teams_config(db)
    if not config:
        raise ValueError("Platform Teams app not configured")
    token_data = exchange_code_for_tokens(config, code)
    save_user_teams_tokens(
        db,
        company_id=oauth_row.company_id,
        user_id=oauth_row.user_id,
        integration=integration,
        token_data=token_data,
    )
    redirect = oauth_row.redirect_path or settings.web_base_url
    return redirect
