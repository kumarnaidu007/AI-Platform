from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.deps import DbDep
from config import settings
from services.github_service import complete_github_oauth
from services.jira_service import complete_jira_oauth

router = APIRouter(prefix="/api/oauth", tags=["oauth"])


@router.get("/github/callback")
def github_oauth_callback(
    db: DbDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        return RedirectResponse(
            f"{settings.web_base_url}/workspace/integrations/github?github_error={error}",
            status_code=302,
        )
    if not code or not state:
        raise HTTPException(400, "Missing code or state")
    try:
        redirect_path = complete_github_oauth(db, state=state, code=code)
    except ValueError as exc:
        return RedirectResponse(
            f"{settings.web_base_url}/workspace/integrations/github?github_error={str(exc)}",
            status_code=302,
        )
    sep = "&" if "?" in redirect_path else "?"
    return RedirectResponse(f"{redirect_path}{sep}github_connected=1", status_code=302)


@router.get("/jira/callback")
def jira_oauth_callback(
    db: DbDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        return RedirectResponse(
            f"{settings.web_base_url}/workspace/integrations/jira?jira_error={error}",
            status_code=302,
        )
    if not code or not state:
        raise HTTPException(400, "Missing code or state")
    try:
        redirect_path = complete_jira_oauth(db, state=state, code=code)
    except ValueError as exc:
        return RedirectResponse(
            f"{settings.web_base_url}/workspace/integrations/jira?jira_error={str(exc)}",
            status_code=302,
        )
    sep = "&" if "?" in redirect_path else "?"
    return RedirectResponse(f"{redirect_path}{sep}jira_connected=1", status_code=302)
