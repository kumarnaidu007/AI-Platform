import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, Database, Server, XCircle } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { StatCard } from "@/components/admin/StatCard";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";

export function SystemHealthPage() {
  const { data, isLoading, isError, error } = useQuery({ queryKey: ["system-health"], queryFn: adminApi.getSystemHealth });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const statusIcon = { healthy: CheckCircle2, degraded: Clock, down: XCircle };

  return (
    <div className="space-y-8">
      <PageHeader title="System Health" description="Infrastructure and platform services status." />
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Healthy" value={data!.healthy} icon={CheckCircle2} />
        <StatCard label="Degraded" value={data!.degraded} icon={Clock} />
        <StatCard label="Down" value={data!.down} icon={XCircle} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {data!.services.map((service) => {
          const Icon = statusIcon[service.status];
          const isDb = service.name === "PostgreSQL";
          return (
            <div key={service.name} className="rounded-lg border bg-card p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="rounded-md bg-muted p-2">{isDb ? <Database className="h-5 w-5" /> : <Server className="h-5 w-5" />}</div>
                  <div><h3 className="font-semibold">{service.name}</h3><p className="text-sm text-muted-foreground">{service.message}</p></div>
                </div>
                <StatusBadge status={service.status} />
              </div>
              <div className="mt-4 flex items-center justify-between border-t pt-4 text-sm">
                <span className="flex items-center gap-1.5 text-muted-foreground"><Icon className="h-4 w-4" />{service.status}</span>
                {service.latencyMs !== null && <span className="font-mono text-xs">{service.latencyMs}ms</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
