import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban, DollarSign, FolderKanban, GitBranch, Mail, User, Users } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { StatCard } from "@/components/admin/StatCard";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { DataTable, TableCell, TableRow } from "@/components/admin/DataTable";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import {
  AgentsAccessSection,
  IntegrationsAccessSection,
  ServicesAccessSection,
} from "@/components/admin/WorkspaceAccessSections";
import { adminApi } from "@/services/adminApi";
import { formatRole } from "@/types/roles";

function formatUsd(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

export function TeamDetailPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const queryClient = useQueryClient();

  const { data: team, isLoading, isError, error } = useQuery({
    queryKey: ["team", teamId],
    queryFn: () => adminApi.getCompany(teamId!),
    enabled: !!teamId,
  });

  const membersQuery = useQuery({
    queryKey: ["team-members", teamId],
    queryFn: () => adminApi.getCompanyMembers(teamId!),
    enabled: !!teamId,
  });

  const suspendMutation = useMutation({
    mutationFn: () => adminApi.updateCompany(teamId!, { status: "suspended" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", teamId] }),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !team) return <ErrorState message={String(error ?? "Team not found")} />;

  const members = membersQuery.data ?? [];

  return (
    <div className="space-y-8">
      <Link to="/admin/teams" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />
        Teams
      </Link>

      <PageHeader
        title={team.name}
        description={`Team slug: ${team.slug} · ${team.planName} · Created ${team.createdAt}`}
        actions={
          <div className="flex items-center gap-2">
            <a
              href="/workspace/login"
              target="_blank"
              rel="noreferrer"
              className="rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent"
            >
              Team portal login
            </a>
            {team.status !== "suspended" ? (
              <button
                type="button"
                onClick={() => suspendMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-md border border-destructive/30 px-3 py-2 text-sm font-medium text-destructive"
              >
                <Ban className="h-4 w-4" />
                Suspend team
              </button>
            ) : null}
          </div>
        }
      />

      <StatusBadge status={team.status} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Members" value={team.usersCount} icon={Users} />
        <StatCard label="Projects" value={team.projectsCount} icon={FolderKanban} />
        <StatCard label="Active pipelines" value={team.activePipelines} icon={GitBranch} />
        <StatCard label="Monthly usage" value={formatUsd(team.monthlyUsageUsd)} icon={DollarSign} />
      </div>

      <div className="rounded-lg border bg-card p-5">
        <h3 className="text-sm font-semibold">Team lead</h3>
        <div className="mt-4 space-y-3 text-sm">
          {team.adminName ? (
            <>
              <div className="flex items-center gap-3">
                <User className="h-4 w-4" />
                {team.adminName}
              </div>
              <div className="flex items-center gap-3">
                <Mail className="h-4 w-4" />
                {team.adminEmail}
              </div>
              <p className="text-xs text-muted-foreground">
                The team lead assigns integrations and agents to individual members from the workspace portal → Team.
              </p>
            </>
          ) : (
            <p className="text-muted-foreground">No team lead assigned yet.</p>
          )}
        </div>
      </div>

      {teamId && (
        <div className="space-y-4">
          <div>
            <h2 className="text-base font-semibold">Team access grants</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Enable integrations and agents for <strong>{team.name}</strong> only. Other teams are unaffected.
            </p>
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <IntegrationsAccessSection workspaceId={teamId} />
            <ServicesAccessSection workspaceId={teamId} />
            <AgentsAccessSection workspaceId={teamId} />
          </div>
        </div>
      )}

      <div className="space-y-3">
        <h2 className="text-base font-semibold">Team members</h2>
        <p className="text-sm text-muted-foreground">
          Super admin grants access at the team level above. The team lead assigns integrations and agents per person.
        </p>
        {membersQuery.isLoading ? (
          <LoadingState />
        ) : members.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
            No members yet. The team lead can add members from the workspace portal.
          </div>
        ) : (
          <DataTable headers={["Name", "Email", "Role", "Integrations", "Agents", "Status"]}>
            {members.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="font-medium">{m.fullName}</TableCell>
                <TableCell>{m.email}</TableCell>
                <TableCell>{formatRole(m.role)}</TableCell>
                <TableCell>{m.integrationsAssigned}</TableCell>
                <TableCell>{m.agentsAssigned}</TableCell>
                <TableCell>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      m.isActive ? "bg-emerald-100 text-emerald-800" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {m.isActive ? "Active" : "Inactive"}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </DataTable>
        )}
      </div>

      <div className="space-y-3">
        <h2 className="text-base font-semibold">Recent projects</h2>
        {team.recentProjects.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">No projects yet.</div>
        ) : (
          <DataTable headers={["Project", "Stack", "Status"]}>
            {team.recentProjects.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-medium">{p.name}</TableCell>
                <TableCell className="text-muted-foreground">{p.stack}</TableCell>
                <TableCell>
                  <StatusBadge status={p.status} />
                </TableCell>
              </TableRow>
            ))}
          </DataTable>
        )}
      </div>
    </div>
  );
}
