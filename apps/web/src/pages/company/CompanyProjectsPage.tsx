import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Plus } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";

export function CompanyProjectsPage() {
  const { slug } = useParams<{ slug: string }>();
  const { company } = useAuth();
  const canWrite = company?.role !== "viewer";

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["company-projects"],
    queryFn: companyApi.getProjects,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Projects"
        description="AI automation projects for your company workspace."
        actions={
          canWrite ? (
            <Link
              to={`/c/${slug}/projects/new`}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              <Plus className="h-4 w-4" />
              New project
            </Link>
          ) : undefined
        }
      />

      {(data ?? []).length === 0 ? (
        <div className="rounded-lg border border-dashed p-10 text-center">
          <p className="text-sm text-muted-foreground">No projects yet.</p>
          {canWrite && (
            <Link
              to={`/c/${slug}/projects/new`}
              className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-primary"
            >
              <Plus className="h-4 w-4" />
              Create first project
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {(data ?? []).map((project) => (
            <Link
              key={project.id}
              to={`/c/${slug}/projects/${project.id}`}
              className="flex items-center justify-between rounded-lg border px-4 py-3 hover:bg-muted/20"
            >
              <div>
                <p className="text-sm font-medium">{project.name}</p>
                <p className="text-xs capitalize text-muted-foreground">
                  {project.status}
                  {project.frontendStack || project.backendStack
                    ? ` · ${[project.frontendStack, project.backendStack].filter(Boolean).join(" + ")}`
                    : ""}
                  {project.createdByName ? ` · ${project.createdByName}` : ""}
                </p>
              </div>
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
