"""Sync Microsoft Teams chats and messages into local cache."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from config import settings
from models.company_portal import MemberIntegrationConnection
from models.teams import TeamsChat, TeamsMessage, TeamsSyncState
from services.microsoft_graph import (
    TeamsAppConfig,
    ensure_fresh_tokens,
    fetch_channel_messages,
    fetch_chat_messages,
    fetch_chats,
    fetch_joined_teams,
    fetch_team_channels,
    fetch_me,
    parse_message_body,
    parse_sender,
    secrets_to_tokens,
    tokens_to_secrets,
)
from services.secrets import decrypt_secrets, encrypt_secrets


def _upsert_chat(
    db: Session,
    *,
    company_id,
    user_id,
    graph_chat_id: str,
    chat_type: str,
    topic: str | None,
    team_id: str | None = None,
    team_name: str | None = None,
    channel_id: str | None = None,
    channel_name: str | None = None,
    last_preview: str | None = None,
    last_at: datetime | None = None,
) -> TeamsChat:
    row = (
        db.query(TeamsChat)
        .filter(
            TeamsChat.company_id == company_id,
            TeamsChat.user_id == user_id,
            TeamsChat.graph_chat_id == graph_chat_id,
        )
        .first()
    )
    if not row:
        row = TeamsChat(
            company_id=company_id,
            user_id=user_id,
            graph_chat_id=graph_chat_id,
        )
        db.add(row)
    row.chat_type = chat_type
    row.topic = topic
    row.team_id = team_id
    row.team_name = team_name
    row.channel_id = channel_id
    row.channel_name = channel_name
    if last_preview:
        row.last_message_preview = last_preview[:500]
    if last_at:
        row.last_message_at = last_at
    row.synced_at = datetime.now(UTC)
    return row


def _upsert_message(
    db: Session,
    *,
    company_id,
    user_id,
    graph_chat_id: str,
    message: dict,
    own_email: str | None,
) -> bool:
    msg_id = message.get("id")
    if not msg_id:
        return False
    existing = (
        db.query(TeamsMessage)
        .filter(
            TeamsMessage.company_id == company_id,
            TeamsMessage.user_id == user_id,
            TeamsMessage.graph_message_id == msg_id,
        )
        .first()
    )
    if existing:
        return False
    sender_name, sender_email = parse_sender(message)
    created = message.get("createdDateTime") or message.get("lastModifiedDateTime")
    try:
        created_at = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        created_at = datetime.now(UTC)
    db.add(
        TeamsMessage(
            company_id=company_id,
            user_id=user_id,
            graph_chat_id=graph_chat_id,
            graph_message_id=msg_id,
            sender_name=sender_name,
            sender_email=sender_email,
            body_text=parse_message_body(message),
            body_html=(message.get("body") or {}).get("content"),
            message_created_at=created_at,
        )
    )
    return True


def sync_mock_data(db: Session, company_id, user_id) -> tuple[int, int]:
    """Demo chats when Graph is unavailable (local dev)."""
    now = datetime.now(UTC)
    chats_data = [
        {
            "graph_chat_id": "mock-chat-1",
            "chat_type": "group",
            "topic": "Engineering Standup",
            "preview": "Alice: Sprint planning at 3pm today",
        },
        {
            "graph_chat_id": "mock-channel-1",
            "chat_type": "channel",
            "topic": "General",
            "team_name": "Acme Engineering",
            "channel_name": "General",
            "preview": "Bob: Deploy completed successfully",
        },
        {
            "graph_chat_id": "mock-chat-2",
            "chat_type": "oneOnOne",
            "topic": "Jane Admin",
            "preview": "Thanks for connecting Teams!",
        },
    ]
    messages_count = 0
    for c in chats_data:
        _upsert_chat(
            db,
            company_id=company_id,
            user_id=user_id,
            graph_chat_id=c["graph_chat_id"],
            chat_type=c["chat_type"],
            topic=c.get("topic"),
            team_name=c.get("team_name"),
            channel_name=c.get("channel_name"),
            last_preview=c.get("preview"),
            last_at=now,
        )
        for i, (sender, text) in enumerate(
            [
                ("Alice", "Sprint planning at 3pm today"),
                ("You", "I'll join the standup"),
                ("Bob", "Deploy completed successfully"),
            ]
        ):
            _upsert_message(
                db,
                company_id=company_id,
                user_id=user_id,
                graph_chat_id=c["graph_chat_id"],
                message={
                    "id": f"{c['graph_chat_id']}-msg-{i}",
                    "createdDateTime": now.isoformat(),
                    "body": {"contentType": "text", "content": text},
                    "from": {"user": {"displayName": sender, "email": f"{sender.lower()}@acme.com"}},
                },
                own_email="you@acme.com",
            )
            messages_count += 1

    state = (
        db.query(TeamsSyncState)
        .filter(
            TeamsSyncState.company_id == company_id,
            TeamsSyncState.user_id == user_id,
            TeamsSyncState.resource_type == "chats",
        )
        .first()
    )
    if not state:
        state = TeamsSyncState(company_id=company_id, user_id=user_id, resource_type="chats")
        db.add(state)
    state.last_synced_at = now
    db.commit()
    return len(chats_data), messages_count


def sync_teams_for_user(
    db: Session,
    *,
    company_id,
    user_id,
    conn: MemberIntegrationConnection,
    config: TeamsAppConfig,
) -> tuple[int, int]:
    secrets = decrypt_secrets(conn.encrypted_config_ref)
    if settings.teams_mock_mode and not secrets.get("access_token"):
        return sync_mock_data(db, company_id, user_id)

    secrets = ensure_fresh_tokens(db, config, secrets)
    conn.encrypted_config_ref = encrypt_secrets(secrets)
    conn.status = "connected"
    tokens = secrets_to_tokens(secrets)
    if not tokens:
        if settings.teams_mock_mode:
            return sync_mock_data(db, company_id, user_id)
        raise ValueError("Teams not connected — complete Microsoft sign-in first")

    access_token = tokens.access_token
    own_email = tokens.microsoft_email
    if not own_email:
        try:
            me = fetch_me(access_token)
            own_email = me.get("mail") or me.get("userPrincipalName")
            tokens.microsoft_email = own_email
            conn.encrypted_config_ref = encrypt_secrets(tokens_to_secrets(tokens))
        except Exception:
            pass

    chats_synced = 0
    messages_synced = 0
    now = datetime.now(UTC)

    try:
        for chat in fetch_chats(access_token):
            chat_id = chat.get("id")
            if not chat_id:
                continue
            topic = chat.get("topic") or "Chat"
            chat_type = chat.get("chatType") or "chat"
            preview_data = chat.get("lastMessagePreview") or {}
            preview_body = parse_message_body(preview_data) if preview_data else None
            last_at_str = chat.get("lastUpdatedDateTime")
            last_at = None
            if last_at_str:
                try:
                    last_at = datetime.fromisoformat(str(last_at_str).replace("Z", "+00:00"))
                except ValueError:
                    last_at = now
            _upsert_chat(
                db,
                company_id=company_id,
                user_id=user_id,
                graph_chat_id=chat_id,
                chat_type=chat_type,
                topic=topic,
                last_preview=preview_body,
                last_at=last_at,
            )
            chats_synced += 1
            try:
                for msg in fetch_chat_messages(access_token, chat_id, top=25):
                    if _upsert_message(
                        db,
                        company_id=company_id,
                        user_id=user_id,
                        graph_chat_id=chat_id,
                        message=msg,
                        own_email=own_email,
                    ):
                        messages_synced += 1
            except Exception:
                continue

        for team in fetch_joined_teams(access_token):
            team_id = team.get("id")
            team_name = team.get("displayName") or "Team"
            if not team_id:
                continue
            try:
                channels = fetch_team_channels(access_token, team_id)
            except Exception:
                continue
            for channel in channels:
                channel_id = channel.get("id")
                channel_name = channel.get("displayName") or "Channel"
                if not channel_id:
                    continue
                graph_chat_id = f"channel:{team_id}:{channel_id}"
                _upsert_chat(
                    db,
                    company_id=company_id,
                    user_id=user_id,
                    graph_chat_id=graph_chat_id,
                    chat_type="channel",
                    topic=f"{team_name} / {channel_name}",
                    team_id=team_id,
                    team_name=team_name,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    last_at=now,
                )
                chats_synced += 1
                try:
                    for msg in fetch_channel_messages(access_token, team_id, channel_id, top=25):
                        if _upsert_message(
                            db,
                            company_id=company_id,
                            user_id=user_id,
                            graph_chat_id=graph_chat_id,
                            message=msg,
                            own_email=own_email,
                        ):
                            messages_synced += 1
                except Exception:
                    continue
    except Exception:
        if settings.teams_mock_mode:
            db.rollback()
            return sync_mock_data(db, company_id, user_id)
        raise

    state = (
        db.query(TeamsSyncState)
        .filter(
            TeamsSyncState.company_id == company_id,
            TeamsSyncState.user_id == user_id,
            TeamsSyncState.resource_type == "chats",
        )
        .first()
    )
    if not state:
        state = TeamsSyncState(company_id=company_id, user_id=user_id, resource_type="chats")
        db.add(state)
    state.last_synced_at = now
    db.commit()
    return chats_synced, messages_synced
