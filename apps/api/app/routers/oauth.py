from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.deps import DbDep
from config import settings
from models import Company
from services.teams_service import complete_teams_oauth

router = APIRouter(prefix="/api/oauth", tags=["oauth"])


@router.get("/teams/callback")
def teams_oauth_callback(
    db: DbDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        return RedirectResponse(
            f"{settings.web_base_url}?teams_error={error}",
            status_code=302,
        )
    if not code or not state:
        raise HTTPException(400, "Missing code or state")
    try:
        redirect_path = complete_teams_oauth(db, state=state, code=code)
    except ValueError as exc:
        return RedirectResponse(
            f"{settings.web_base_url}?teams_error={str(exc)}",
            status_code=302,
        )
    sep = "&" if "?" in redirect_path else "?"
    return RedirectResponse(f"{redirect_path}{sep}teams_connected=1", status_code=302)
