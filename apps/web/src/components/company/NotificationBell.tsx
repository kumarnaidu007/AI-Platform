import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bell } from "lucide-react";
import { notificationsApi } from "@/services/notificationsApi";
import { useAuth } from "@/context/AuthContext";
import { POLL_NOTIFICATIONS_MS } from "@/lib/polling";
import { cn } from "@/lib/utils";

export function NotificationBell({ className }: { className?: string }) {
  const { session } = useAuth();
  const unread = useQuery({
    queryKey: ["notifications-unread"],
    queryFn: () => notificationsApi.unreadCount(),
    enabled: !!session?.token,
    staleTime: POLL_NOTIFICATIONS_MS,
    refetchInterval: POLL_NOTIFICATIONS_MS,
    refetchIntervalInBackground: false,
  });
  const count = unread.data ?? 0;

  return (
    <Link
      to="/workspace/notifications"
      className={cn("relative rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground", className)}
      aria-label="Notifications"
    >
      <Bell className="h-5 w-5" />
      {count > 0 && (
        <span className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
          {count > 9 ? "9+" : count}
        </span>
      )}
    </Link>
  );
}
