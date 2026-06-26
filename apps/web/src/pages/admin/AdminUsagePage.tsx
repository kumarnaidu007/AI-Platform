import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";

export function AdminUsagePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-usage"],
    queryFn: adminApi.getUsage,
  });

  if (isLoading) return <LoadingState />;

  const totals = data?.totals;
  const byUser = data?.byUser ?? [];
  const byProject = data?.byProject ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Token usage"
        description="LLM token spend across users and projects. No subscription tiers — pay only for what agents consume."
      />

      <div className="grid gap-4 sm:grid-cols-4">
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">Total tokens</p>
          <p className="mt-1 text-2xl font-semibold">{totals?.totalTokens?.toLocaleString() ?? 0}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">Input tokens</p>
          <p className="mt-1 text-2xl font-semibold">{totals?.inputTokens?.toLocaleString() ?? 0}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">Output tokens</p>
          <p className="mt-1 text-2xl font-semibold">{totals?.outputTokens?.toLocaleString() ?? 0}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-xs text-muted-foreground">Estimated cost</p>
          <p className="mt-1 text-2xl font-semibold">${totals?.costUsd?.toFixed(4) ?? "0.0000"}</p>
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">By user</h2>
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th className="px-4 py-2 font-medium">User</th>
                <th className="px-4 py-2 font-medium">Tokens</th>
                <th className="px-4 py-2 font-medium">Cost</th>
                <th className="px-4 py-2 font-medium">Events</th>
              </tr>
            </thead>
            <tbody>
              {byUser.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-muted-foreground">
                    No usage recorded yet.
                  </td>
                </tr>
              ) : (
                byUser.map((row) => (
                  <tr key={row.userId ?? row.userEmail} className="border-t">
                    <td className="px-4 py-2">
                      <p className="font-medium">{row.userName}</p>
                      <p className="text-xs text-muted-foreground">{row.userEmail}</p>
                    </td>
                    <td className="px-4 py-2">{row.totalTokens.toLocaleString()}</td>
                    <td className="px-4 py-2">${row.costUsd.toFixed(4)}</td>
                    <td className="px-4 py-2">{row.events}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">By project</h2>
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th className="px-4 py-2 font-medium">Project</th>
                <th className="px-4 py-2 font-medium">Tokens</th>
                <th className="px-4 py-2 font-medium">Cost</th>
                <th className="px-4 py-2 font-medium">Events</th>
              </tr>
            </thead>
            <tbody>
              {byProject.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-muted-foreground">
                    No project usage yet.
                  </td>
                </tr>
              ) : (
                byProject.map((row) => (
                  <tr key={row.projectId} className="border-t">
                    <td className="px-4 py-2 font-medium">{row.projectName}</td>
                    <td className="px-4 py-2">{row.totalTokens.toLocaleString()}</td>
                    <td className="px-4 py-2">${row.costUsd.toFixed(4)}</td>
                    <td className="px-4 py-2">{row.events}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
