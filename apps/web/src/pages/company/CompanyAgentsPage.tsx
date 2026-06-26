import { Link, Navigate, useParams } from "react-router-dom";
import { isTeamLead } from "@/types/roles";
import { useQuery } from "@tanstack/react-query";
import { Bot } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { AgentIcon } from "@/components/admin/AgentIcon";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";
import { agentCategoryLabels } from "@/types/agents";

export function CompanyAgentsPage() {
  useParams<{ slug: string }>();
  const { company } = useAuth();

  if (!isTeamLead(company?.role)) {
    return <Navigate to={`/workspace`} replace />;
  }

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["company-agent-catalog"],
    queryFn: companyApi.getAgentCatalog,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const agents = data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Agents"
        description="Agents granted to your company by the platform. Assign them to team members from the Team page."
      />

      {agents.length === 0 ? (
        <div className="rounded-lg border border-dashed p-10 text-center">
          <Bot className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="mt-4 text-sm text-muted-foreground">
            No agents granted yet. Ask your platform administrator to enable agents for your company.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {agents.map((agent) => (
            <div key={agent.agentKey} className="rounded-lg border bg-card p-5">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <AgentIcon agentKey={agent.agentKey} className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-semibold">{agent.name}</h3>
                  <p className="text-xs capitalize text-muted-foreground">
                    {agent.group ?? agentCategoryLabels[agent.category as keyof typeof agentCategoryLabels]}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">{agent.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-sm text-muted-foreground">
        Go to{" "}
        <Link to={`/workspace/team`} className="text-primary hover:underline">
          Team
        </Link>{" "}
        to assign agents to employees.
      </p>
    </div>
  );
}
