import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";

const STATUS_OPTIONS = ["draft", "active", "paused", "completed", "archived"];

export function CompanyProjectDetailPage() {
  const { slug, projectId } = useParams<{ slug: string; projectId: string }>();
  const { company } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = company?.role !== "viewer";

  const projectQuery = useQuery({
    queryKey: ["company-project", projectId],
    queryFn: () => companyApi.getProject(projectId!),
    enabled: !!projectId,
  });

  const runsQuery = useQuery({
    queryKey: ["company-project-runs", projectId],
    queryFn: () => companyApi.getProjectRuns(projectId!),
    enabled: !!projectId,
  });

  const statusMutation = useMutation({
    mutationFn: (status: string) => companyApi.updateProject(projectId!, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["company-project", projectId] });
      queryClient.invalidateQueries({ queryKey: ["company-projects"] });
    },
  });

  if (projectQuery.isLoading) return <LoadingState />;
  if (projectQuery.isError || !projectQuery.data) {
    return <ErrorState message="Project not found" />;
  }

  const project = projectQuery.data;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link
        to={`/c/${slug}/projects`}
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
            <dd>{project.vcsProvider ?? "—"}</dd>
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

      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-sm font-semibold">Pipeline runs</h3>
        {runsQuery.isLoading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading runs...</p>
        ) : (runsQuery.data ?? []).length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            No pipeline runs yet. AI pipeline execution will be available in a future release.
          </p>
        ) : (
          <div className="mt-4 space-y-2">
            {(runsQuery.data ?? []).map((run) => (
              <div key={run.id} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                <span className="capitalize">{run.status}</span>
                <span className="text-muted-foreground">{new Date(run.createdAt).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
