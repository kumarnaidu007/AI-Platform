import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { FolderKanban, Plug, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { StatCard } from "@/components/admin/StatCard";
import { ConnectionStatusBadge } from "@/components/admin/ConnectionStatusBadge";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";

export function UserDashboardPage() {
  const { slug } = useParams<{ slug: string }>();
  const { user } = useAuth();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["user-dashboard"],
    queryFn: companyApi.getUserDashboard,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const pendingIntegrations = (data?.integrationStatus ?? []).filter((i) => !i.isConnected);

  return (
    <div className="space-y-8">
      <PageHeader
        title={`Hello, ${user?.fullName?.split(" ")[0] ?? "there"}`}
        description={`Your workspace at ${data?.companyName} · ${data?.role}`}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="My projects" value={data?.myProjectsCount ?? 0} icon={FolderKanban} />
        <StatCard
          label="Integrations connected"
          value={`${data?.integrationsConnected ?? 0}/${data?.integrationsAssigned ?? 0}`}
          icon={Plug}
        />
        <StatCard label="AI services available" value={data?.servicesEnabled ?? 0} icon={Sparkles} />
        <StatCard label="Company projects" value={data?.companyProjectsCount ?? 0} icon={FolderKanban} />
      </div>

      {pendingIntegrations.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-medium text-amber-900">Action needed: connect your integrations</p>
          <ul className="mt-2 space-y-1">
            {pendingIntegrations.map((item) => (
              <li key={item.integrationKey} className="flex items-center justify-between text-sm">
                <span>{item.name}</span>
                <Link
                  to={`/c/${slug}/integrations/${item.integrationKey}`}
                  className="font-medium text-primary hover:underline"
                >
                  Connect now
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border bg-card p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">My integrations</h2>
            <Link to={`/c/${slug}/integrations`} className="text-sm text-primary hover:underline">
              View all
            </Link>
          </div>
          {(data?.integrationStatus ?? []).length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">
              No integrations assigned yet. Ask your company admin to grant access.
            </p>
          ) : (
            <div className="mt-4 space-y-2">
              {(data?.integrationStatus ?? []).map((item) => (
                <div key={item.integrationKey} className="flex items-center justify-between rounded-md border px-3 py-2">
                  <span className="text-sm font-medium">{item.name}</span>
                  <ConnectionStatusBadge status={item.connectionStatus} />
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-lg border bg-card p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">Recent projects</h2>
            <Link to={`/c/${slug}/projects`} className="text-sm text-primary hover:underline">
              View all
            </Link>
          </div>
          {(data?.recentProjects ?? []).length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">
              No projects yet.{" "}
              <Link to={`/c/${slug}/projects/new`} className="text-primary hover:underline">
                Create your first project
              </Link>
            </p>
          ) : (
            <div className="mt-4 space-y-2">
              {(data?.recentProjects ?? []).map((project) => (
                <Link
                  key={project.id}
                  to={`/c/${slug}/projects/${project.id}`}
                  className="block rounded-md border px-3 py-2 hover:bg-muted/30"
                >
                  <p className="text-sm font-medium">{project.name}</p>
                  <p className="text-xs capitalize text-muted-foreground">
                    {project.status}
                    {project.createdByName ? ` · ${project.createdByName}` : ""}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
