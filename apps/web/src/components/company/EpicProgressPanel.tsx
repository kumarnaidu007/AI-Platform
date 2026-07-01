import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { intakeApi } from "@/services/intakeApi";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-800",
  implementing: "bg-blue-100 text-blue-800",
  approved: "bg-sky-100 text-sky-800",
  awaiting_pr_review: "bg-amber-100 text-amber-800",
  implementation_failed: "bg-red-100 text-red-800",
  not_started: "bg-muted text-muted-foreground",
};

export function EpicProgressPanel({ parentKey }: { parentKey: string }) {
  const progress = useQuery({
    queryKey: ["epic-progress", parentKey],
    queryFn: () => intakeApi.getEpicProgress(parentKey),
    enabled: !!parentKey,
  });

  if (progress.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading epic progress…
      </div>
    );
  }

  const data = progress.data;
  if (!data || data.totalSubtasks === 0) return null;

  const pct = data.totalSubtasks > 0 ? Math.round((data.completedSubtasks / data.totalSubtasks) * 100) : 0;

  return (
    <section className="rounded-lg border bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Epic progress — {data.parentJiraKey}</h2>
        <span className="text-xs text-muted-foreground">
          {data.completedSubtasks}/{data.totalSubtasks} completed ({pct}%)
        </span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
      <ul className="mt-4 space-y-2">
        {data.subtasks.map((task) => (
          <li key={task.jiraIssueKey} className="flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
            <div>
              {task.intakeId ? (
                <Link to={`/workspace/jira/${task.jiraIssueKey}`} className="font-medium text-primary hover:underline">
                  {task.jiraIssueKey}
                </Link>
              ) : (
                <span className="font-medium">{task.jiraIssueKey}</span>
              )}
              <span className="ml-2 text-muted-foreground">{task.jiraSummary}</span>
            </div>
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase", STATUS_COLORS[task.status] ?? "bg-muted")}>
              {task.status.replace(/_/g, " ")}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
