"""GitHub OAuth and repository API for pipeline agents."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session, joinedload

from config import settings
from models.workspace_portal import MemberIntegrationAccess, MemberIntegrationConnection
from models.platform import WorkspacePlatformIntegration, PlatformIntegration
from services.member_integrations import get_member_connection
from services.oauth_state import consume_oauth_state, create_oauth_state
from services.platform_helpers import _primary_connection, get_oauth_credentials_from_connection
from services.secrets import decrypt_secrets, encrypt_secrets

GITHUB_API = "https://api.github.com"
GITHUB_OAUTH_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_SCOPES = "repo read:user"


@dataclass
class GitHubAppConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass
class RepoRef:
    owner: str
    repo: str
    full_name: str


class GitHubError(RuntimeError):
    pass


def parse_repo_url(url: str) -> RepoRef:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    patterns = [
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+)",
        r"^(?P<owner>[^/]+)/(?P<repo>[^/]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            owner = match.group("owner")
            repo = match.group("repo")
            return RepoRef(owner=owner, repo=repo, full_name=f"{owner}/{repo}")
    raise GitHubError(f"Invalid GitHub repository URL: {url}")


def get_platform_github_config(db: Session) -> GitHubAppConfig | None:
    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == "github")
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
    return GitHubAppConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=f"{redirect_base}/api/oauth/github/callback",
    )


def get_github_integration(db: Session, workspace_id) -> PlatformIntegration | None:
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
        .filter(PlatformIntegration.integration_key == "github")
        .first()
    )
    if not integration or integration.id not in granted_ids:
        return None
    return integration


def user_has_github_assigned(db: Session, workspace_id, user_id) -> bool:
    integration = get_github_integration(db, workspace_id)
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


def get_github_connection(db: Session, workspace_id, user_id) -> MemberIntegrationConnection | None:
    integration = get_github_integration(db, workspace_id)
    if not integration:
        return None
    return get_member_connection(db, workspace_id, user_id, integration.id)


def get_github_access_token(conn: MemberIntegrationConnection | None) -> str:
    if not conn or not conn.encrypted_config_ref:
        raise GitHubError("GitHub is not connected. Connect GitHub under My Integrations.")
    secrets = decrypt_secrets(conn.encrypted_config_ref)
    token = secrets.get("access_token") or secrets.get("personal_access_token")
    if not token:
        raise GitHubError("GitHub access token missing. Reconnect your GitHub account.")
    return token


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _request(method: str, path: str, token: str, **kwargs) -> Any:
    url = path if path.startswith("http") else f"{GITHUB_API}{path}"
    with httpx.Client(timeout=60) as client:
        resp = client.request(method, url, headers=_github_headers(token), **kwargs)
    if resp.status_code >= 400:
        detail = resp.text[:500]
        try:
            detail = resp.json().get("message", detail)
        except Exception:
            pass
        raise GitHubError(f"GitHub API error ({resp.status_code}): {detail}")
    if resp.status_code == 204:
        return None
    return resp.json()


def test_github_token(token: str) -> dict[str, Any]:
    return _request("GET", "/user", token)


def verify_repo_access(token: str, repo_url: str) -> dict[str, Any]:
    ref = parse_repo_url(repo_url)
    repo = _request("GET", f"/repos/{ref.full_name}", token)
    return {
        "owner": ref.owner,
        "repo": ref.repo,
        "full_name": ref.full_name,
        "default_branch": repo.get("default_branch", "main"),
        "private": repo.get("private", False),
        "html_url": repo.get("html_url"),
    }


def list_user_repos(token: str, *, per_page: int = 30) -> list[dict[str, Any]]:
    data = _request("GET", "/user/repos", token, params={"per_page": per_page, "sort": "updated"})
    return [
        {
            "full_name": row["full_name"],
            "html_url": row["html_url"],
            "default_branch": row.get("default_branch", "main"),
            "private": row.get("private", False),
        }
        for row in data
    ]


def list_repo_source_files(
    token: str,
    repo_url: str,
    *,
    max_files: int = 80,
    extensions: set[str] | None = None,
) -> list[tuple[str, str]]:
    repo_ref = parse_repo_url(repo_url)
    repo = _request("GET", f"/repos/{repo_ref.full_name}", token)
    branch = repo.get("default_branch", "main")
    commit = _request("GET", f"/repos/{repo_ref.full_name}/commits/{branch}", token)
    tree_sha = commit["commit"]["tree"]["sha"]
    tree = _request(
        "GET", f"/repos/{repo_ref.full_name}/git/trees/{tree_sha}", token, params={"recursive": "1"}
    )
    paths: list[str] = []
    for item in tree.get("tree", []):
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        if not path or path.startswith(".git/"):
            continue
        if extensions and not any(path.endswith(ext) for ext in extensions):
            continue
        if any(skip in path for skip in ("node_modules/", "dist/", "build/", ".venv/", "__pycache__/")):
            continue
        paths.append(path)
        if len(paths) >= max_files:
            break

    results: list[tuple[str, str]] = []
    for path in paths:
        try:
            content = get_file_content(token, repo_ref, path, branch=branch)
            if content:
                results.append((path, content))
        except GitHubError:
            continue
    return results


def get_file_content(token: str, repo_ref: RepoRef, path: str, *, branch: str = "main") -> str:
    data = _request("GET", f"/repos/{repo_ref.full_name}/contents/{path}", token, params={"ref": branch})
    if isinstance(data, list):
        return ""
    encoding = data.get("encoding")
    raw = data.get("content", "")
    if encoding == "base64" and raw:
        return base64.b64decode(raw).decode("utf-8", errors="replace")
    return str(data.get("content", ""))


def branch_exists(token: str, ref: RepoRef, branch: str) -> bool:
    try:
        _request("GET", f"/repos/{ref.full_name}/git/ref/heads/{branch}", token)
        return True
    except GitHubError:
        return False


def resolve_base_branch(token: str, ref: RepoRef, requirements_text: str, repo_info: dict[str, Any]) -> str:
    match = re.search(r"\bfrom\s+([A-Za-z0-9._/-]+)\s+branch\b", requirements_text, re.I)
    if match:
        candidate = match.group(1).split("/")[-1]
        if branch_exists(token, ref, candidate):
            return candidate
    if branch_exists(token, ref, "develop"):
        return "develop"
    return repo_info.get("default_branch", "main")


def get_branch_sha(token: str, ref: RepoRef, branch: str) -> str:
    data = _request("GET", f"/repos/{ref.full_name}/git/ref/heads/{branch}", token)
    return str(data["object"]["sha"])


def create_branch(token: str, ref: RepoRef, *, base_branch: str, new_branch: str) -> None:
    if branch_exists(token, ref, new_branch):
        raise GitHubError(f"Branch '{new_branch}' already exists")
    sha = get_branch_sha(token, ref, base_branch)
    _request(
        "POST",
        f"/repos/{ref.full_name}/git/refs",
        token,
        json={"ref": f"refs/heads/{new_branch}", "sha": sha},
    )


def upsert_file(
    token: str,
    ref: RepoRef,
    *,
    branch: str,
    path: str,
    content: str,
    message: str,
) -> None:
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    payload: dict[str, Any] = {
        "message": message,
        "content": encoded,
        "branch": branch,
    }
    try:
        existing = _request("GET", f"/repos/{ref.full_name}/contents/{path}", token, params={"ref": branch})
        if isinstance(existing, dict) and existing.get("sha"):
            payload["sha"] = existing["sha"]
    except GitHubError:
        pass
    _request("PUT", f"/repos/{ref.full_name}/contents/{path}", token, json=payload)


def create_pull_request(
    token: str,
    ref: RepoRef,
    *,
    title: str,
    body: str,
    head: str,
    base: str,
) -> dict[str, Any]:
    return _request(
        "POST",
        f"/repos/{ref.full_name}/pulls",
        token,
        json={"title": title, "body": body, "head": head, "base": base},
    )


def get_pull_request_diff(token: str, ref: RepoRef, pull_number: int) -> str:
    with httpx.Client(timeout=60) as client:
        resp = client.get(
            f"{GITHUB_API}/repos/{ref.full_name}/pulls/{pull_number}",
            headers={**_github_headers(token), "Accept": "application/vnd.github.diff"},
        )
    if resp.status_code >= 400:
        raise GitHubError(f"Failed to fetch PR diff: {resp.text[:300]}")
    return resp.text


def extract_pull_number(url: str) -> int | None:
    match = re.search(r"/pull/(\d+)", url)
    return int(match.group(1)) if match else None


def save_user_github_tokens(
    db: Session,
    *,
    workspace_id,
    user_id,
    integration: PlatformIntegration,
    access_token: str,
    profile: dict[str, Any] | None = None,
) -> MemberIntegrationConnection:
    profile = profile or test_github_token(access_token)
    conn = get_member_connection(db, workspace_id, user_id, integration.id)
    if not conn:
        conn = MemberIntegrationConnection(
            workspace_id=workspace_id,
            user_id=user_id,
            platform_integration_id=integration.id,
        )
        db.add(conn)
    conn.encrypted_config_ref = encrypt_secrets({"access_token": access_token})
    conn.status = "connected"
    conn.connection_name = profile.get("login") or "GitHub"
    conn.config_metadata_json = {
        "github_login": profile.get("login", ""),
        "github_name": profile.get("name") or profile.get("login") or "",
        "connected_via": "oauth2",
    }
    conn.last_test_status = True
    conn.last_tested_at = datetime.now(UTC)
    db.commit()
    db.refresh(conn)
    return conn


def build_authorize_url(config: GitHubAppConfig, state: str) -> str:
    params = urlencode(
        {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "scope": GITHUB_SCOPES,
            "state": state,
        }
    )
    return f"{GITHUB_OAUTH_AUTHORIZE}?{params}"


def exchange_code_for_token(config: GitHubAppConfig, code: str) -> str:
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            GITHUB_OAUTH_TOKEN,
            headers={"Accept": "application/json"},
            json={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "redirect_uri": config.redirect_uri,
            },
        )
    if resp.status_code >= 400:
        raise GitHubError(f"GitHub token exchange failed: {resp.text[:300]}")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise GitHubError(data.get("error_description") or "GitHub did not return an access token")
    return token


def start_github_oauth(db: Session, *, user_id, workspace_id, redirect_path: str) -> str:
    if not user_has_github_assigned(db, workspace_id, user_id):
        raise ValueError("GitHub has not been assigned to your account")
    config = get_platform_github_config(db)
    if not config:
        raise ValueError("Platform GitHub OAuth app is not configured. Contact your administrator.")
    state = create_oauth_state(
        db,
        user_id=user_id,
        workspace_id=workspace_id,
        integration_key="github",
        redirect_path=redirect_path,
    )
    return build_authorize_url(config, state)


def complete_github_oauth(db: Session, *, state: str, code: str) -> str:
    oauth = consume_oauth_state(db, state, integration_key="github")
    if not oauth:
        raise ValueError("Invalid or expired OAuth state")
    config = get_platform_github_config(db)
    if not config:
        raise ValueError("Platform GitHub OAuth app is not configured")
    integration = get_github_integration(db, oauth.workspace_id)
    if not integration:
        raise ValueError("GitHub is not granted to this workspace")
    token = exchange_code_for_token(config, code)
    profile = test_github_token(token)
    save_user_github_tokens(
        db,
        workspace_id=oauth.workspace_id,
        user_id=oauth.user_id,
        integration=integration,
        access_token=token,
        profile=profile,
    )
    return oauth.redirect_path or f"{settings.web_base_url}/workspace/integrations/github"


def apply_code_changes(
    token: str,
    repo_url: str,
    *,
    base_branch: str,
    branch_name: str,
    files: list[dict[str, str]],
    pr_title: str,
    pr_body: str,
) -> dict[str, Any]:
    ref = parse_repo_url(repo_url)
    repo_info = verify_repo_access(token, repo_url)
    create_branch(token, ref, base_branch=base_branch, new_branch=branch_name)
    changed_paths: list[str] = []
    for item in files:
        path = item.get("path", "").lstrip("/")
        if not path:
            continue
        upsert_file(
            token,
            ref,
            branch=branch_name,
            path=path,
            content=item.get("content", ""),
            message=item.get("message") or f"feat: update {path}",
        )
        changed_paths.append(path)
    pr = create_pull_request(
        token,
        ref,
        title=pr_title,
        body=pr_body,
        head=branch_name,
        base=base_branch,
    )
    return {
        "title": pr.get("title", pr_title),
        "branch_name": branch_name,
        "base_branch": base_branch,
        "url": pr.get("html_url"),
        "number": pr.get("number"),
        "files_changed": changed_paths,
        "summary": pr_body,
    }
