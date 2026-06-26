import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Bot } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { AgentIcon } from "@/components/admin/AgentIcon";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { agentCategoryLabels } from "@/types/agents";

export function CompanyMyAgentsPage() {
  useParams<{ slug: string }>();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["company-my-agents"],
    queryFn: companyApi.getMyAgents,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const agents = data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Agents"
        description="AI agents assigned to you. Enable them per project from the project settings."
      />

      {agents.length === 0 ? (
        <div className="rounded-lg border border-dashed p-10 text-center">
          <Bot className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="mt-4 text-sm text-muted-foreground">
            No agents assigned yet. Ask your company admin to assign agents from the Team page.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {agents.map((agent) => (
            <div key={agent.agentKey} className="rounded-lg border bg-card p-5">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <AgentIcon agentKey={agent.agentKey} className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold">{agent.name}</h3>
                  <p className="text-xs capitalize text-muted-foreground">
                    {agent.group ?? agentCategoryLabels[agent.category as keyof typeof agentCategoryLabels]}
                    {" · "}Step {agent.defaultStepOrder}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">{agent.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-sm text-muted-foreground">
        Configure which agents run on each project from{" "}
        <Link to={`/workspace/projects`} className="text-primary hover:underline">
          Projects
        </Link>
        .
      </p>
    </div>
  );
}
