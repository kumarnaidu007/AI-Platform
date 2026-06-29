import { api } from "@/services/authApi";

export interface AppNotification {
  id: string;
  notificationType: string;
  title: string;
  body: string | null;
  linkPath: string | null;
  intakeId: string | null;
  isRead: boolean;
  createdAt: string;
}

function mapNotification(row: Record<string, unknown>): AppNotification {
  return {
    id: String(row.id),
    notificationType: String(row.notification_type),
    title: String(row.title),
    body: row.body != null ? String(row.body) : null,
    linkPath: row.link_path != null ? String(row.link_path) : null,
    intakeId: row.intake_id != null ? String(row.intake_id) : null,
    isRead: Boolean(row.is_read),
    createdAt: String(row.created_at),
  };
}

export const notificationsApi = {
  list: async (unreadOnly = false) => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/notifications", {
      params: unreadOnly ? { unread_only: true } : undefined,
    });
    return data.map(mapNotification);
  },

  unreadCount: async () => {
    const { data } = await api.get<{ count: number }>("/api/workspace/notifications/unread-count");
    return data.count;
  },

  markRead: async (id: string) => {
    const { data } = await api.post<Record<string, unknown>>(`/api/workspace/notifications/${id}/read`);
    return mapNotification(data);
  },

  markAllRead: async () => {
    const { data } = await api.post<{ updated: number }>("/api/workspace/notifications/read-all");
    return data.updated;
  },
};
