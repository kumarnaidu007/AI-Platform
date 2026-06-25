"""Microsoft Teams / Graph API client and OAuth helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session, joinedload

from config import settings
from models.platform import PlatformIntegration
from services.secrets import decrypt_secrets
from services.teams_platform import teams_config_from_env

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TEAMS_SCOPES = [
    "openid",
    "profile",
    "offline_access",
    "User.Read",
    "Chat.Read",
    "Chat.ReadWrite",
    "ChannelMessage.Read.All",
    "Channel.ReadBasic.All",
    "Team.ReadBasic.All",
]


@dataclass
class TeamsAppConfig:
    tenant_id: str
    client_id: str
    client_secret: str


@dataclass
class TeamsUserTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    microsoft_email: str | None = None


def get_platform_teams_config(db: Session) -> TeamsAppConfig | None:
    env_config = teams_config_from_env()
    if env_config:
        return TeamsAppConfig(
            tenant_id=env_config["tenant_id"],
            client_id=env_config["client_id"],
            client_secret=env_config["client_secret"],
        )

    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == "teams")
        .first()
    )
    if not integration or not integration.connections:
        return None
    conn = integration.connections[0]
    if conn.status != "connected" or not conn.encrypted_config_ref:
        return None
    secrets = decrypt_secrets(conn.encrypted_config_ref)
    metadata = conn.config_metadata_json or {}
    tenant_id = str(metadata.get("tenant_id") or secrets.get("tenant_id") or "common")
    client_id = str(secrets.get("client_id") or metadata.get("client_id") or "")
    client_secret = str(secrets.get("client_secret") or "")
    if not client_id or not client_secret:
        return None
    return TeamsAppConfig(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)


def teams_redirect_uri() -> str:
    base = settings.api_public_url.rstrip("/")
    return f"{base}/api/oauth/teams/callback"


def build_authorize_url(config: TeamsAppConfig, state: str) -> str:
    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": teams_redirect_uri(),
        "response_mode": "query",
        "scope": " ".join(TEAMS_SCOPES),
        "state": state,
        "prompt": "select_account",
    }
    tenant = config.tenant_id or "common"
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{urlencode(params)}"


def exchange_code_for_tokens(config: TeamsAppConfig, code: str) -> dict[str, Any]:
    tenant = config.tenant_id or "common"
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "code": code,
        "redirect_uri": teams_redirect_uri(),
        "grant_type": "authorization_code",
        "scope": " ".join(TEAMS_SCOPES),
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, data=data)
        resp.raise_for_status()
        return resp.json()


def refresh_access_token(config: TeamsAppConfig, refresh_token: str) -> dict[str, Any]:
    tenant = config.tenant_id or "common"
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": " ".join(TEAMS_SCOPES),
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, data=data)
        resp.raise_for_status()
        return resp.json()


def tokens_from_oauth_response(data: dict[str, Any]) -> TeamsUserTokens:
    expires_in = int(data.get("expires_in", 3600))
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in - 60)
    return TeamsUserTokens(
        access_token=str(data["access_token"]),
        refresh_token=data.get("refresh_token"),
        expires_at=expires_at,
    )


def tokens_to_secrets(tokens: TeamsUserTokens) -> dict[str, Any]:
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_at": tokens.expires_at.isoformat() if tokens.expires_at else None,
        "microsoft_email": tokens.microsoft_email,
    }


def secrets_to_tokens(secrets: dict[str, Any]) -> TeamsUserTokens | None:
    access = secrets.get("access_token")
    if not access:
        return None
    expires_at = None
    if secrets.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(str(secrets["expires_at"]))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
        except ValueError:
            pass
    return TeamsUserTokens(
        access_token=str(access),
        refresh_token=secrets.get("refresh_token"),
        expires_at=expires_at,
        microsoft_email=secrets.get("microsoft_email"),
    )


def ensure_fresh_tokens(db: Session, config: TeamsAppConfig, secrets: dict[str, Any]) -> dict[str, Any]:
    tokens = secrets_to_tokens(secrets)
    if not tokens:
        return secrets
    if tokens.expires_at and tokens.expires_at > datetime.now(UTC) + timedelta(seconds=30):
        return secrets
    if not tokens.refresh_token:
        return secrets
    refreshed = refresh_access_token(config, tokens.refresh_token)
    new_tokens = tokens_from_oauth_response(refreshed)
    if not new_tokens.refresh_token:
        new_tokens.refresh_token = tokens.refresh_token
    new_tokens.microsoft_email = tokens.microsoft_email
    return tokens_to_secrets(new_tokens)


def _graph_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def graph_get(access_token: str, path: str, params: dict | None = None) -> dict[str, Any]:
    url = path if path.startswith("http") else f"{GRAPH_BASE}{path}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=_graph_headers(access_token), params=params)
        resp.raise_for_status()
        return resp.json()


def graph_post(access_token: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    url = path if path.startswith("http") else f"{GRAPH_BASE}{path}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=_graph_headers(access_token), json=body)
        resp.raise_for_status()
        return resp.json()


def fetch_me(access_token: str) -> dict[str, Any]:
    return graph_get(access_token, "/me")


def fetch_chats(access_token: str) -> list[dict[str, Any]]:
    data = graph_get(access_token, "/me/chats", params={"$top": 50, "$expand": "lastMessagePreview"})
    return data.get("value", [])


def fetch_chat_messages(access_token: str, chat_id: str, top: int = 50) -> list[dict[str, Any]]:
    data = graph_get(
        access_token,
        f"/me/chats/{chat_id}/messages",
        params={"$top": top, "$orderby": "createdDateTime desc"},
    )
    return data.get("value", [])


def fetch_joined_teams(access_token: str) -> list[dict[str, Any]]:
    data = graph_get(access_token, "/me/joinedTeams", params={"$top": 50})
    return data.get("value", [])


def fetch_team_channels(access_token: str, team_id: str) -> list[dict[str, Any]]:
    data = graph_get(access_token, f"/teams/{team_id}/channels", params={"$top": 50})
    return data.get("value", [])


def fetch_channel_messages(access_token: str, team_id: str, channel_id: str, top: int = 50) -> list[dict[str, Any]]:
    data = graph_get(
        access_token,
        f"/teams/{team_id}/channels/{channel_id}/messages",
        params={"$top": top},
    )
    return data.get("value", [])


def send_chat_message(access_token: str, chat_id: str, content: str) -> dict[str, Any]:
    body = {
        "body": {
            "contentType": "text",
            "content": content,
        }
    }
    return graph_post(access_token, f"/me/chats/{chat_id}/messages", body)


def send_channel_message(access_token: str, team_id: str, channel_id: str, content: str) -> dict[str, Any]:
    body = {
        "body": {
            "contentType": "text",
            "content": content,
        }
    }
    return graph_post(access_token, f"/teams/{team_id}/channels/{channel_id}/messages", body)


def parse_message_body(message: dict[str, Any]) -> str:
    body = message.get("body") or {}
    content = body.get("content") or ""
    if body.get("contentType") == "html":
        import re

        text = re.sub(r"<[^>]+>", "", content)
        return text.strip()
    return str(content).strip()


def parse_sender(message: dict[str, Any]) -> tuple[str | None, str | None]:
    from_data = message.get("from") or {}
    user = from_data.get("user") or {}
    return user.get("displayName"), user.get("email") or user.get("userPrincipalName")
