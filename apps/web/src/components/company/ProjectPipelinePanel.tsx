import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, Loader2, Play, XCircle } from "lucide-react";
import { AgentIcon } from "@/components/admin/AgentIcon";
import { companyApi } from "@/services/companyApi";
import { githubApi } from "@/services/githubApi";
import { jiraApi } from "@/services/jiraApi";
import { getApiErrorMessage } from "@/services/authApi";
import { cn } from "@/lib/utils";

interface ProjectPipelinePanelProps {
  projectId: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "text-amber-600",
  running: "text-blue-600",
  awaiting_approval: "text-purple-600",
  completed: "text-emerald-600",
  failed: "text-red-600",
  skipped: "text-muted-foreground",
  cancelled: "text-muted-foreground",
};

const ACTIVE_RUN_STATUSES = new Set(["pending", "running", "awaiting_approval"]);

function StepIcon({ status }: { status: string }) {
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-blue-600" />;
  if (status === "completed") return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
  if (status === "failed") return <XCircle className="h-4 w-4 text-red-600" />;
  return <span className="h-2 w-2 rounded-full bg-muted-foreground/40" />;
}

export function ProjectPipelinePanel({ projectId }: ProjectPipelinePanelProps) {
  const queryClient = useQueryClient();
  const canWrite = true;
  const [mode, setMode] = useState<"jira" | "freeform">("jira");
  const [requirements, setRequirements] = useState("");
  const [selectedProjectKey, setSelectedProjectKey] = useState("");
  const [selectedIssueKey, setSelectedIssueKey] = useState("");
  const [selectedAgents, setSelectedAgents] = useState<Record<string, boolean>>({});
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const githubStatusQuery = useQuery({
    queryKey: ["github-status"],
    queryFn: () => githubApi.getStatus(),
  });

  const jiraStatusQuery = useQuery({
    queryKey: ["jira-status"],
    queryFn: () => jiraApi.getStatus(),
  });

  const jiraProjectsQuery = useQuery({
    queryKey: ["jira-projects"],
    queryFn: () => jiraApi.listProjects(),
    enabled: mode === "jira" && jiraStatusQuery.data?.isConnected === true,
  });

  const jiraIssuesQuery = useQuery({
    queryKey: ["jira-issues", selectedProjectKey],
    queryFn: () => jiraApi.listIssues({ projectKey: selectedProjectKey || undefined }),
    enabled: mode === "jira" && jiraStatusQuery.data?.isConnected === true,
  });

  const agentsQuery = useQuery({
    queryKey: ["project-agents", projectId],
    queryFn: () => companyApi.getProjectAgents(projectId),
  });

  const runsQuery = useQuery({
    queryKey: ["company-project-runs", projectId],
    queryFn: () => companyApi.getProjectRuns(projectId),
    refetchInterval: (query) => {
      const runs = query.state.data ?? [];
      return runs.some((r) => ACTIVE_RUN_STATUSES.has(r.status)) ? 3000 : false;
    },
  });

  const detailQuery = useQuery({
    queryKey: ["pipeline-run-detail", projectId, selectedRunId],
    queryFn: () => companyApi.getPipelineRunDetail(projectId, selectedRunId!),
    enabled: !!selectedRunId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_RUN_STATUSES.has(status) ? 2000 : false;
    },
  });

  const agents = agentsQuery.data ?? [];
  const selectedIssue = useMemo(
    () => jiraIssuesQuery.data?.find((issue) => issue.key === selectedIssueKey) ?? null,
    [jiraIssuesQuery.data, selectedIssueKey]
  );

  useEffect(() => {
    if (!agents.length) return;
    setSelectedAgents((prev) => {
      const hasAny = Object.values(prev).some(Boolean);
      if (hasAny) return prev;
      const next: Record<string, boolean> = {};
      for (const agent of agents) {
        next[agent.agentKey] = agent.isEnabled;
      }
      if (!Object.values(next).some(Boolean) && agents.length > 0) {
        next[agents[0].agentKey] = true;
      }
      return next;
    });
  }, [agents]);

  useEffect(() => {
    const projects = jiraProjectsQuery.data ?? [];
    if (!selectedProjectKey && projects.length > 0 && projects[0].key) {
      setSelectedProjectKey(projects[0].key);
    }
  }, [jiraProjectsQuery.data, selectedProjectKey]);

  const approveMutation = useMutation({
    mutationFn: () => companyApi.approvePipelineRun(projectId, selectedRunId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipeline-run-detail", projectId, selectedRunId] });
      queryClient.invalidateQueries({ queryKey: ["company-project-runs", projectId] });
    },
    onError: (err: unknown) => setError(getApiErrorMessage(err, "Failed to approve plan")),
  });

  const rejectMutation = useMutation({
    mutationFn: () => companyApi.rejectPipelineRun(projectId, selectedRunId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipeline-run-detail", projectId, selectedRunId] });
      queryClient.invalidateQueries({ queryKey: ["company-project-runs", projectId] });
    },
    onError: (err: unknown) => setError(getApiErrorMessage(err, "Failed to reject plan")),
  });

  const startMutation = useMutation({
    mutationFn: () => {
      const agentKeys = Object.entries(selectedAgents)
        .filter(([, enabled]) => enabled)
        .map(([key]) => key);
      return companyApi.startPipelineRun(projectId, {
        requirementsText: requirements,
        jiraIssueKey: mode === "jira" ? selectedIssueKey : undefined,
        agentKeys: agentKeys.length > 0 ? agentKeys : undefined,
      });
    },
    onSuccess: (run) => {
      setError(null);
      setSelectedRunId(run.id);
      setRequirements("");
      queryClient.invalidateQueries({ queryKey: ["company-project-runs", projectId] });
      queryClient.invalidateQueries({ queryKey: ["company-project", projectId] });
    },
    onError: (err: unknown) => setError(getApiErrorMessage(err, "Failed to start pipeline")),
  });

  useEffect(() => {
    const runs = runsQuery.data ?? [];
    if (!selectedRunId && runs.length > 0) {
      setSelectedRunId(runs[0].id);
    }
  }, [runsQuery.data, selectedRunId]);

  const runs = runsQuery.data ?? [];
  const detail = detailQuery.data;
  const githubReady = githubStatusQuery.data?.isConnected === true;
  const jiraReady = jiraStatusQuery.data?.isConnected === true;
  const selectedAgentCount = Object.values(selectedAgents).filter(Boolean).length;

  const canStartJira = jiraReady && githubReady && !!selectedIssueKey && selectedAgentCount > 0;
  const canStartFreeform = githubReady && requirements.trim().length >= 10 && selectedAgentCount > 0;
  const canStart = mode === "jira" ? canStartJira : canStartFreeform;

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="rounded-lg border bg-card p-6">
          <h3 className="text-sm font-semibold">Start AI pipeline</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Connect GitHub and Jira, set a repository URL on this project, pick a ticket, add instructions, and choose
            agents for this run.
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setMode("jira")}
              className={cn(
                "rounded-md border px-3 py-1.5 text-xs font-medium",
                mode === "jira" ? "border-primary bg-primary/5" : "hover:bg-muted/40"
              )}
            >
              From Jira ticket
            </button>
            <button
              type="button"
              onClick={() => setMode("freeform")}
              className={cn(
                "rounded-md border px-3 py-1.5 text-xs font-medium",
                mode === "freeform" ? "border-primary bg-primary/5" : "hover:bg-muted/40"
              )}
            >
              Free text
            </button>
          </div>

          <div className="mt-4 grid gap-2 text-xs sm:grid-cols-2">
            <div
              className={cn(
                "rounded-md border px-3 py-2",
                githubReady ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800"
              )}
            >
              GitHub: {githubReady ? "Connected" : "Not connected — link under Integrations"}
            </div>
            <div
              className={cn(
                "rounded-md border px-3 py-2",
                mode === "jira"
                  ? jiraReady
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-amber-200 bg-amber-50 text-amber-800"
                  : "border-muted bg-muted/30 text-muted-foreground"
              )}
            >
              Jira:{" "}
              {mode === "jira"
                ? jiraReady
                  ? `Connected${jiraStatusQuery.data?.jiraSiteName ? ` (${jiraStatusQuery.data.jiraSiteName})` : ""}`
                  : "Not connected — link under Integrations"
                : "Optional for free text mode"}
            </div>
          </div>

          {mode === "jira" && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Jira project</label>
                <select
                  value={selectedProjectKey}
                  onChange={(e) => {
                    setSelectedProjectKey(e.target.value);
                    setSelectedIssueKey("");
                  }}
                  disabled={!jiraReady || jiraProjectsQuery.isLoading}
                  className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm"
                >
                  <option value="">All my open issues</option>
                  {(jiraProjectsQuery.data ?? []).map((project) => (
                    <option key={project.key ?? project.id} value={project.key ?? ""}>
                      {project.name} ({project.key})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Jira ticket</label>
                <select
                  value={selectedIssueKey}
                  onChange={(e) => setSelectedIssueKey(e.target.value)}
                  disabled={!jiraReady || jiraIssuesQuery.isLoading}
                  className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm"
                >
                  <option value="">Select a ticket</option>
                  {(jiraIssuesQuery.data ?? []).map((issue) => (
                    <option key={issue.key ?? issue.id} value={issue.key ?? ""}>
                      {issue.key}: {issue.summary}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {mode === "jira" && selectedIssue && (
            <div className="mt-4 rounded-md border bg-muted/30 p-3 text-xs">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium">
                    {selectedIssue.key}: {selectedIssue.summary}
                  </p>
                  <p className="mt-1 text-muted-foreground">
                    {selectedIssue.status}
                    {selectedIssue.priority ? ` · ${selectedIssue.priority}` : ""}
                    {selectedIssue.issueType ? ` · ${selectedIssue.issueType}` : ""}
                  </p>
                </div>
                {selectedIssue.url && (
                  <a
                    href={selectedIssue.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    Open
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
              {selectedIssue.description && (
                <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-muted-foreground">
                  {selectedIssue.description}
                </p>
              )}
            </div>
          )}

          <div className="mt-4">
            <label className="text-xs font-medium text-muted-foreground">
              {mode === "jira" ? "Additional instructions (optional)" : "Requirements"}
            </label>
            <textarea
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              rows={4}
              placeholder={
                mode === "jira"
                  ? "Example: Focus on the API layer first, add unit tests, keep changes minimal..."
                  : "Example: Build a task management app with user login, project boards, and due-date reminders..."
              }
              className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
              disabled={startMutation.isPending}
            />
          </div>

          <div className="mt-4">
            <label className="text-xs font-medium text-muted-foreground">Agents for this run</label>
            {agentsQuery.isLoading ? (
              <p className="mt-2 text-xs text-muted-foreground">Loading agents...</p>
            ) : agents.length === 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">
                No agents assigned to you. Ask your team lead to assign agents.
              </p>
            ) : (
              <div className="mt-2 space-y-2">
                {agents.map((agent) => (
                  <label
                    key={agent.agentKey}
                    className="flex cursor-pointer items-center justify-between gap-3 rounded-md border px-3 py-2"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
                        <AgentIcon agentKey={agent.agentKey} className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium">{agent.name}</p>
                        <p className="text-xs text-muted-foreground">Step {agent.stepOrder}</p>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={selectedAgents[agent.agentKey] ?? false}
                      onChange={(e) =>
                        setSelectedAgents((prev) => ({ ...prev, [agent.agentKey]: e.target.checked }))
                      }
                      className="h-4 w-4"
                    />
                  </label>
                ))}
              </div>
            )}
          </div>

          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <button
            type="button"
            disabled={startMutation.isPending || !canStart}
            onClick={() => startMutation.mutate()}
            className="mt-4 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {startMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Run pipeline
          </button>
        </div>
      )}

      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-sm font-semibold">Pipeline runs</h3>
        {runsQuery.isLoading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading runs...</p>
        ) : runs.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">No pipeline runs yet. Start one above.</p>
        ) : (
          <div className="mt-4 flex flex-wrap gap-2">
            {runs.map((run) => (
              <button
                key={run.id}
                type="button"
                onClick={() => setSelectedRunId(run.id)}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-xs capitalize",
                  selectedRunId === run.id ? "border-primary bg-primary/5" : "hover:bg-muted/40"
                )}
              >
                <span className={STATUS_COLORS[run.status] ?? ""}>{run.status}</span>
                <span className="ml-2 text-muted-foreground">{new Date(run.createdAt).toLocaleString()}</span>
              </button>
            ))}
          </div>
        )}

        {detail && detail.status === "awaiting_approval" && (
          <div className="mt-4 rounded-lg border border-purple-200 bg-purple-50 p-4">
            <h4 className="text-sm font-semibold text-purple-900">Plan awaiting your approval</h4>
            <p className="mt-1 text-xs text-purple-800">
              Review the plan below. After approval, agents will write code, open PRs, run tests, and deploy.
            </p>
            {(detail.approvalPlan || detail.artifacts.approval_plan) ? (
              <pre className="mt-3 max-h-64 overflow-auto rounded bg-white/80 p-3 text-xs">
                {JSON.stringify(detail.approvalPlan ?? detail.artifacts.approval_plan, null, 2)}
              </pre>
            ) : null}
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              >
                Approve & continue
              </button>
              <button
                type="button"
                onClick={() => rejectMutation.mutate()}
                disabled={rejectMutation.isPending}
                className="rounded-md border px-4 py-2 text-sm font-medium"
              >
                Reject
              </button>
            </div>
          </div>
        )}

        {detail && (
          <div className="mt-6 space-y-4 border-t pt-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium capitalize">Run status: {detail.status}</p>
                {detail.currentStep && (
                  <p className="text-xs text-muted-foreground">Current step: {detail.currentStep.replace(/_/g, " ")}</p>
                )}
                {detail.errorMessage && <p className="mt-1 text-xs text-red-600">{detail.errorMessage}</p>}
              </div>
              {(detail.status === "pending" || detail.status === "running") && (
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
              )}
            </div>

            <ol className="space-y-2">
              {detail.steps.map((step) => (
                <li key={step.id} className="rounded-md border px-3 py-2.5">
                  <div className="flex items-center gap-3">
                    <StepIcon status={step.status} />
                    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
                      <AgentIcon agentKey={step.stepName} className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium capitalize">{step.stepName.replace(/_/g, " ")}</p>
                      <p className="text-xs capitalize text-muted-foreground">{step.status}</p>
                      {step.errorMessage && (
                        <p className="mt-0.5 text-xs text-red-600">{step.errorMessage}</p>
                      )}
                    </div>
                    <span className="text-xs text-muted-foreground">#{step.stepOrder}</span>
                  </div>
                  {step.logs[0]?.outputJson && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs text-primary">View output</summary>
                      <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted p-2 text-xs">
                        {JSON.stringify(step.logs[0].outputJson, null, 2)}
                      </pre>
                    </details>
                  )}
                </li>
              ))}
            </ol>

            {Object.keys(detail.artifacts).length > 0 && (
              <div>
                <h4 className="text-sm font-semibold">Artifacts</h4>
                <div className="mt-2 space-y-2">
                  {Object.entries(detail.artifacts).map(([key, value]) => (
                    <details key={key} className="rounded-md border px-3 py-2">
                      <summary className="cursor-pointer text-sm font-medium capitalize">{key}</summary>
                      <pre className="mt-2 max-h-64 overflow-auto text-xs">{JSON.stringify(value, null, 2)}</pre>
                    </details>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
