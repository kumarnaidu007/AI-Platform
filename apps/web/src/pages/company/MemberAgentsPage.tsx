import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { isTeamLead } from "@/types/roles";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Save } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { AgentIcon } from "@/components/admin/AgentIcon";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";
import { agentCategoryLabels } from "@/types/agents";

export function MemberAgentsPage() {
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

  const agentsQuery = useQuery({
    queryKey: ["company-member-agents", memberId],
    queryFn: () => companyApi.getMemberAgents(memberId!),
    enabled: !!memberId,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      companyApi.updateMemberAgents(
        memberId!,
        (agentsQuery.data ?? []).map((item) => ({
          agentKey: item.agentKey,
          isAssigned: assignments[item.agentKey] ?? item.isAssigned,
        }))
      ),
    onSuccess: () => {
      setMessage("Agent access updated");
      queryClient.invalidateQueries({ queryKey: ["company-member-agents", memberId] });
      queryClient.invalidateQueries({ queryKey: ["company-members"] });
    },
  });

  if (memberQuery.isLoading || agentsQuery.isLoading) return <LoadingState />;
  if (memberQuery.isError || agentsQuery.isError || !memberQuery.data) {
    return <ErrorState message="Member not found" />;
  }

  const member = memberQuery.data;
  const agents = agentsQuery.data ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to={`/workspace/team`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Team
      </Link>

      <PageHeader
        title={`Agents — ${member.fullName}`}
        description="Choose which AI agents this employee can use on their projects."
      />

      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
          {message}
        </div>
      )}

      {agents.length === 0 ? (
        <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center text-sm">
          <p className="font-medium text-foreground">No agents available to assign</p>
          <p className="mt-2 text-muted-foreground">
            Ask the platform administrator to grant AI agents to your team under Super Admin → Teams.
          </p>
        </div>
      ) : (
        <div className="space-y-2 rounded-lg border bg-card p-4">
          {agents.map((item) => {
            const checked = assignments[item.agentKey] ?? item.isAssigned;
            return (
              <label
                key={item.agentKey}
                className="flex cursor-pointer items-center justify-between gap-4 rounded-md border px-4 py-3 hover:bg-muted/30"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <AgentIcon agentKey={item.agentKey} className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{item.name}</p>
                    <p className="text-xs capitalize text-muted-foreground">
                      {item.group ?? agentCategoryLabels[item.category as keyof typeof agentCategoryLabels]}
                    </p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) =>
                    setAssignments((prev) => ({ ...prev, [item.agentKey]: e.target.checked }))
                  }
                  className="h-4 w-4"
                />
              </label>
            );
          })}
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="button"
          disabled={saveMutation.isPending || agents.length === 0}
          onClick={() => saveMutation.mutate()}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          <Save className="h-4 w-4" />
          Save assignments
        </button>
        <Link
          to={`/workspace/team/${memberId}`}
          className="inline-flex items-center rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent"
        >
          Integrations
        </Link>
      </div>
    </div>
  );
}
