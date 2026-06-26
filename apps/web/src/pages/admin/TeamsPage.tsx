import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search, Users } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { DataTable, TableCell, TableRow } from "@/components/admin/DataTable";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import type { CompanyStatus } from "@/types/admin";

function formatUsd(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

export function TeamsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<CompanyStatus | "all">("all");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["teams"],
    queryFn: adminApi.getCompanies,
  });

  const filtered = useMemo(() => {
    return (data ?? []).filter((c) => {
      const matchesSearch =
        c.name.toLowerCase().includes(search.toLowerCase()) || c.slug.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === "all" || c.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [data, search, statusFilter]);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Teams"
        description="Each team is an isolated workspace. Grant integrations and AI agents per team — team leads then assign them to individual members."
        actions={
          <Link
            to="/admin/teams/new"
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            <Plus className="h-4 w-4" />
            Create team
          </Link>
        }
      />

      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
        <p className="font-medium">Access model</p>
        <ol className="mt-2 list-inside list-decimal space-y-1 text-xs">
          <li>Configure platform OAuth apps under Integrations (GitHub, Jira)</li>
          <li>Open a team below and enable which integrations & agents that team may use</li>
          <li>Team lead logs in and assigns integrations & agents to each member</li>
        </ol>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search teams..."
            className="h-9 w-full rounded-md border pl-9 pr-3 text-sm"
          />
        </div>
        <div className="flex gap-1 rounded-md border p-1">
          {(["all", "active", "trial", "suspended"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={`rounded px-3 py-1.5 text-xs font-medium capitalize ${
                statusFilter === s ? "bg-primary text-primary-foreground" : "text-muted-foreground"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <DataTable headers={["Team", "Plan", "Members", "Projects", "Pipelines", "Usage", "Status", "Created"]}>
        {filtered.length === 0 ? (
          <tr>
            <td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
              <Users className="mx-auto mb-2 h-8 w-8 opacity-40" />
              No teams found. Create one to get started.
            </td>
          </tr>
        ) : (
          filtered.map((team) => (
            <TableRow key={team.id} onClick={() => navigate(`/admin/teams/${team.id}`)}>
              <TableCell>
                <p className="font-medium">{team.name}</p>
                <p className="text-xs text-muted-foreground">{team.slug}</p>
              </TableCell>
              <TableCell>{team.planName}</TableCell>
              <TableCell>{team.usersCount}</TableCell>
              <TableCell>{team.projectsCount}</TableCell>
              <TableCell>{team.activePipelines}</TableCell>
              <TableCell>{formatUsd(team.monthlyUsageUsd)}</TableCell>
              <TableCell>
                <StatusBadge status={team.status} />
              </TableCell>
              <TableCell className="text-muted-foreground">{team.createdAt}</TableCell>
            </TableRow>
          ))
        )}
      </DataTable>
    </div>
  );
}
