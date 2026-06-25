from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.deps import CompanyAuthDep, CompanyWriterDep, DbDep
from models import User
from models.teams import TeamsChat, TeamsMessage
from schemas.teams import (
    TeamsChatItem,
    TeamsConnectionStatus,
    TeamsMessageItem,
    TeamsOAuthStartResponse,
    TeamsSendMessageRequest,
    TeamsSyncResponse,
)
from services.microsoft_graph import (
    ensure_fresh_tokens,
    get_platform_teams_config,
    send_channel_message,
    send_chat_message,
    secrets_to_tokens,
    tokens_to_secrets,
)
from services.secrets import decrypt_secrets, encrypt_secrets
from services.teams_service import (
    chat_display_name,
    connect_teams_mock,
    get_last_sync,
    get_teams_connection,
    get_teams_integration,
    start_teams_oauth,
    user_has_teams_assigned,
)
from config import settings
from services.teams_sync import sync_mock_data, sync_teams_for_user

router = APIRouter(prefix="/api/company/teams", tags=["company-teams"])


def _require_teams_access(db: Session, ctx: CompanyAuthDep):
    if not user_has_teams_assigned(db, ctx.company_id, ctx.user.id):
        raise HTTPException(403, "Microsoft Teams has not been assigned to your account")
    integration = get_teams_integration(db, ctx.company_id)
    if not integration:
        raise HTTPException(403, "Teams is not granted to your company")
    return integration


def _is_mock_connection(conn) -> bool:
    return (conn.config_metadata_json or {}).get("connected_via") == "mock"


def _is_teams_connected(conn, tokens) -> bool:
    if not conn or conn.status != "connected":
        return False
    if tokens:
        return True
    return settings.teams_mock_mode and _is_mock_connection(conn)


def _run_teams_sync(db: Session, *, company_id, user_id, conn) -> tuple[int, int]:
    config = get_platform_teams_config(db)
    if config:
        return sync_teams_for_user(
            db,
            company_id=company_id,
            user_id=user_id,
            conn=conn,
            config=config,
        )
    if settings.teams_mock_mode and _is_mock_connection(conn):
        return sync_mock_data(db, company_id, user_id)
    raise ValueError("Platform Teams app not configured")


@router.get("/status", response_model=TeamsConnectionStatus)
def teams_status(ctx: CompanyAuthDep, db: DbDep):
    assigned = user_has_teams_assigned(db, ctx.company_id, ctx.user.id)
    conn = get_teams_connection(db, ctx.company_id, ctx.user.id)
    platform_config = get_platform_teams_config(db)
    secrets = decrypt_secrets(conn.encrypted_config_ref) if conn and conn.encrypted_config_ref else {}
    tokens = secrets_to_tokens(secrets)
    return TeamsConnectionStatus(
        is_assigned=assigned,
        is_connected=_is_teams_connected(conn, tokens),
        connection_status=conn.status if conn else "not_configured",
        microsoft_email=(conn.config_metadata_json or {}).get("microsoft_email") if conn else tokens.microsoft_email if tokens else None,
        last_synced_at=get_last_sync(db, ctx.company_id, ctx.user.id),
        oauth_available=platform_config is not None,
        message=(
            None
            if platform_config
            else (
                "Set TEAMS_CLIENT_ID and TEAMS_CLIENT_SECRET in your .env file, or configure "
                "the Teams app under Super Admin → Integrations → Microsoft Teams. "
                f"Redirect URI: {settings.api_public_url.rstrip('/')}/api/oauth/teams/callback"
            )
        ),
    )


