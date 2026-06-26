import { Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bot, Plug, Save } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { AgentIcon } from "@/components/admin/AgentIcon";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import { companyApi } from "@/services/companyApi";
import { formatRole, TEAM_LEAD, TEAM_MEMBER } from "@/types/roles";
import { agentCategoryLabels } from "@/types/agents";

export function AdminTeamMemberPage() {
  const { memberId } = useParams<{ memberId: string }>();
  const queryClient = useQueryClient();
  const [integrationAssignments, setIntegrationAssignments] = useState<Record<string, boolean>>({});
  const [agentAssignments, setAgentAssignments] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState<string | null>(null);

  const workspaceQuery = useQuery({
    queryKey: ["admin-workspace"],
    queryFn: adminApi.getWorkspace,
  });

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

  const agentsQuery = useQuery({
    queryKey: ["company-member-agents", memberId],
    queryFn: () => companyApi.getMemberAgents(memberId!),
    enabled: !!memberId,
  });

  const integrations = integrationsQuery.data ?? [];
  const agents = agentsQuery.data ?? [];

  useEffect(() => {
    if (!integrations.length) return;
    setIntegrationAssignments((prev) => {
      if (Object.keys(prev).length > 0) return prev;
      const next: Record<string, boolean> = {};
      for (const item of integrations) next[item.integrationKey] = item.isAssigned;
      return next;
    });
  }, [integrations]);

  useEffect(() => {
    if (!agents.length) return;
    setAgentAssignments((prev) => {
      if (Object.keys(prev).length > 0) return prev;
      const next: Record<string, boolean> = {};
      for (const item of agents) next[item.agentKey] = item.isAssigned;
      return next;
    });
  }, [agents]);

  const integrationMutation = useMutation({
    mutationFn: () =>
      companyApi.updateMemberIntegrations(
        memberId!,
        integrations.map((item) => ({
          integrationKey: item.integrationKey,
          isAssigned: integrationAssignments[item.integrationKey] ?? item.isAssigned,
        }))
      ),
    onSuccess: () => {
      setMessage("Integration access saved");
      queryClient.invalidateQueries({ queryKey: ["company-member-integrations", memberId] });
      queryClient.invalidateQueries({ queryKey: ["admin-workspace-members"] });
    },
  });

  const agentMutation = useMutation({
    mutationFn: () =>
      companyApi.updateMemberAgents(
        memberId!,
        agents.map((item) => ({
          agentKey: item.agentKey,
          isAssigned: agentAssignments[item.agentKey] ?? item.isAssigned,
        }))
      ),
    onSuccess: () => {
      setMessage("Agent access saved");
      queryClient.invalidateQueries({ queryKey: ["company-member-agents", memberId] });
      queryClient.invalidateQueries({ queryKey: ["admin-workspace-members"] });
    },
  });

  const roleMutation = useMutation({
    mutationFn: (role: string) => companyApi.updateMember(memberId!, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["company-member", memberId] });
      queryClient.invalidateQueries({ queryKey: ["admin-workspace-members"] });
    },
  });

  if (workspaceQuery.isLoading || memberQuery.isLoading) return <LoadingState />;
  if (memberQuery.isError || !memberQuery.data) return <ErrorState message="Member not found" />;

  const member = memberQuery.data;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to="/admin/team"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Team Access
      </Link>

      <PageHeader title={member.fullName} description={member.email} />

      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>
      )}

      <div className="rounded-lg border bg-card p-4">
        <label htmlFor="member_role" className="block text-sm font-medium">
          Role
        </label>
        <select
          id="member_role"
          value={member.role}
          onChange={(e) => roleMutation.mutate(e.target.value)}
          className="mt-2 h-10 w-full rounded-md border bg-background px-3 text-sm"
        >
          <option value={TEAM_LEAD}>{formatRole(TEAM_LEAD)}</option>
          <option value={TEAM_MEMBER}>{formatRole(TEAM_MEMBER)}</option>
        </select>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Plug className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold">Integration access</h3>
          </div>
          <button
            type="button"
            disabled={integrationMutation.isPending || integrationsQuery.isLoading}
            onClick={() => integrationMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            Save
          </button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Which integrations this user may connect with their own account.
        </p>
        {integrationsQuery.isLoading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading...</p>
        ) : integrations.length === 0 ? (
          <div className="mt-4 rounded-md border border-dashed bg-muted/30 p-4 text-sm text-muted-foreground">
            No integrations granted to the workspace. Enable them under{" "}
            <Link to="/admin/workspace" className="text-primary hover:underline">
              Workspace Access
            </Link>
            .
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {integrations.map((item) => (
              <label
                key={item.integrationKey}
                className="flex cursor-pointer items-center justify-between rounded-md border px-3 py-2.5"
              >
                <span className="text-sm">{item.name}</span>
                <input
                  type="checkbox"
                  checked={integrationAssignments[item.integrationKey] ?? item.isAssigned}
                  onChange={(e) =>
                    setIntegrationAssignments((prev) => ({ ...prev, [item.integrationKey]: e.target.checked }))
                  }
                  className="h-4 w-4"
                />
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold">Agent access</h3>
          </div>
          <button
            type="button"
            disabled={agentMutation.isPending || agentsQuery.isLoading}
            onClick={() => agentMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            Save
          </button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">Which AI agents this user may run on projects.</p>
        {agentsQuery.isLoading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading...</p>
        ) : agents.length === 0 ? (
          <div className="mt-4 rounded-md border border-dashed bg-muted/30 p-4 text-sm text-muted-foreground">
            No agents granted to the workspace. Enable them under{" "}
            <Link to="/admin/workspace" className="text-primary hover:underline">
              Workspace Access
            </Link>
            .
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {agents.map((item) => (
              <label
                key={item.agentKey}
                className="flex cursor-pointer items-center justify-between gap-3 rounded-md border px-3 py-2.5"
              >
                <div className="flex items-center gap-3">
                  <AgentIcon agentKey={item.agentKey} className="h-4 w-4" />
                  <div>
                    <p className="text-sm font-medium">{item.name}</p>
                    <p className="text-xs capitalize text-muted-foreground">
                      {item.group ?? agentCategoryLabels[item.category as keyof typeof agentCategoryLabels]}
                    </p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={agentAssignments[item.agentKey] ?? item.isAssigned}
                  onChange={(e) =>
                    setAgentAssignments((prev) => ({ ...prev, [item.agentKey]: e.target.checked }))
                  }
                  className="h-4 w-4"
                />
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
