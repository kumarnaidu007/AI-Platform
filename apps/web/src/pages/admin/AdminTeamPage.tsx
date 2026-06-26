import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronRight, Users } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import { formatRole } from "@/types/roles";

export function AdminTeamPage() {
  const workspaceQuery = useQuery({
    queryKey: ["admin-workspace"],
    queryFn: adminApi.getWorkspace,
  });

  const membersQuery = useQuery({
    queryKey: ["admin-workspace-members"],
    queryFn: adminApi.getWorkspaceMembers,
  });

  if (workspaceQuery.isLoading || membersQuery.isLoading) return <LoadingState />;
  if (workspaceQuery.isError || membersQuery.isError) {
    return <ErrorState message="Failed to load team" />;
  }

  const workspace = workspaceQuery.data;
  const members = membersQuery.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Team Access"
        description="Assign integrations and agents to each workspace member."
        actions={
          <Link
            to="/admin/workspace"
            className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent"
          >
            Workspace grants
            <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-100">
        <p className="font-medium">Two-step assignment</p>
        <ol className="mt-2 list-inside list-decimal space-y-1 text-xs">
          <li>
            Super admin enables integrations & agents for the workspace →{" "}
            <Link to="/admin/workspace" className="font-medium underline">
              Workspace Access
            </Link>
          </li>
          <li>Here: grant each member access to specific integrations and agents</li>
        </ol>
      </div>

      <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3 text-sm">
        <Users className="h-5 w-5 text-primary" />
        <span>
          <strong>{workspace?.name}</strong> · {members.length} members
        </span>
      </div>

      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/40">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Name</th>
              <th className="px-4 py-3 text-left font-medium">Email</th>
              <th className="px-4 py-3 text-left font-medium">Role</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {members.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                  No members yet. Team leads can add members from the workspace portal.
                </td>
              </tr>
            ) : (
              members.map((member) => (
                <tr key={member.id} className="border-b last:border-0 hover:bg-muted/20">
                  <td className="px-4 py-3 font-medium">{member.fullName}</td>
                  <td className="px-4 py-3 text-muted-foreground">{member.email}</td>
                  <td className="px-4 py-3">{formatRole(member.role)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        member.isActive ? "bg-emerald-100 text-emerald-800" : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {member.isActive ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/admin/team/${member.id}`}
                      className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                    >
                      Manage access
                      <ChevronRight className="h-4 w-4" />
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <p className="text-sm text-muted-foreground">
        Team leads can also manage members from{" "}
        <Link to="/workspace/team" className="text-primary hover:underline">
          workspace portal → Team
        </Link>
        .
      </p>
    </div>
  );
}
