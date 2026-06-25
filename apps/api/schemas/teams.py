from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TeamsConnectionStatus(BaseModel):
    is_assigned: bool
    is_connected: bool
    connection_status: str = "not_configured"
    microsoft_email: str | None = None
    last_synced_at: datetime | None = None
    oauth_available: bool = True
    message: str | None = None


class TeamsOAuthStartResponse(BaseModel):
    authorize_url: str


class TeamsChatItem(BaseModel):
    id: UUID
    graph_chat_id: str
    chat_type: str
    topic: str | None = None
    team_name: str | None = None
    channel_name: str | None = None
    display_name: str
    last_message_preview: str | None = None
    last_message_at: datetime | None = None


class TeamsMessageItem(BaseModel):
    id: UUID
    graph_message_id: str
    sender_name: str | None = None
    sender_email: str | None = None
    body_text: str | None = None
    message_created_at: datetime
    is_own_message: bool = False


class TeamsSendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class TeamsSyncResponse(BaseModel):
    chats_synced: int
    messages_synced: int
    last_synced_at: datetime
