import { Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { githubApi } from "@/services/githubApi";
import { getApiErrorMessage } from "@/services/authApi";
import { ProjectAgentsPanel } from "@/components/company/ProjectAgentsPanel";
import { ProjectPipelinePanel } from "@/components/company/ProjectPipelinePanel";
import { cn } from "@/lib/utils";

const STATUS_OPTIONS = ["draft", "active", "paused", "completed", "archived"];

type ProjectTab = "overview" | "agents" | "pipeline";

export function CompanyProjectDetailPage() {
  const { projectId } = useParams<{ slug: string; projectId: string }>();
  const queryClient = useQueryClient();
  const canWrite = true;
  const [tab, setTab] = useState<ProjectTab>("overview");

  const projectQuery = useQuery({
    queryKey: ["company-project", projectId],
    queryFn: () => companyApi.getProject(projectId!),
    enabled: !!projectId,
  });

  const statusMutation = useMutation({
    mutationFn: (status: string) => companyApi.updateProject(projectId!, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["company-project", projectId] });
      queryClient.invalidateQueries({ queryKey: ["company-projects"] });
    },
  });

  const [repoUrl, setRepoUrl] = useState("");
  const [repoMessage, setRepoMessage] = useState<string | null>(null);

  const repoMutation = useMutation({
    mutationFn: (url: string) => companyApi.updateProject(projectId!, { repoUrl: url }),
    onSuccess: () => {
      setRepoMessage("Repository URL saved");
      queryClient.invalidateQueries({ queryKey: ["company-project", projectId] });
    },
    onError: (err: unknown) => setRepoMessage(getApiErrorMessage(err, "Failed to save repository")),
  });

  const verifyRepoMutation = useMutation({
    mutationFn: () => githubApi.verifyRepo(repoUrl),
    onSuccess: (info) => setRepoMessage(`Verified — default branch: ${info.defaultBranch}`),
    onError: (err: unknown) => setRepoMessage(getApiErrorMessage(err, "Could not verify repository")),
  });

  useEffect(() => {
    setRepoUrl(projectQuery.data?.repoUrl ?? "");
  }, [projectQuery.data?.repoUrl]);

  if (projectQuery.isLoading) return <LoadingState />;
  if (projectQuery.isError || !projectQuery.data) {
    return <ErrorState message="Project not found" />;
  }

  const project = projectQuery.data;

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <Link
        to={`/workspace/projects`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to projects
      </Link>

      <PageHeader
        title={project.name}
        description={project.description || "No description"}
        actions={
          canWrite ? (
            <select
              value={project.status}
              onChange={(e) => statusMutation.mutate(e.target.value)}
              className="h-9 rounded-md border bg-background px-3 text-sm capitalize"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          ) : (
            <span className="rounded-full bg-muted px-3 py-1 text-xs font-medium capitalize">{project.status}</span>
          )
        }
      />

      <div className="flex flex-wrap gap-1 border-b pb-1">
        {(
          [
            ["overview", "Overview"],
            ["agents", "Agent pipeline"],
            ["pipeline", "Runs & start"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={cn(
              "rounded-t-md px-4 py-2 text-sm font-medium",
              tab === key
                ? "border border-b-0 border-border bg-card text-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border bg-card p-4">
              <p className="text-xs text-muted-foreground">Created by</p>
              <p className="mt-1 text-sm font-medium">{project.createdByName ?? "—"}</p>
            </div>
            <div className="rounded-lg border bg-card p-4">
              <p className="text-xs text-muted-foreground">Stack</p>
              <p className="mt-1 text-sm font-medium">
                {[project.frontendStack, project.backendStack].filter(Boolean).join(" + ") || "—"}
              </p>
            </div>
            <div className="rounded-lg border bg-card p-4">
              <p className="text-xs text-muted-foreground">Pipeline runs</p>
              <p className="mt-1 text-sm font-medium">{project.pipelineRunsCount}</p>
            </div>
            <div className="rounded-lg border bg-card p-4">
              <p className="text-xs text-muted-foreground">Active runs</p>
              <p className="mt-1 text-sm font-medium">{project.activePipelineRuns}</p>
            </div>
          </div>

          <div className="rounded-lg border bg-card p-5">
            <h3 className="text-sm font-semibold">Configuration</h3>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted-foreground">Database</dt>
                <dd>{project.dbType ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">VCS</dt>
                <dd>{project.vcsProvider ?? "github"}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-muted-foreground">Repository</dt>
                <dd className="mt-1 space-y-2">
                  {canWrite ? (
                    <>
                      <div className="flex flex-wrap gap-2">
                        <input
                          value={repoUrl}
                          onChange={(e) => setRepoUrl(e.target.value)}
                          placeholder="https://github.com/org/repo"
                          className="h-9 min-w-[200px] flex-1 rounded-md border bg-background px-3 text-sm"
                        />
                        <button
                          type="button"
                          onClick={() => verifyRepoMutation.mutate()}
                          disabled={!repoUrl.trim() || verifyRepoMutation.isPending}
                          className="rounded-md border px-3 text-xs font-medium"
                        >
                          Verify
                        </button>
                        <button
                          type="button"
                          onClick={() => repoMutation.mutate(repoUrl)}
                          disabled={repoMutation.isPending}
                          className="rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground"
                        >
                          Save
                        </button>
                      </div>
                      {repoMessage && <p className="text-xs text-muted-foreground">{repoMessage}</p>}
                    </>
                  ) : (
                    project.repoUrl ?? "—"
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">PM tool</dt>
                <dd>{project.pmTool ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Token budget / mo</dt>
                <dd>{project.monthlyTokenBudgetUsd != null ? `$${project.monthlyTokenBudgetUsd}` : "—"}</dd>
              </div>
            </dl>
          </div>
        </>
      )}

      {tab === "agents" && projectId && <ProjectAgentsPanel projectId={projectId} />}

      {tab === "pipeline" && projectId && <ProjectPipelinePanel projectId={projectId} />}
    </div>
  );
}
