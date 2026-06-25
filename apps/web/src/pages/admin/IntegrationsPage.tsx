import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, Plug, PlugZap, Settings2, AlertCircle, Layers } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { ConnectionStatusBadge } from "@/components/admin/ConnectionStatusBadge";
import { IntegrationIcon } from "@/components/admin/IntegrationIcon";
import { StatCard } from "@/components/admin/StatCard";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import { authTypeLabels, categoryLabels, type IntegrationCategory } from "@/types/platform";

const categories: IntegrationCategory[] = ["vcs", "pm", "requirements", "notify", "deploy"];

export function IntegrationsPage() {
  const [categoryFilter, setCategoryFilter] = useState<IntegrationCategory | "all">("all");
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["integrations"],
    queryFn: adminApi.getIntegrations,
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    if (categoryFilter === "all") return data;
    return data.filter((i) => i.category === categoryFilter);
  }, [data, categoryFilter]);

  const stats = useMemo(() => {
    const enabled = (data ?? []).filter((i) => i.isEnabled);
    return {
      connected: enabled.filter((i) => i.connectionStatus === "connected").length,
      enabled: enabled.length,
      notConfigured: enabled.filter((i) => i.connectionStatus === "not_configured").length,
      errors: enabled.filter((i) => i.connectionStatus === "error").length,
      total: (data ?? []).length,
    };
  }, [data]);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Integrations Catalog"
        description="Platform OAuth apps and connection templates. Companies connect their own accounts through these."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Enabled Integrations" value={`${stats.connected}/${stats.enabled}`} subtext="connected of enabled" icon={PlugZap} />
        <StatCard label="Not Configured" value={stats.notConfigured} icon={Plug} />
        <StatCard label="Connection Errors" value={stats.errors} icon={AlertCircle} />
        <StatCard label="Total in Catalog" value={stats.total} icon={Layers} />
      </div>

      <div className="flex flex-wrap gap-1 rounded-md border p-1">
        {(["all", ...categories] as const).map((cat) => (
          <button
            key={cat}
            type="button"
            onClick={() => setCategoryFilter(cat)}
            className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
              categoryFilter === cat ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"
            }`}
          >
            {cat === "all" ? "All" : categoryLabels[cat]}
          </button>
        ))}
      </div>

      {categoryFilter === "all" ? (
        <div className="space-y-8">
          {categories.map((cat) => {
            const items = (data ?? []).filter((i) => i.category === cat);
            if (!items.length) return null;
            return (
              <section key={cat} className="space-y-3">
                <h2 className="text-base font-semibold">{categoryLabels[cat]}</h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {items.map((integration) => (
                    <IntegrationCard key={integration.id} integration={integration} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((integration) => (
            <IntegrationCard key={integration.id} integration={integration} />
          ))}
        </div>
      )}

      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
        <div className="flex gap-3">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-blue-600" />
          <p className="text-sm text-blue-800">
            You register OAuth apps here. Companies later authorize <strong>their own</strong> accounts through these apps.
          </p>
        </div>
      </div>
    </div>
  );
}

function IntegrationCard({ integration }: { integration: NonNullable<Awaited<ReturnType<typeof adminApi.getIntegrations>>[0]> }) {
  return (
    <div className={`rounded-lg border bg-card p-5 ${!integration.isEnabled ? "opacity-60" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
            <IntegrationIcon integrationKey={integration.integrationKey} className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-semibold">{integration.name}</h3>
            <p className="text-xs text-muted-foreground">{authTypeLabels[integration.authType]}</p>
          </div>
        </div>
        <ConnectionStatusBadge status={integration.isEnabled ? integration.connectionStatus : "disabled"} />
      </div>
      <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{integration.description}</p>
      {integration.lastErrorMessage && (
        <p className="mt-2 rounded bg-red-50 px-2 py-1 text-xs text-red-700">{integration.lastErrorMessage}</p>
      )}
      <div className="mt-4 flex items-center gap-2 border-t pt-4">
        <Link
          to={`/admin/integrations/${integration.integrationKey}`}
          className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Settings2 className="h-3.5 w-3.5" />
          Configure
        </Link>
        {integration.documentationUrl && (
          <a href={integration.documentationUrl} target="_blank" rel="noopener noreferrer" className="inline-flex rounded-md border p-2 text-muted-foreground hover:bg-accent">
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>
    </div>
  );
}
