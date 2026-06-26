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

const STATUS_OPTIONS = ["draft", "active", "paused", "completed", "archived"];

export function CompanyProjectDetailPage() {
  const { projectId } = useParams<{ slug: string; projectId: string }>();
  const queryClient = useQueryClient();
  const canWrite = true;

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
    <div className="mx-auto max-w-4xl space-y-6">
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

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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

      <div className="rounded-lg border bg-card p-6">
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
                  <div className="flex gap-2">
                    <input
                      value={repoUrl}
                      onChange={(e) => setRepoUrl(e.target.value)}
                      placeholder="https://github.com/org/repo"
                      className="h-9 flex-1 rounded-md border bg-background px-3 text-sm"
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

      {projectId && <ProjectAgentsPanel projectId={projectId} />}

      {projectId && <ProjectPipelinePanel projectId={projectId} />}
    </div>
  );
}
