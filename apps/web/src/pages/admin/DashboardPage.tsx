import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Building2, DollarSign, GitBranch, Plug, Sparkles, Users, Zap } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { StatCard } from "@/components/admin/StatCard";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { ConnectionStatusBadge } from "@/components/admin/ConnectionStatusBadge";
import { DataTable, TableCell, TableRow } from "@/components/admin/DataTable";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";

function formatUsd(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

function formatTime(iso: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function DashboardPage() {
  const navigate = useNavigate();
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: adminApi.getDashboard });
  const activity = useQuery({ queryKey: ["pipeline-activity"], queryFn: adminApi.getPipelineActivity });
  const companies = useQuery({ queryKey: ["companies"], queryFn: adminApi.getCompanies });
  const integrations = useQuery({ queryKey: ["integrations"], queryFn: adminApi.getIntegrations });

  if (dashboard.isLoading) return <LoadingState />;
  if (dashboard.isError) return <ErrorState message={String(dashboard.error)} />;

  const { platformStats, metrics } = dashboard.data!;
  const recentCompanies = [...(companies.data ?? [])].slice(0, 5);
  const needsAttention = (integrations.data ?? []).filter(
    (i) => i.isEnabled && (i.connectionStatus === "error" || i.connectionStatus === "not_configured")
  ).slice(0, 5);

  return (
    <div className="space-y-8">
      <PageHeader title="Platform Dashboard" description="Platform setup, integrations, and tenant overview." />

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">Platform Setup</h2>
          <Link to="/admin/integrations" className="text-sm text-primary hover:underline">
            Manage integrations
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Integrations Connected"
            value={`${platformStats.connectedIntegrations}/${platformStats.enabledIntegrations}`}
            subtext={`${platformStats.notConfiguredIntegrations} need configuration`}
            icon={Plug}
          />
          <StatCard label="Connection Errors" value={platformStats.errorIntegrations} subtext="Fix in integrations catalog" icon={AlertTriangle} />
          <StatCard
            label="AI Services Active"
            value={`${platformStats.servicesEnabled}/${platformStats.totalServices}`}
            icon={Sparkles}
          />
          <StatCard label="Total Companies" value={metrics.totalCompanies} subtext={`${metrics.activeCompanies} active tenants`} icon={Building2} />
        </div>
      </div>

      {needsAttention.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-base font-semibold">Integrations needing attention</h2>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {needsAttention.map((i) => (
              <Link
                key={i.id}
                to={`/admin/integrations/${i.integrationKey}`}
                className="flex items-center justify-between rounded-lg border bg-card px-4 py-3 hover:bg-accent/50"
              >
                <span className="text-sm font-medium">{i.name}</span>
                <ConnectionStatusBadge status={i.connectionStatus} />
              </Link>
            ))}
          </div>
        </div>
      )}

      <div>
        <h2 className="mb-3 text-base font-semibold">Tenant Activity</h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Trial Companies" value={metrics.trialCompanies} subtext={`${metrics.suspendedCompanies} suspended`} icon={Users} />
          <StatCard label="Monthly Platform Cost" value={formatUsd(metrics.monthlyPlatformCostUsd)} subtext={`${metrics.monthlyTokenUsageM}M tokens used`} icon={DollarSign} />
          <StatCard label="Failed Pipelines (24h)" value={metrics.failedPipelines24h} icon={AlertTriangle} />
          <StatCard label="Active Pipelines" value={metrics.activePipelines} icon={GitBranch} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 className="text-base font-semibold">Live Pipeline Activity</h2>
          {(activity.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No pipeline runs yet.</p>
          ) : (
            <DataTable headers={["Company", "Project", "Step", "Status", "Started"]}>
              {(activity.data ?? []).map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">{p.companyName}</TableCell>
                  <TableCell>{p.projectName}</TableCell>
                  <TableCell><code className="rounded bg-muted px-1.5 py-0.5 text-xs">{p.step}</code></TableCell>
                  <TableCell><StatusBadge status={p.status} /></TableCell>
                  <TableCell className="text-muted-foreground">{formatTime(p.startedAt)}</TableCell>
                </TableRow>
              ))}
            </DataTable>
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">Recent Companies</h2>
            <Link to="/admin/companies" className="text-sm text-primary hover:underline">View all</Link>
          </div>
          {recentCompanies.length === 0 ? (
            <p className="text-sm text-muted-foreground">No companies yet. Create one from the Companies page.</p>
          ) : (
            <DataTable headers={["Company", "Plan", "Users", "Status", "Usage"]}>
              {recentCompanies.map((c) => (
                <TableRow key={c.id} onClick={() => navigate(`/admin/companies/${c.id}`)}>
                  <TableCell>
                    <p className="font-medium">{c.name}</p>
                    <p className="text-xs text-muted-foreground">{c.slug}</p>
                  </TableCell>
                  <TableCell>{c.planName}</TableCell>
                  <TableCell>{c.usersCount}</TableCell>
                  <TableCell><StatusBadge status={c.status} /></TableCell>
                  <TableCell>{formatUsd(c.monthlyUsageUsd)}</TableCell>
                </TableRow>
              ))}
            </DataTable>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
        <div className="flex gap-3">
          <Zap className="h-5 w-5 shrink-0 text-amber-600" />
          <div>
            <p className="text-sm font-medium text-amber-900">Platform status</p>
            <p className="mt-0.5 text-sm text-amber-800">
              {platformStats.notConfiguredIntegrations} integration(s) need platform OAuth configuration before companies can connect.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
