import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/admin/PageHeader";
import { DataTable, TableCell, TableRow } from "@/components/admin/DataTable";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";

function formatTime(iso: string) {
  return new Date(iso).toLocaleString();
}

export function AuditLogPage() {
  const [actionFilter, setActionFilter] = useState("all");
  const { data, isLoading, isError, error } = useQuery({ queryKey: ["audit-log"], queryFn: adminApi.getAuditLog });

  const actions = useMemo(() => ["all", ...new Set((data ?? []).map((e) => e.action))], [data]);
  const filtered = useMemo(() => {
    if (actionFilter === "all") return data ?? [];
    return (data ?? []).filter((e) => e.action === actionFilter);
  }, [data, actionFilter]);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  return (
    <div className="space-y-6">
      <PageHeader title="Audit Log" description="Platform-wide activity log." />
      <div className="flex flex-wrap gap-1 rounded-md border p-1">
        {actions.map((action) => (
          <button key={action} type="button" onClick={() => setActionFilter(action)} className={`rounded px-3 py-1.5 text-xs font-medium capitalize ${actionFilter === action ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
            {action.replace(/_/g, " ")}
          </button>
        ))}
      </div>
      {filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground">No audit events recorded yet.</p>
      ) : (
        <DataTable headers={["Timestamp", "User", "Action", "Resource", "Company", "IP"]}>
          {filtered.map((event) => (
            <TableRow key={event.id}>
              <TableCell className="text-muted-foreground">{formatTime(event.timestamp)}</TableCell>
              <TableCell className="font-medium">{event.user}</TableCell>
              <TableCell className="capitalize">{event.action.replace(/_/g, " ")}</TableCell>
              <TableCell><p className="font-medium">{event.resourceName}</p><p className="text-xs text-muted-foreground">{event.resourceType}</p></TableCell>
              <TableCell className="text-muted-foreground">{event.companyName ?? "—"}</TableCell>
              <TableCell><code className="rounded bg-muted px-1.5 py-0.5 text-xs">{event.ipAddress || "—"}</code></TableCell>
            </TableRow>
          ))}
        </DataTable>
      )}
    </div>
  );
}
