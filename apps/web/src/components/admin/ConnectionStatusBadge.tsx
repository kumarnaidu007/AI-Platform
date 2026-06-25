import { cn } from "@/lib/utils";
import type { ConnectionStatus } from "@/types/platform";

const styles: Record<ConnectionStatus, string> = {
  connected: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  not_configured: "bg-slate-50 text-slate-600 ring-slate-500/20",
  error: "bg-red-50 text-red-700 ring-red-600/20",
  disabled: "bg-slate-100 text-slate-400 ring-slate-400/20",
};

const labels: Record<ConnectionStatus, string> = {
  connected: "Connected",
  not_configured: "Not configured",
  error: "Error",
  disabled: "Disabled",
};

export function ConnectionStatusBadge({
  status,
  className,
}: {
  status: ConnectionStatus;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        styles[status],
        className
      )}
    >
      {labels[status]}
    </span>
  );
}
