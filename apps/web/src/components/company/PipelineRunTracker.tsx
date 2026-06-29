import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { AgentIcon } from "@/components/admin/AgentIcon";
import { companyApi } from "@/services/companyApi";
import { POLL_PIPELINE_MS, PIPELINE_ACTIVE_STATUSES, shouldPollPipeline } from "@/lib/polling";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  pending: "text-amber-600",
  running: "text-blue-600",
  awaiting_approval: "text-purple-600",
  completed: "text-emerald-600",
  failed: "text-red-600",
  skipped: "text-muted-foreground",
  cancelled: "text-muted-foreground",
};

const TERMINAL_RUN_STATUSES = new Set(["completed", "failed", "cancelled"]);

function StepIcon({ status }: { status: string }) {
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-blue-600" />;
  if (status === "completed") return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
  if (status === "failed") return <XCircle className="h-4 w-4 text-red-600" />;
  return <span className="h-2 w-2 rounded-full bg-muted-foreground/40" />;
}

interface PipelineRunTrackerProps {
  projectId: string;
  runId: string | null | undefined;
  compact?: boolean;
  showRunPicker?: boolean;
  selectedRunId?: string | null;
  onSelectRun?: (runId: string) => void;
  /** When false, fetches once and never polls (use on ticket workspace during implementation). */
  enablePolling?: boolean;
  /** Invalidate this intake query when the run reaches a terminal state. */
  intakeQueryKey?: readonly unknown[];
}

export function PipelineRunTracker({
  projectId,
  runId,
  compact = false,
  showRunPicker = false,
  selectedRunId,
  onSelectRun,
  enablePolling = false,
  intakeQueryKey,
}: PipelineRunTrackerProps) {
  const queryClient = useQueryClient();
  const effectiveRunId = runId ?? selectedRunId ?? null;

  const runsQuery = useQuery({
    queryKey: ["company-project-runs", projectId],
    queryFn: () => companyApi.getProjectRuns(projectId),
    enabled: showRunPicker,
    staleTime: 30_000,
  });

  const detailQuery = useQuery({
    queryKey: ["pipeline-run-detail", projectId, effectiveRunId],
    queryFn: () => companyApi.getPipelineRunDetail(projectId, effectiveRunId!),
    enabled: !!effectiveRunId,
    staleTime: enablePolling ? 0 : 60_000,
    refetchInterval: (query) => {
      if (!enablePolling) return false;
      const status = query.state.data?.status;
      return shouldPollPipeline(status) ? POLL_PIPELINE_MS : false;
    },
  });

  const detail = detailQuery.data;
  const runs = runsQuery.data ?? [];

  useEffect(() => {
    if (!detail?.status || !TERMINAL_RUN_STATUSES.has(detail.status)) return;
    if (intakeQueryKey?.length) {
      queryClient.invalidateQueries({ queryKey: intakeQueryKey });
    }
  }, [detail?.status, intakeQueryKey, queryClient]);

  if (!effectiveRunId) {
    return <p className="text-sm text-muted-foreground">No pipeline run linked yet.</p>;
  }

  if (detailQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading pipeline…
      </div>
    );
  }

  if (!detail) {
    return <p className="text-sm text-muted-foreground">Pipeline run not found.</p>;
  }

  return (
    <div className={cn("space-y-3", compact && "space-y-2")}>
      {showRunPicker && runs.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {runs.map((run) => (
            <button
              key={run.id}
              type="button"
              onClick={() => onSelectRun?.(run.id)}
              className={cn(
                "rounded-md border px-2 py-1 text-[11px] capitalize",
                effectiveRunId === run.id ? "border-primary bg-primary/5" : "hover:bg-muted/40"
              )}
            >
              <span className={STATUS_COLORS[run.status] ?? ""}>{run.status}</span>
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium capitalize">
            Status: <span className={STATUS_COLORS[detail.status]}>{detail.status.replace(/_/g, " ")}</span>
          </p>
          {detail.currentStep && (
            <p className="text-xs text-muted-foreground">
              Current: {detail.currentStep.replace(/_/g, " ")}
            </p>
          )}
          {detail.errorMessage && <p className="mt-1 text-xs text-red-600">{detail.errorMessage}</p>}
        </div>
        {PIPELINE_ACTIVE_STATUSES.has(detail.status) && (
          <Loader2 className="h-5 w-5 shrink-0 animate-spin text-primary" />
        )}
      </div>

      <div className={cn("grid gap-2", compact ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1")}>
        {detail.steps.map((step) => (
          <div
            key={step.id}
            className={cn(
              "flex items-center gap-2 rounded-md border px-3 py-2",
              step.status === "running" && "border-blue-200 bg-blue-50/50",
              step.status === "completed" && "border-emerald-200/80 bg-emerald-50/30",
              step.status === "failed" && "border-red-200 bg-red-50/40"
            )}
          >
            <StepIcon status={step.status} />
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-muted">
              <AgentIcon agentKey={step.stepName} className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium capitalize">{step.stepName.replace(/_/g, " ")}</p>
              <p className="text-[10px] capitalize text-muted-foreground">{step.status}</p>
            </div>
            <span className="text-[10px] text-muted-foreground">#{step.stepOrder}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
