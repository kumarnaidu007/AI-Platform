import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { ExternalLink, Loader2, Ticket } from "lucide-react";
import { jiraApi } from "@/services/jiraApi";
import { intakeApi } from "@/services/intakeApi";
import { companyApi } from "@/services/companyApi";
import { getApiErrorMessage } from "@/services/authApi";
import { useAuth } from "@/context/AuthContext";
import { isTeamLead } from "@/types/roles";
import { cn } from "@/lib/utils";

const INTAKE_STATUS_LABEL: Record<string, string> = {
  synced: "Ready to clarify",
  analyzing: "Analyzing…",
  awaiting_answers: "Questions pending",
  drafting_specs: "Generating specs…",
  awaiting_review: "Review specs",
  locked: "Locked",
  awaiting_plan_approval: "Confirm plan",
  approved: "Ready to implement",
  implementing: "Implementing",
  implementation_failed: "Implementation failed",
  awaiting_pr_review: "PR review",
  completed: "Completed",
  failed: "Failed",
};

export function CompanyJiraPortalPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { company } = useAuth();
  const teamLead = isTeamLead(company?.role);
  const [projectKey, setProjectKey] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const jiraStatus = useQuery({ queryKey: ["jira-status"], queryFn: () => jiraApi.getStatus() });
  const projects = useQuery({ queryKey: ["jira-projects"], queryFn: () => jiraApi.listProjects(), enabled: jiraStatus.data?.isConnected });
  const platformProjects = useQuery({ queryKey: ["company-projects"], queryFn: () => companyApi.getProjects() });
  const portal = useQuery({
    queryKey: ["jira-portal", projectKey],
    queryFn: () => intakeApi.getPortal(projectKey || undefined),
    enabled: jiraStatus.data?.isConnected === true,
  });

  const startIntake = useMutation({
    mutationFn: (issueKey: string) =>
      intakeApi.createIntake({
        jiraIssueKey: issueKey,
        projectId: selectedProjectId || undefined,
      }),
    onSuccess: (intake) => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["jira-portal"] });
      navigate(`/workspace/jira/${intake.jiraIssueKey}`);
    },
    onError: (err: unknown) => setError(getApiErrorMessage(err, "Failed to start intake")),
  });

  const planEpic = useMutation({
    mutationFn: (issueKey: string) =>
      intakeApi.planEpic({
        jiraIssueKey: issueKey,
        projectId: selectedProjectId || undefined,
      }),
    onSuccess: (intake) => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["jira-portal"] });
      navigate(`/workspace/jira/${intake.jiraIssueKey}`);
    },
    onError: (err: unknown) => setError(getApiErrorMessage(err, "Failed to start epic planning")),
  });

  const connected = jiraStatus.data?.isConnected === true;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Jira Portal</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {teamLead
            ? "As team lead: plan epics with AI, create Jira subtasks, and hand off to members. Members implement assigned subtasks."
            : "Each ticket gets its own clarification flow — questions, separate specs, your confirmation, then implementation."}
        </p>
      </div>

      {!connected && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          {jiraStatus.data?.message ? (
            <p>{jiraStatus.data.message}</p>
          ) : (
            <p>Connect Jira to load tickets assigned to you.</p>
          )}
          <p className="mt-2">
            Go to{" "}
            <Link to="/workspace/integrations/jira" className="font-medium underline">
              My Integrations → Jira
            </Link>{" "}
            {jiraStatus.data?.connectionStatus === "expired" ? "and reconnect your account." : "to connect."}
          </p>
        </div>
      )}

      {connected && (
        <div className="flex flex-wrap gap-3 rounded-lg border bg-card p-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground">Jira project filter</label>
            <select
              className="mt-1 block rounded-md border bg-background px-3 py-2 text-sm"
              value={projectKey}
              onChange={(e) => setProjectKey(e.target.value)}
            >
              <option value="">All projects</option>
              {(projects.data ?? []).map((p) => (
                <option key={p.key ?? ""} value={p.key ?? ""}>
                  {p.key} — {p.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Link platform project (repo)</label>
            <select
              className="mt-1 block min-w-[220px] rounded-md border bg-background px-3 py-2 text-sm"
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
            >
              <option value="">Select project…</option>
              {(platformProjects.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="rounded-lg border bg-card">
        <div className="border-b px-4 py-3">
          <h2 className="text-sm font-semibold">{teamLead ? "Jira tickets (team backlog)" : "Your Jira tickets"}</h2>
        </div>
        {portal.isLoading ? (
          <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading tickets…
          </div>
        ) : !connected ? (
          <p className="p-8 text-sm text-muted-foreground">Connect Jira to see tickets.</p>
        ) : portal.isError ? (
          <p className="p-8 text-sm text-red-600">
            {getApiErrorMessage(portal.error, "Failed to load Jira tickets")}
          </p>
        ) : (portal.data ?? []).length === 0 ? (
          <p className="p-8 text-sm text-muted-foreground">No tickets found.</p>
        ) : (
          <div className="divide-y">
            {(portal.data ?? []).map((issue) => (
              <div key={issue.key ?? issue.id} className="flex flex-wrap items-center gap-4 px-4 py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Ticket className="h-5 w-5 text-primary" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-semibold">{issue.key}</span>
                    <span className="text-xs text-muted-foreground">{issue.status}</span>
                    {issue.intakeStatus && (
                      <span className="rounded-full bg-muted px-2 py-0.5 text-xs capitalize">
                        {INTAKE_STATUS_LABEL[issue.intakeStatus] ?? issue.intakeStatus.replace(/_/g, " ")}
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-sm">{issue.summary}</p>
                  <p className="text-xs text-muted-foreground">
                    {issue.assignee ? `Assignee: ${issue.assignee}` : "Unassigned"}
                    {issue.priority ? ` · ${issue.priority}` : ""}
                  </p>
                </div>
                <div className="flex gap-2">
                  {issue.url && (
                    <a
                      href={issue.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs"
                    >
                      Jira <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  {issue.intakeId ? (
                    <Link
                      to={`/workspace/jira/${issue.key}`}
                      className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                    >
                      Continue
                    </Link>
                  ) : (
                    <>
                      {teamLead && (
                        <button
                          type="button"
                          disabled={planEpic.isPending || !selectedProjectId}
                          title={!selectedProjectId ? "Select a platform project first" : undefined}
                          onClick={() => issue.key && planEpic.mutate(issue.key)}
                          className="rounded-md border border-primary px-3 py-1.5 text-xs font-medium text-primary"
                        >
                          Plan epic
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={startIntake.isPending || !selectedProjectId}
                        title={!selectedProjectId ? "Select a platform project first" : undefined}
                        onClick={() => issue.key && startIntake.mutate(issue.key)}
                        className={cn(
                          "rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
                        )}
                      >
                        Start clarification
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
