import { api } from "@/services/authApi";

export interface TeamsConnectionStatus {
  isAssigned: boolean;
  isConnected: boolean;
  connectionStatus: string;
  microsoftEmail: string | null;
  lastSyncedAt: string | null;
  oauthAvailable: boolean;
  message: string | null;
}

export interface TeamsChat {
  id: string;
  graphChatId: string;
  chatType: string;
  topic: string | null;
  teamName: string | null;
  channelName: string | null;
  displayName: string;
  lastMessagePreview: string | null;
  lastMessageAt: string | null;
}

export interface TeamsMessage {
  id: string;
  graphMessageId: string;
  senderName: string | null;
  senderEmail: string | null;
  bodyText: string | null;
  messageCreatedAt: string;
  isOwnMessage: boolean;
}

function mapStatus(row: Record<string, unknown>): TeamsConnectionStatus {
  return {
    isAssigned: Boolean(row.is_assigned),
    isConnected: Boolean(row.is_connected),
    connectionStatus: String(row.connection_status ?? "not_configured"),
    microsoftEmail: row.microsoft_email != null ? String(row.microsoft_email) : null,
    lastSyncedAt: row.last_synced_at != null ? String(row.last_synced_at) : null,
    oauthAvailable: Boolean(row.oauth_available),
    message: row.message != null ? String(row.message) : null,
  };
}

function mapChat(row: Record<string, unknown>): TeamsChat {
  return {
    id: String(row.id),
    graphChatId: String(row.graph_chat_id),
    chatType: String(row.chat_type),
    topic: row.topic != null ? String(row.topic) : null,
    teamName: row.team_name != null ? String(row.team_name) : null,
    channelName: row.channel_name != null ? String(row.channel_name) : null,
    displayName: String(row.display_name),
    lastMessagePreview: row.last_message_preview != null ? String(row.last_message_preview) : null,
    lastMessageAt: row.last_message_at != null ? String(row.last_message_at) : null,
  };
}

function mapMessage(row: Record<string, unknown>): TeamsMessage {
  return {
    id: String(row.id),
    graphMessageId: String(row.graph_message_id),
    senderName: row.sender_name != null ? String(row.sender_name) : null,
    senderEmail: row.sender_email != null ? String(row.sender_email) : null,
    bodyText: row.body_text != null ? String(row.body_text) : null,
    messageCreatedAt: String(row.message_created_at),
    isOwnMessage: Boolean(row.is_own_message),
  };
}

export const teamsApi = {
  getStatus: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/company/teams/status");
    return mapStatus(data);
  },

  startOAuth: async (redirectPath?: string) => {
    const { data } = await api.get<Record<string, unknown>>("/api/company/teams/oauth/start", {
      params: redirectPath ? { redirect_path: redirectPath } : undefined,
    });
    return { authorizeUrl: String(data.authorize_url) };
  },

  connectMock: async () => {
    const { data } = await api.post<Record<string, unknown>>("/api/company/teams/connect/mock");
    return mapStatus(data);
  },

  disconnect: async () => {
    const { data } = await api.post<Record<string, unknown>>("/api/company/teams/disconnect");
    return mapStatus(data);
  },

  sync: async () => {
    const { data } = await api.post<Record<string, unknown>>("/api/company/teams/sync");
    return {
      chatsSynced: Number(data.chats_synced),
      messagesSynced: Number(data.messages_synced),
      lastSyncedAt: String(data.last_synced_at),
    };
  },

  getChats: async (sync = true) => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/company/teams/chats", {
      params: { sync },
    });
    return data.map(mapChat);
  },

  getMessages: async (graphChatId: string) => {
    const { data } = await api.get<Record<string, unknown>[]>(
      `/api/company/teams/chats/${encodeURIComponent(graphChatId)}/messages`
    );
    return data.map(mapMessage);
  },

  sendMessage: async (graphChatId: string, content: string) => {
    const { data } = await api.post<Record<string, unknown>>(
      `/api/company/teams/chats/${encodeURIComponent(graphChatId)}/messages`,
      { content }
    );
    return mapMessage(data);
  },
};
