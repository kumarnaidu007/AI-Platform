import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Building2, Plus, Search } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { DataTable, TableCell, TableRow } from "@/components/admin/DataTable";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import type { CompanyStatus } from "@/types/admin";

function formatUsd(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

export function CompaniesPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<CompanyStatus | "all">("all");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["companies"],
    queryFn: adminApi.getCompanies,
  });

  const filtered = useMemo(() => {
    return (data ?? []).filter((c) => {
      const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase()) || c.slug.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === "all" || c.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [data, search, statusFilter]);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Companies"
        description="Manage tenant companies, plans, and access."
        actions={
          <Link to="/admin/companies/new" className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
            <Plus className="h-4 w-4" />
            Create Company
          </Link>
        }
      />

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search..." className="h-9 w-full rounded-md border pl-9 pr-3 text-sm" />
        </div>
        <div className="flex gap-1 rounded-md border p-1">
          {(["all", "active", "trial", "suspended"] as const).map((s) => (
            <button key={s} type="button" onClick={() => setStatusFilter(s)} className={`rounded px-3 py-1.5 text-xs font-medium capitalize ${statusFilter === s ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
              {s}
            </button>
          ))}
        </div>
      </div>

      <DataTable headers={["Company", "Plan", "Users", "Projects", "Pipelines", "Usage", "Status", "Created"]}>
        {filtered.length === 0 ? (
          <tr><td colSpan={8} className="px-4 py-12 text-center text-muted-foreground"><Building2 className="mx-auto mb-2 h-8 w-8 opacity-40" />No companies found.</td></tr>
        ) : (
          filtered.map((c) => (
            <TableRow key={c.id} onClick={() => navigate(`/admin/companies/${c.id}`)}>
              <TableCell><p className="font-medium">{c.name}</p><p className="text-xs text-muted-foreground">{c.slug}</p></TableCell>
              <TableCell>{c.planName}</TableCell>
              <TableCell>{c.usersCount}</TableCell>
              <TableCell>{c.projectsCount}</TableCell>
              <TableCell>{c.activePipelines}</TableCell>
              <TableCell>{formatUsd(c.monthlyUsageUsd)}</TableCell>
              <TableCell><StatusBadge status={c.status} /></TableCell>
              <TableCell className="text-muted-foreground">{c.createdAt}</TableCell>
            </TableRow>
          ))
        )}
      </DataTable>
    </div>
  );
}
