import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { isTeamLead } from "@/types/roles";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bot, Save } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";
import { categoryLabels } from "@/types/platform";

export function MemberIntegrationsPage() {
  const { memberId } = useParams<{ slug: string; memberId: string }>();
  const { company } = useAuth();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const [assignments, setAssignments] = useState<Record<string, boolean>>({});

  if (!isTeamLead(company?.role)) {
    return <Navigate to={`/workspace`} replace />;
  }

  const memberQuery = useQuery({
    queryKey: ["company-member", memberId],
    queryFn: () => companyApi.getMember(memberId!),
    enabled: !!memberId,
  });

  const integrationsQuery = useQuery({
    queryKey: ["company-member-integrations", memberId],
    queryFn: () => companyApi.getMemberIntegrations(memberId!),
    enabled: !!memberId,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      companyApi.updateMemberIntegrations(
        memberId!,
        (integrationsQuery.data ?? []).map((item) => ({
          integrationKey: item.integrationKey,
          isAssigned: assignments[item.integrationKey] ?? item.isAssigned,
        }))
      ),
    onSuccess: () => {
      setMessage("Integration access updated");
      queryClient.invalidateQueries({ queryKey: ["company-member-integrations", memberId] });
      queryClient.invalidateQueries({ queryKey: ["company-members"] });
    },
  });

  const roleMutation = useMutation({
    mutationFn: (role: string) => companyApi.updateMember(memberId!, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["company-member", memberId] });
      queryClient.invalidateQueries({ queryKey: ["company-members"] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: (isActive: boolean) => companyApi.updateMember(memberId!, { isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["company-member", memberId] });
      queryClient.invalidateQueries({ queryKey: ["company-members"] });
    },
  });

  if (memberQuery.isLoading || integrationsQuery.isLoading) return <LoadingState />;
  if (memberQuery.isError || integrationsQuery.isError || !memberQuery.data) {
    return <ErrorState message="Member not found" />;
  }

  const member = memberQuery.data;
  const integrations = integrationsQuery.data ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to={`/workspace/team`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to team
      </Link>

      <PageHeader
        title={member.fullName}
        description={member.email}
        actions={
          <Link
            to={`/workspace/team/${memberId}/agents`}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent"
          >
            <Bot className="h-4 w-4" />
            Manage agents
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border bg-card p-4">
          <label htmlFor="member_role" className="block text-sm font-medium">
            Role
          </label>
          <select
            id="member_role"
            defaultValue={member.role}
            onChange={(e) => roleMutation.mutate(e.target.value)}
            className="mt-2 h-10 w-full rounded-md border bg-background px-3 text-sm"
          >
            <option value="team_member">Team Member</option>
            <option value="team_lead">Team Lead</option>
          </select>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <label htmlFor="member_status" className="block text-sm font-medium">
            Account status
          </label>
          <select
            id="member_status"
            defaultValue={member.isActive ? "active" : "inactive"}
            onChange={(e) => statusMutation.mutate(e.target.value === "active")}
            className="mt-2 h-10 w-full rounded-md border bg-background px-3 text-sm"
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold">Integration access</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Assign integrations this employee can connect with their own work account credentials.
            </p>
          </div>
          <button
            type="button"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            <Save className="h-4 w-4" />
            {saveMutation.isPending ? "Saving..." : "Save access"}
          </button>
        </div>

        {message && (
          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
            {message}
          </div>
        )}

        {integrations.length === 0 ? (
          <div className="mt-6 rounded-lg border border-dashed bg-muted/30 p-6 text-sm">
            <p className="font-medium text-foreground">No integrations available to assign</p>
            <p className="mt-2 text-muted-foreground">
              The platform administrator must grant integrations to your team first (Super Admin → Teams → your team).
              Then you can assign them here.
            </p>
          </div>
        ) : (
          <div className="mt-6 space-y-2">
            {integrations.map((item) => {
              const checked = assignments[item.integrationKey] ?? item.isAssigned;
              return (
                <label
                  key={item.integrationKey}
                  className="flex cursor-pointer items-center justify-between rounded-lg border px-4 py-3 hover:bg-muted/30"
                >
                  <div>
                    <p className="text-sm font-medium">{item.name}</p>
                    <p className="text-xs capitalize text-muted-foreground">
                      {categoryLabels[item.category as keyof typeof categoryLabels] ?? item.category}
                      {item.isAssigned && item.isConnected && " · Employee connected"}
                      {item.isAssigned && !item.isConnected && " · Assigned, not connected yet"}
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) =>
                      setAssignments((prev) => ({ ...prev, [item.integrationKey]: e.target.checked }))
                    }
                    className="h-4 w-4 rounded border"
                  />
                </label>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
