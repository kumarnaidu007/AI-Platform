"""Jira OAuth and REST API for pipeline agents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session, joinedload

from config import settings
from models.platform import PlatformIntegration, WorkspacePlatformIntegration
from models.workspace_portal import MemberIntegrationAccess, MemberIntegrationConnection
from services.member_integrations import get_member_connection
from services.oauth_state import consume_oauth_state, create_oauth_state
from services.platform_helpers import _primary_connection, get_oauth_credentials_from_connection
from services.secrets import decrypt_secrets, encrypt_secrets

ATLASSIAN_AUTHORIZE = "https://auth.atlassian.com/authorize"
ATLASSIAN_TOKEN = "https://auth.atlassian.com/oauth/token"
ATLASSIAN_RESOURCES = "https://api.atlassian.com/oauth/token/accessible-resources"
JIRA_SCOPES = "read:jira-work write:jira-work read:jira-user offline_access"


@dataclass
class JiraAppConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


class JiraError(RuntimeError):
    pass


def get_platform_jira_config(db: Session) -> JiraAppConfig | None:
    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == "jira")
        .first()
    )
    if not integration:
        return None
    conn = _primary_connection(integration)
    if not conn or not conn.encrypted_config_ref:
        return None
    client_id, client_secret = get_oauth_credentials_from_connection(conn)
    if not client_id or not client_secret:
        return None
    redirect_base = settings.api_public_url.rstrip("/")
    return JiraAppConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=f"{redirect_base}/api/oauth/jira/callback",
    )


def get_jira_integration(db: Session, workspace_id) -> PlatformIntegration | None:
    granted_ids = {
        row.platform_integration_id
        for row in db.query(WorkspacePlatformIntegration)
        .filter(
            WorkspacePlatformIntegration.workspace_id == workspace_id,
            WorkspacePlatformIntegration.is_enabled.is_(True),
        )
        .all()
    }
    integration = (
        db.query(PlatformIntegration)
        .filter(PlatformIntegration.integration_key == "jira")
        .first()
    )
    if not integration or integration.id not in granted_ids:
        return None
    return integration


def user_has_jira_assigned(db: Session, workspace_id, user_id) -> bool:
    integration = get_jira_integration(db, workspace_id)
    if not integration:
        return False
    row = (
        db.query(MemberIntegrationAccess)
        .filter(
            MemberIntegrationAccess.workspace_id == workspace_id,
            MemberIntegrationAccess.user_id == user_id,
            MemberIntegrationAccess.platform_integration_id == integration.id,
            MemberIntegrationAccess.is_enabled.is_(True),
        )
        .first()
    )
    return row is not None


def get_jira_connection(db: Session, workspace_id, user_id) -> MemberIntegrationConnection | None:
    integration = get_jira_integration(db, workspace_id)
    if not integration:
        return None
    return get_member_connection(db, workspace_id, user_id, integration.id)


def get_jira_tokens(conn: MemberIntegrationConnection | None) -> dict[str, str]:
    if not conn or not conn.encrypted_config_ref:
        raise JiraError("Jira is not connected. Connect Jira under My Integrations.")
    secrets = decrypt_secrets(conn.encrypted_config_ref)
    access_token = secrets.get("access_token")
    cloud_id = secrets.get("cloud_id")
    if not access_token or not cloud_id:
        raise JiraError("Jira access token missing. Reconnect your Jira account.")
    return {"access_token": access_token, "cloud_id": cloud_id}


def _jira_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _request(method: str, url: str, token: str, **kwargs) -> Any:
    with httpx.Client(timeout=60) as client:
        resp = client.request(method, url, headers=_jira_headers(token), **kwargs)
    if resp.status_code >= 400:
        detail = resp.text[:500]
        try:
            detail = resp.json().get("message", detail)
        except Exception:
            pass
        raise JiraError(f"Jira API error ({resp.status_code}): {detail}")
    if resp.status_code == 204:
        return None
    return resp.json()


def fetch_accessible_resource(access_token: str) -> dict[str, Any]:
    with httpx.Client(timeout=30) as client:
        resp = client.get(ATLASSIAN_RESOURCES, headers=_jira_headers(access_token))
    if resp.status_code >= 400:
        raise JiraError(f"Failed to fetch Jira sites: {resp.text[:300]}")
    resources = resp.json()
    if not resources:
        raise JiraError("No accessible Jira Cloud sites found for this account")
    return resources[0]


def test_jira_token(access_token: str, cloud_id: str) -> dict[str, Any]:
    url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/myself"
    return _request("GET", url, access_token)


def list_projects(token: str, cloud_id: str, *, max_results: int = 30) -> list[dict[str, Any]]:
    url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/project/search"
    data = _request("GET", url, token, params={"maxResults": max_results})
    return [
        {
            "id": row.get("id"),
            "key": row.get("key"),
            "name": row.get("name"),
        }
        for row in data.get("values", [])
    ]


def _adf_to_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(filter(None, (_adf_to_text(item) for item in node)))
    if not isinstance(node, dict):
        return str(node)
    node_type = node.get("type")
    if node_type == "text":
        return str(node.get("text", ""))
    if node_type == "hardBreak":
        return "\n"
    content = node.get("content")
    if content:
        joined = _adf_to_text(content)
        if node_type in ("paragraph", "heading", "listItem"):
            return joined + "\n"
        return joined
    return ""


def _normalize_issue(raw: dict[str, Any], *, site_url: str | None = None) -> dict[str, Any]:
    fields = raw.get("fields") or {}
    description = fields.get("description")
    if isinstance(description, dict):
        description_text = _adf_to_text(description).strip()
    else:
        description_text = str(description or "").strip()
    issue_type = (fields.get("issuetype") or {}).get("name")
    status = (fields.get("status") or {}).get("name")
    priority = (fields.get("priority") or {}).get("name")
    assignee = (fields.get("assignee") or {}).get("displayName")
    reporter = (fields.get("reporter") or {}).get("displayName")
    project = fields.get("project") or {}
    key = raw.get("key") or ""
    base = (site_url or "").rstrip("/")
    return {
        "id": raw.get("id"),
        "key": key,
        "summary": fields.get("summary") or "",
        "description": description_text,
        "issue_type": issue_type,
        "status": status,
        "priority": priority,
        "assignee": assignee,
        "reporter": reporter,
        "project_key": project.get("key"),
        "project_name": project.get("name"),
        "url": f"{base}/browse/{key}" if base and key else None,
    }


def search_issues(
    token: str,
    cloud_id: str,
    *,
    project_key: str | None = None,
    jql: str | None = None,
    max_results: int = 30,
    site_url: str | None = None,
) -> list[dict[str, Any]]:
    if jql:
        query = jql
    elif project_key:
        query = (
            f'project = "{project_key}" AND assignee = currentUser() '
            f'AND statusCategory != Done ORDER BY updated DESC'
        )
    else:
        query = "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC"
    url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/search"
    data = _request(
        "POST",
        url,
        token,
        json={
            "jql": query,
            "maxResults": max_results,
            "fields": ["summary", "status", "priority", "issuetype", "assignee", "project", "updated"],
        },
    )
    return [_normalize_issue(row, site_url=site_url) for row in data.get("issues", [])]


def get_issue(
    token: str,
    cloud_id: str,
    issue_key: str,
    *,
    site_url: str | None = None,
) -> dict[str, Any]:
    url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/issue/{issue_key}"
    data = _request(
        "GET",
        url,
        token,
        params={"fields": "summary,description,status,priority,issuetype,assignee,reporter,project"},
    )
    return _normalize_issue(data, site_url=site_url)


def build_requirements_from_issue(issue: dict[str, Any], user_prompt: str = "") -> str:
    parts = [
        f"Jira ticket: {issue.get('key')} — {issue.get('summary', '')}",
        f"Type: {issue.get('issue_type') or 'Task'}",
        f"Status: {issue.get('status') or 'Unknown'}",
    ]
    if issue.get("priority"):
        parts.append(f"Priority: {issue['priority']}")
    if issue.get("description"):
        parts.append(f"Description:\n{issue['description']}")
    prompt = (user_prompt or "").strip()
    if prompt:
        parts.append(f"Additional instructions from developer:\n{prompt}")
    return "\n\n".join(parts)


def _adf_paragraph(text: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text[:32000]}],
            }
        ],
    }


def add_issue_comment(token: str, cloud_id: str, issue_key: str, body: str) -> dict[str, Any]:
    url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/issue/{issue_key}/comment"
    return _request("POST", url, token, json={"body": _adf_paragraph(body)})


def add_issue_remote_link(
    token: str,
    cloud_id: str,
    issue_key: str,
    *,
    title: str,
    url: str,
) -> dict[str, Any]:
    api_url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/issue/{issue_key}/remotelink"
    return _request(
        "POST",
        api_url,
        token,
        json={
            "object": {"url": url, "title": title},
            "relationship": "mentioned in",
        },
    )


def notify_jira_pr_created(
    db: Session,
    *,
    workspace_id,
    user_id,
    issue_key: str,
    pr_title: str,
    pr_url: str,
    summary: str | None = None,
) -> None:
    conn = get_jira_connection(db, workspace_id, user_id)
    if not conn:
        return
    tokens = get_jira_tokens(conn)
    body = f"AI pipeline opened a pull request: {pr_title}\n{pr_url}"
    if summary:
        body += f"\n\nSummary:\n{summary[:2000]}"
    add_issue_comment(tokens["access_token"], tokens["cloud_id"], issue_key, body)
    add_issue_remote_link(
        tokens["access_token"],
        tokens["cloud_id"],
        issue_key,
        title=pr_title,
        url=pr_url,
    )


def save_user_jira_tokens(
    db: Session,
    *,
    workspace_id,
    user_id,
    integration: PlatformIntegration,
    access_token: str,
    refresh_token: str | None = None,
    resource: dict[str, Any] | None = None,
) -> MemberIntegrationConnection:
    resource = resource or fetch_accessible_resource(access_token)
    cloud_id = resource.get("id", "")
    profile = test_jira_token(access_token, cloud_id)
    conn = get_member_connection(db, workspace_id, user_id, integration.id)
    if not conn:
        conn = MemberIntegrationConnection(
            workspace_id=workspace_id,
            user_id=user_id,
            platform_integration_id=integration.id,
        )
        db.add(conn)
    payload: dict[str, str] = {"access_token": access_token, "cloud_id": cloud_id}
    if refresh_token:
        payload["refresh_token"] = refresh_token
    conn.encrypted_config_ref = encrypt_secrets(payload)
    conn.status = "connected"
    conn.connection_name = resource.get("name") or profile.get("displayName") or "Jira"
    conn.config_metadata_json = {
        "jira_site_name": resource.get("name", ""),
        "jira_site_url": resource.get("url", ""),
        "jira_account_id": profile.get("accountId", ""),
        "jira_display_name": profile.get("displayName", ""),
        "connected_via": "oauth2",
    }
    conn.last_test_status = True
    conn.last_tested_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)
    return conn


def build_authorize_url(config: JiraAppConfig, state: str) -> str:
    params = urlencode(
        {
            "audience": "api.atlassian.com",
            "client_id": config.client_id,
            "scope": JIRA_SCOPES,
            "redirect_uri": config.redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
    )
    return f"{ATLASSIAN_AUTHORIZE}?{params}"


def exchange_code_for_tokens(config: JiraAppConfig, code: str) -> dict[str, str]:
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            ATLASSIAN_TOKEN,
            json={
                "grant_type": "authorization_code",
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "redirect_uri": config.redirect_uri,
            },
            headers={"Content-Type": "application/json"},
        )
    if resp.status_code >= 400:
        raise JiraError(f"Jira token exchange failed: {resp.text[:300]}")
    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise JiraError(data.get("error_description") or "Jira did not return an access token")
    return {
        "access_token": access_token,
        "refresh_token": data.get("refresh_token", ""),
    }


def start_jira_oauth(db: Session, *, user_id, workspace_id, redirect_path: str) -> str:
    if not user_has_jira_assigned(db, workspace_id, user_id):
        raise ValueError("Jira has not been assigned to your account")
    config = get_platform_jira_config(db)
    if not config:
        raise ValueError("Platform Jira OAuth app is not configured. Contact your administrator.")
    state = create_oauth_state(
        db,
        user_id=user_id,
        workspace_id=workspace_id,
        integration_key="jira",
        redirect_path=redirect_path,
    )
    return build_authorize_url(config, state)


def complete_jira_oauth(db: Session, *, state: str, code: str) -> str:
    oauth = consume_oauth_state(db, state, integration_key="jira")
    if not oauth:
        raise ValueError("Invalid or expired OAuth state")
    config = get_platform_jira_config(db)
    if not config:
        raise ValueError("Platform Jira OAuth app is not configured")
    integration = get_jira_integration(db, oauth.workspace_id)
    if not integration:
        raise ValueError("Jira is not granted to this workspace")
    tokens = exchange_code_for_tokens(config, code)
    save_user_jira_tokens(
        db,
        workspace_id=oauth.workspace_id,
        user_id=oauth.user_id,
        integration=integration,
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token") or None,
    )
    return oauth.redirect_path or f"{settings.web_base_url}/workspace/integrations/jira"
