import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban, DollarSign, FolderKanban, GitBranch, Mail, Plug, Sparkles, User, Users } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { StatCard } from "@/components/admin/StatCard";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { DataTable, TableCell, TableRow } from "@/components/admin/DataTable";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import type { CompanyIntegrationAccess, CompanyServiceAccess } from "@/types/admin";

function formatUsd(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

function AccessToggle({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange?: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange?.(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"
      } ${checked ? "bg-primary" : "bg-muted"}`}
    >
      <span
        className={`inline-block h-5 w-5 translate-y-0.5 rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-5" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

function IntegrationsAccessSection({ companyId }: { companyId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["company-integrations-access", companyId],
    queryFn: () => adminApi.getCompanyIntegrationsAccess(companyId),
  });

  const mutation = useMutation({
    mutationFn: (integrations: CompanyIntegrationAccess[]) =>
      adminApi.updateCompanyIntegrationsAccess(
        companyId,
        integrations.map((i) => ({ integrationKey: i.integrationKey, isEnabled: i.isEnabled }))
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["company-integrations-access", companyId] }),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const enabledCount = (data ?? []).filter((i) => i.isEnabled && i.assignable).length;
  const assignable = (data ?? []).filter((i) => i.assignable);
  const blocked = (data ?? []).filter((i) => !i.assignable);

  return (
    <div className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Plug className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Integration Access</h3>
        </div>
        <span className="text-xs text-muted-foreground">{enabledCount} enabled</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Only integrations connected in Platform → Integrations can be granted to companies.
      </p>
      <div className="mt-4 space-y-2">
        {assignable.map((item) => (
          <div
            key={item.integrationKey}
            className="flex items-center justify-between gap-3 rounded-md border px-3 py-2.5"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium">{item.name}</p>
              <p className="text-xs text-muted-foreground capitalize">{item.category} · connected</p>
            </div>
            <AccessToggle
              checked={item.isEnabled}
              disabled={mutation.isPending}
              onChange={(isEnabled) => {
                const next = (data ?? []).map((row) =>
                  row.integrationKey === item.integrationKey ? { ...row, isEnabled } : row
                );
                mutation.mutate(next);
              }}
            />
          </div>
        ))}
        {blocked.length > 0 && (
          <div className="pt-2">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Not assignable (configure platform first)</p>
            {blocked.map((item) => (
              <div
                key={item.integrationKey}
                className="mb-2 flex items-center justify-between gap-3 rounded-md border border-dashed bg-muted/30 px-3 py-2.5 opacity-70"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">{item.name}</p>
                  <p className="text-xs text-muted-foreground capitalize">
                    {item.category} · {item.connectionStatus.replace(/_/g, " ")}
                  </p>
                </div>
                <AccessToggle checked={false} disabled />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ServicesAccessSection({ companyId }: { companyId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["company-services-access", companyId],
    queryFn: () => adminApi.getCompanyServicesAccess(companyId),
  });

  const mutation = useMutation({
    mutationFn: (services: CompanyServiceAccess[]) =>
      adminApi.updateCompanyServicesAccess(
        companyId,
        services.map((s) => ({ serviceKey: s.serviceKey, isEnabled: s.isEnabled }))
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["company-services-access", companyId] }),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const enabledCount = (data ?? []).filter((s) => s.isEnabled && s.assignable).length;
  const assignable = (data ?? []).filter((s) => s.assignable);
  const blocked = (data ?? []).filter((s) => !s.assignable);

  return (
    <div className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">AI Services Access</h3>
        </div>
        <span className="text-xs text-muted-foreground">{enabledCount} enabled</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Only AI services enabled and configured in Platform → AI Services can be granted.
      </p>
      <div className="mt-4 space-y-2">
        {assignable.map((item) => (
          <div
            key={item.serviceKey}
            className="flex items-center justify-between gap-3 rounded-md border px-3 py-2.5"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium">{item.displayName}</p>
              <p className="text-xs text-muted-foreground">Uses platform credentials</p>
            </div>
            <AccessToggle
              checked={item.isEnabled}
              disabled={mutation.isPending}
              onChange={(isEnabled) => {
                const next = (data ?? []).map((row) =>
                  row.serviceKey === item.serviceKey ? { ...row, isEnabled } : row
                );
                mutation.mutate(next);
              }}
            />
          </div>
        ))}
        {blocked.length > 0 && (
          <div className="pt-2">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Not assignable (configure platform first)</p>
            {blocked.map((item) => (
              <div
                key={item.serviceKey}
                className="mb-2 flex items-center justify-between gap-3 rounded-md border border-dashed bg-muted/30 px-3 py-2.5 opacity-70"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">{item.displayName}</p>
                  <p className="text-xs text-muted-foreground">
                    {!item.platformEnabled && "Disabled platform-wide"}
                    {item.platformEnabled && !item.platformConfigured && "Not configured — add API keys"}
                    {item.platformEnabled && item.platformConfigured && "Unavailable"}
                  </p>
                </div>
                <AccessToggle checked={false} disabled />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data: company, isLoading, isError, error } = useQuery({
    queryKey: ["company", id],
    queryFn: () => adminApi.getCompany(id!),
    enabled: !!id,
  });

  const suspendMutation = useMutation({
    mutationFn: () => adminApi.updateCompany(id!, { status: "suspended" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["company", id] }),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !company) return <ErrorState message={String(error ?? "Not found")} />;

  return (
    <div className="space-y-8">
      <Link to="/admin/companies" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />
        Companies
      </Link>

      <PageHeader
        title={company.name}
        description={`/${company.slug} · ${company.planName} · Created ${company.createdAt}`}
        actions={
          <div className="flex items-center gap-2">
            <a
              href={`/c/${company.slug}/login`}
              target="_blank"
              rel="noreferrer"
              className="rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent"
            >
              Company portal
            </a>
            {company.status !== "suspended" ? (
            <button type="button" onClick={() => suspendMutation.mutate()} className="inline-flex items-center gap-2 rounded-md border border-destructive/30 px-3 py-2 text-sm font-medium text-destructive">
              <Ban className="h-4 w-4" />
              Suspend
            </button>
            ) : null}
          </div>
        }
      />

      <StatusBadge status={company.status} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Users" value={company.usersCount} icon={Users} />
        <StatCard label="Projects" value={company.projectsCount} icon={FolderKanban} />
        <StatCard label="Active Pipelines" value={company.activePipelines} icon={GitBranch} />
        <StatCard label="Monthly Usage" value={formatUsd(company.monthlyUsageUsd)} icon={DollarSign} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border bg-card p-5">
          <h3 className="text-sm font-semibold">Company Admin</h3>
          <div className="mt-4 space-y-3 text-sm">
            {company.adminName ? (
              <>
                <div className="flex items-center gap-3"><User className="h-4 w-4" />{company.adminName}</div>
                <div className="flex items-center gap-3"><Mail className="h-4 w-4" />{company.adminEmail}</div>
              </>
            ) : (
              <p className="text-muted-foreground">No admin user created yet.</p>
            )}
          </div>
        </div>
        <div className="rounded-lg border bg-card p-5">
          <h3 className="text-sm font-semibold">Limits Override</h3>
          <p className="mt-4 text-sm text-muted-foreground">Using default plan limits.</p>
        </div>
      </div>

      {id && (
        <div className="grid gap-6 lg:grid-cols-2">
          <IntegrationsAccessSection companyId={id} />
          <ServicesAccessSection companyId={id} />
        </div>
      )}

      <div className="space-y-3">
        <h2 className="text-base font-semibold">Recent Projects</h2>
        {company.recentProjects.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">No projects yet.</div>
        ) : (
          <DataTable headers={["Project", "Stack", "Status"]}>
            {company.recentProjects.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-medium">{p.name}</TableCell>
                <TableCell className="text-muted-foreground">{p.stack}</TableCell>
                <TableCell><StatusBadge status={p.status} /></TableCell>
              </TableRow>
            ))}
          </DataTable>
        )}
      </div>
    </div>
  );
}
