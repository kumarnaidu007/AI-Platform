import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bell, CheckCheck, Loader2 } from "lucide-react";
import { notificationsApi } from "@/services/notificationsApi";
import { cn } from "@/lib/utils";

export function CompanyNotificationsPage() {
  const queryClient = useQueryClient();
  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () => notificationsApi.list(),
  });

  const markAll = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-unread"] });
    },
  });

  const markOne = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-unread"] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Bell className="h-6 w-6" /> Notifications
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Clarification questions, spec reviews, plan approvals, and PR reviews.
          </p>
        </div>
        <button
          type="button"
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
        >
          <CheckCheck className="h-4 w-4" /> Mark all read
        </button>
      </div>

      <div className="rounded-lg border bg-card divide-y">
        {notifications.isLoading ? (
          <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        ) : (notifications.data ?? []).length === 0 ? (
          <p className="p-8 text-sm text-muted-foreground">No notifications yet.</p>
        ) : (
          (notifications.data ?? []).map((n) => (
            <div
              key={n.id}
              className={cn("flex items-start gap-4 px-4 py-4", !n.isRead && "bg-primary/5")}
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{n.title}</p>
                {n.body && <p className="mt-0.5 text-sm text-muted-foreground">{n.body}</p>}
                <p className="mt-1 text-xs text-muted-foreground">{new Date(n.createdAt).toLocaleString()}</p>
              </div>
              <div className="flex shrink-0 gap-2">
                {n.linkPath && (
                  <Link
                    to={n.linkPath}
                    onClick={() => !n.isRead && markOne.mutate(n.id)}
                    className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                  >
                    Open
                  </Link>
                )}
                {!n.isRead && (
                  <button
                    type="button"
                    onClick={() => markOne.mutate(n.id)}
                    className="rounded-md border px-3 py-1.5 text-xs"
                  >
                    Mark read
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
