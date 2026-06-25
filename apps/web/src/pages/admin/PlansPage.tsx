import { useQuery } from "@tanstack/react-query";
import { CreditCard, DollarSign, FolderKanban, GitBranch } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { DataTable, TableCell, TableRow } from "@/components/admin/DataTable";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";

function formatUsd(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

export function PlansPage() {
  const { data: plans, isLoading, isError, error } = useQuery({ queryKey: ["plans"], queryFn: adminApi.getPlans });
  const { data: integrations } = useQuery({ queryKey: ["integrations"], queryFn: adminApi.getIntegrations });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const integrationName = (key: string) => integrations?.find((i) => i.integrationKey === key)?.name ?? key;

  return (
    <div className="space-y-8">
      <PageHeader title="Plans & Limits" description="Subscription tiers linked to platform integrations." />

      <div className="grid gap-4 md:grid-cols-3">
        {(plans ?? []).map((plan) => (
          <div key={plan.id} className="rounded-lg border bg-card p-5">
            <h3 className="text-lg font-semibold">{plan.name}</h3>
            <p className="mt-0.5 text-sm text-muted-foreground">{plan.companiesCount} companies</p>
            <dl className="mt-5 space-y-3 text-sm">
              <div className="flex justify-between"><dt className="flex items-center gap-2 text-muted-foreground"><FolderKanban className="h-4 w-4" />Max projects</dt><dd className="font-medium">{plan.maxProjects}</dd></div>
              <div className="flex justify-between"><dt className="flex items-center gap-2 text-muted-foreground"><GitBranch className="h-4 w-4" />Parallel pipelines</dt><dd className="font-medium">{plan.maxParallelPipelines}</dd></div>
              <div className="flex justify-between"><dt className="flex items-center gap-2 text-muted-foreground"><DollarSign className="h-4 w-4" />Token budget</dt><dd className="font-medium">{formatUsd(plan.monthlyTokenBudgetUsd)}</dd></div>
            </dl>
            <div className="mt-4 border-t pt-4">
              <p className="text-xs font-medium text-muted-foreground">Included integrations ({plan.integrationKeys?.length ?? 0})</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {(plan.integrationKeys ?? []).map((key) => (
                  <span key={key} className="rounded bg-muted px-2 py-0.5 text-xs">{integrationName(key)}</span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      <DataTable headers={["Plan", "Max Projects", "Pipelines", "Budget", "Companies", "Integrations"]}>
        {(plans ?? []).map((plan) => (
          <TableRow key={plan.id}>
            <TableCell className="font-medium"><span className="inline-flex items-center gap-2"><CreditCard className="h-4 w-4" />{plan.name}</span></TableCell>
            <TableCell>{plan.maxProjects}</TableCell>
            <TableCell>{plan.maxParallelPipelines}</TableCell>
            <TableCell>{formatUsd(plan.monthlyTokenBudgetUsd)}</TableCell>
            <TableCell>{plan.companiesCount}</TableCell>
            <TableCell>{plan.integrationKeys?.length ?? 0}</TableCell>
          </TableRow>
        ))}
      </DataTable>
    </div>
  );
}
