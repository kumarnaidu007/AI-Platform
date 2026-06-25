import { cn } from "@/lib/utils";

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const styles: Record<string, string> = {
    active: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    trial: "bg-amber-50 text-amber-700 ring-amber-600/20",
    suspended: "bg-red-50 text-red-700 ring-red-600/20",
    running: "bg-blue-50 text-blue-700 ring-blue-600/20",
    completed: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    failed: "bg-red-50 text-red-700 ring-red-600/20",
    healthy: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    degraded: "bg-amber-50 text-amber-700 ring-amber-600/20",
    down: "bg-red-50 text-red-700 ring-red-600/20",
    draft: "bg-slate-50 text-slate-600 ring-slate-500/20",
    paused: "bg-slate-50 text-slate-600 ring-slate-500/20",
    archived: "bg-slate-50 text-slate-500 ring-slate-500/20",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset capitalize",
        styles[status] ?? "bg-slate-50 text-slate-600 ring-slate-500/20",
        className
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