@router.get("/oauth/start", response_model=TeamsOAuthStartResponse)
def teams_oauth_start(
    ctx: CompanyAuthDep,
    db: DbDep,
    redirect_path: str | None = None,
):
    _require_teams_access(db, ctx)
    from models import Company

    company = db.query(Company).filter(Company.id == ctx.company_id).first()
    slug = company.slug if company else ""
    default_redirect = f"{__import__('config').settings.web_base_url}/c/{slug}/teams"
    path = redirect_path or default_redirect
    try:
        url, _ = start_teams_oauth(
            db,
            user_id=ctx.user.id,
            company_id=ctx.company_id,
            redirect_path=path,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return TeamsOAuthStartResponse(authorize_url=url)


@router.post("/connect/mock", response_model=TeamsConnectionStatus)
def teams_connect_mock(ctx: CompanyWriterDep, db: DbDep):
    try:
        connect_teams_mock(db, company_id=ctx.company_id, user_id=ctx.user.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return teams_status(ctx, db)


@router.post("/disconnect", response_model=TeamsConnectionStatus)
def teams_disconnect(ctx: CompanyWriterDep, db: DbDep):
    conn = get_teams_connection(db, ctx.company_id, ctx.user.id)
    if conn:
        db.delete(conn)
        db.commit()
    return teams_status(ctx, db)


@router.post("/sync", response_model=TeamsSyncResponse)
def teams_sync(ctx: CompanyAuthDep, db: DbDep):
    _require_teams_access(db, ctx)
    conn = get_teams_connection(db, ctx.company_id, ctx.user.id)
    if not conn or conn.status != "connected":
        raise HTTPException(400, "Connect Microsoft Teams first")

    try:
        chats, messages = _run_teams_sync(
            db,
            company_id=ctx.company_id,
            user_id=ctx.user.id,
            conn=conn,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Teams sync failed: {exc}") from exc

    last = get_last_sync(db, ctx.company_id, ctx.user.id) or datetime.now(UTC)
    return TeamsSyncResponse(chats_synced=chats, messages_synced=messages, last_synced_at=last)


@router.get("/chats", response_model=list[TeamsChatItem])
def list_teams_chats(ctx: CompanyAuthDep, db: DbDep, sync: bool = True):
    _require_teams_access(db, ctx)
    conn = get_teams_connection(db, ctx.company_id, ctx.user.id)
    if not conn or conn.status != "connected":
        raise HTTPException(400, "Connect Microsoft Teams first")

    if sync:
        try:
            _run_teams_sync(
                db,
                company_id=ctx.company_id,
                user_id=ctx.user.id,
                conn=conn,
            )
        except Exception:
            pass

    chats = (
        db.query(TeamsChat)
        .filter(TeamsChat.company_id == ctx.company_id, TeamsChat.user_id == ctx.user.id)
        .order_by(TeamsChat.last_message_at.desc().nullslast())
        .all()
    )
    return [
        TeamsChatItem(
            id=c.id,
            graph_chat_id=c.graph_chat_id,
            chat_type=c.chat_type,
            topic=c.topic,
            team_name=c.team_name,
            channel_name=c.channel_name,
            display_name=chat_display_name(c),
            last_message_preview=c.last_message_preview,
            last_message_at=c.last_message_at,
        )
        for c in chats
    ]


@router.get("/chats/{graph_chat_id}/messages", response_model=list[TeamsMessageItem])
def list_chat_messages(graph_chat_id: str, ctx: CompanyAuthDep, db: DbDep):
    _require_teams_access(db, ctx)
    conn = get_teams_connection(db, ctx.company_id, ctx.user.id)
    if not conn:
        raise HTTPException(400, "Connect Microsoft Teams first")

    own_email = (conn.config_metadata_json or {}).get("microsoft_email", "").lower()
    messages = (
        db.query(TeamsMessage)
        .filter(
            TeamsMessage.company_id == ctx.company_id,
            TeamsMessage.user_id == ctx.user.id,
            TeamsMessage.graph_chat_id == graph_chat_id,
        )
        .order_by(TeamsMessage.message_created_at.asc())
        .limit(100)
        .all()
    )
    return [
        TeamsMessageItem(
            id=m.id,
            graph_message_id=m.graph_message_id,
            sender_name=m.sender_name,
            sender_email=m.sender_email,
            body_text=m.body_text,
            message_created_at=m.message_created_at,
            is_own_message=bool(
                own_email and m.sender_email and m.sender_email.lower() == own_email
            ),
        )
        for m in messages
    ]


@router.post("/chats/{graph_chat_id}/messages", response_model=TeamsMessageItem)
def send_teams_message(graph_chat_id: str, body: TeamsSendMessageRequest, ctx: CompanyWriterDep, db: DbDep):
    _require_teams_access(db, ctx)
    conn = get_teams_connection(db, ctx.company_id, ctx.user.id)
    if not conn or conn.status != "connected":
        raise HTTPException(400, "Connect Microsoft Teams first")

    user = db.query(User).filter(User.id == ctx.user.id).first()
    now = datetime.now(UTC)
    chat_row = (
        db.query(TeamsChat)
        .filter(
            TeamsChat.company_id == ctx.company_id,
            TeamsChat.user_id == ctx.user.id,
            TeamsChat.graph_chat_id == graph_chat_id,
        )
        .first()
    )

    if settings.teams_mock_mode and _is_mock_connection(conn):
        msg = TeamsMessage(
            company_id=ctx.company_id,
            user_id=ctx.user.id,
            graph_chat_id=graph_chat_id,
            graph_message_id=f"local-{now.timestamp()}",
            sender_name=user.full_name if user else "You",
            sender_email=(conn.config_metadata_json or {}).get("microsoft_email"),
            body_text=body.content,
            message_created_at=now,
        )
        db.add(msg)
        if chat_row:
            chat_row.last_message_preview = body.content[:500]
            chat_row.last_message_at = now
        db.commit()
        db.refresh(msg)
        return TeamsMessageItem(
            id=msg.id,
            graph_message_id=msg.graph_message_id,
            sender_name=msg.sender_name,
            sender_email=msg.sender_email,
            body_text=msg.body_text,
            message_created_at=msg.message_created_at,
            is_own_message=True,
        )

    if not conn.encrypted_config_ref:
        raise HTTPException(400, "Connect Microsoft Teams first")

    config = get_platform_teams_config(db)
    if not config:
        raise HTTPException(400, "Platform Teams app not configured")

    secrets = decrypt_secrets(conn.encrypted_config_ref)
    secrets = ensure_fresh_tokens(db, config, secrets)
    conn.encrypted_config_ref = encrypt_secrets(secrets)
    db.commit()

    tokens = secrets_to_tokens(secrets)
    if not tokens:
        raise HTTPException(400, "Invalid Teams token")

    try:
        if chat_row and chat_row.chat_type == "channel" and chat_row.team_id and chat_row.channel_id:
            result = send_channel_message(tokens.access_token, chat_row.team_id, chat_row.channel_id, body.content)
        else:
            result = send_chat_message(tokens.access_token, graph_chat_id, body.content)
    except Exception as exc:
        raise HTTPException(502, f"Failed to send message: {exc}") from exc

    msg = TeamsMessage(
        company_id=ctx.company_id,
        user_id=ctx.user.id,
        graph_chat_id=graph_chat_id,
        graph_message_id=result.get("id", f"local-{now.timestamp()}"),
        sender_name=user.full_name if user else "You",
        sender_email=tokens.microsoft_email,
        body_text=body.content,
        message_created_at=now,
    )
    db.add(msg)
    if chat_row:
        chat_row.last_message_preview = body.content[:500]
        chat_row.last_message_at = now
    db.commit()
    db.refresh(msg)

    return TeamsMessageItem(
        id=msg.id,
        graph_message_id=msg.graph_message_id,
        sender_name=msg.sender_name,
        sender_email=msg.sender_email,
        body_text=msg.body_text,
        message_created_at=msg.message_created_at,
        is_own_message=True,
    )
