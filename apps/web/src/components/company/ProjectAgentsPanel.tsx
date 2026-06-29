import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Save, Sparkles, Wrench } from "lucide-react";
import { LoadingState } from "@/components/admin/LoadingState";
import {
  ActivePipelinePreview,
  AgentPipelineCard,
} from "@/components/company/AgentPipelineFlow";
import { companyApi } from "@/services/companyApi";
import {
  agentsForProjectPipeline,
  isPlanningAgent,
  sortedCategoryGroups,
} from "@/lib/agentRunUtils";

interface ProjectAgentsPanelProps {
  projectId: string;
}

export function ProjectAgentsPanel({ projectId }: ProjectAgentsPanelProps) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["project-agents", projectId],
    queryFn: () => companyApi.getProjectAgents(projectId),
  });

  useEffect(() => {
    if (!data) return;
    const next: Record<string, boolean> = {};
    for (const agent of data) {
      next[agent.agentKey] = agent.isEnabled;
    }
    setEnabled(next);
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      companyApi.updateProjectAgents(
        projectId,
        (data ?? []).map((agent) => ({
          agentKey: agent.agentKey,
          isEnabled: enabled[agent.agentKey] ?? agent.isEnabled,
          stepOrder: agent.stepOrder,
        }))
      ),
    onSuccess: () => {
      setMessage("Pipeline saved successfully");
      queryClient.invalidateQueries({ queryKey: ["project-agents", projectId] });
    },
  });

  const agents = useMemo(() => agentsForProjectPipeline(data ?? []), [data]);
  const groups = useMemo(() => sortedCategoryGroups(agents), [agents]);
  const enabledCount = agents.filter((a) => enabled[a.agentKey] ?? a.isEnabled).length;

  const enableImplementationDefaults = () => {
    setEnabled((prev) => {
      const next = { ...prev };
      for (const agent of agents) {
        next[agent.agentKey] = !isPlanningAgent(agent.agentKey);
      }
      return next;
    });
  };

  const disableAll = () => {
    setEnabled((prev) => {
      const next = { ...prev };
      for (const agent of agents) {
        next[agent.agentKey] = false;
      }
      return next;
    });
  };

  if (isLoading) return <LoadingState />;

  return (
    <div className="space-y-5">
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                <Bot className="h-4 w-4 text-primary" />
              </div>
              <div>
                <h3 className="text-base font-semibold">Agent pipeline</h3>
                <p className="text-xs text-muted-foreground">
                  {enabledCount} of {agents.length} agents enabled for this project
                </p>
              </div>
            </div>
            <p className="mt-3 max-w-xl text-sm text-muted-foreground">
              Enable the agents that should run on this project. Jira tickets use the implementation agents you turn on
              here (Code Writer, Review, Deploy, etc.).
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={enableImplementationDefaults}
              className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted/50"
            >
              <Wrench className="h-3.5 w-3.5" />
              Enable build agents
            </button>
            <button
              type="button"
              disabled={saveMutation.isPending || agents.length === 0}
              onClick={() => saveMutation.mutate()}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
            >
              <Save className="h-3.5 w-3.5" />
              {saveMutation.isPending ? "Saving…" : "Save pipeline"}
            </button>
          </div>
        </div>

        {message && <p className="mt-3 text-sm text-emerald-600">{message}</p>}

        {agents.length === 0 ? (
          <p className="mt-6 text-sm text-muted-foreground">
            No agents assigned to you. Ask your team lead to assign agents under Team.
          </p>
        ) : (
          <div className="mt-5">
            <ActivePipelinePreview agents={agents} enabled={enabled} />
          </div>
        )}
      </div>

      {agents.length > 0 &&
        groups.map(([group, items]) => (
          <section key={group} className="rounded-xl border bg-card p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-muted-foreground" />
              <h4 className="text-sm font-semibold">{group}</h4>
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                {items.filter((a) => enabled[a.agentKey] ?? a.isEnabled).length}/{items.length} on
              </span>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {items.map((agent) => (
                <AgentPipelineCard
                  key={agent.agentKey}
                  agent={agent}
                  enabled={enabled[agent.agentKey] ?? agent.isEnabled}
                  onToggle={(checked) => setEnabled((prev) => ({ ...prev, [agent.agentKey]: checked }))}
                />
              ))}
            </div>
          </section>
        ))}

      {agents.length > 0 && (
        <p className="text-center text-xs text-muted-foreground">
          <button type="button" onClick={disableAll} className="underline hover:text-foreground">
            Turn off all agents
          </button>
        </p>
      )}
    </div>
  );
}
