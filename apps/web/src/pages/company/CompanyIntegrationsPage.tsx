import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { ConnectionStatusBadge } from "@/components/admin/ConnectionStatusBadge";
import { IntegrationIcon } from "@/components/admin/IntegrationIcon";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";
import { categoryLabels } from "@/types/platform";

export function CompanyIntegrationsPage() {
  const { slug } = useParams<{ slug: string }>();
  const { company } = useAuth();
  const isAdmin = company?.role === "admin";

  const catalogQuery = useQuery({
    queryKey: ["company-integration-catalog"],
    queryFn: companyApi.getIntegrationCatalog,
    enabled: isAdmin,
  });

  const myQuery = useQuery({
    queryKey: ["company-my-integrations"],
    queryFn: companyApi.getMyIntegrations,
  });

  if (catalogQuery.isLoading || myQuery.isLoading) return <LoadingState />;
  if (myQuery.isError) return <ErrorState message={String(myQuery.error)} />;

  const catalog = catalogQuery.data ?? [];
  const myIntegrations = myQuery.data ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Integrations"
        description={
          isAdmin
            ? "Assign integrations to team members — each employee connects with their own credentials."
            : "Connect your assigned integrations using your personal work account credentials."
        }
      />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">My integrations</h2>
        {myIntegrations.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            {isAdmin
              ? "No integrations assigned to you yet. Assign integrations from the Team page."
              : "No integrations assigned yet. Ask your company admin to grant access."}
          </div>
        ) : (
          <div className="space-y-2">
            {myIntegrations.map((item) => (
              <div
                key={item.integrationKey}
                className="flex items-center justify-between gap-4 rounded-lg border px-4 py-3 hover:bg-muted/20"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <IntegrationIcon integrationKey={item.integrationKey} className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.name}</p>
                    <p className="text-xs capitalize text-muted-foreground">{categoryLabels[item.category]}</p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <ConnectionStatusBadge status={item.connectionStatus} />
                  <Link
                    to={`/c/${slug}/integrations/${item.integrationKey}`}
                    className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                  >
                    {item.isConnected ? "Manage" : "Connect"}
                    <ChevronRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {isAdmin && catalog.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Granted to your company</h2>
          <p className="text-sm text-muted-foreground">
            These integrations are available for assignment. Go to{" "}
            <Link to={`/c/${slug}/team`} className="text-primary hover:underline">
              Team
            </Link>{" "}
            to assign them to employees — they will connect with their own accounts.
          </p>
          <div className="space-y-2">
            {catalog.map((item) => (
              <div key={item.integrationKey} className="flex items-center gap-3 rounded-lg border px-4 py-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <IntegrationIcon integrationKey={item.integrationKey} className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium">{item.name}</p>
                  <p className="text-xs capitalize text-muted-foreground">{categoryLabels[item.category]}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
