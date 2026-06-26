import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Save } from "lucide-react";
import { AgentIcon } from "@/components/admin/AgentIcon";
import { LoadingState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { agentCategoryLabels } from "@/types/agents";

interface ProjectAgentsPanelProps {
  projectId: string;
}

export function ProjectAgentsPanel({ projectId }: ProjectAgentsPanelProps) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState<string | null>(null);
  const isViewer = false;

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
      setMessage("Agent pipeline updated");
      queryClient.invalidateQueries({ queryKey: ["project-agents", projectId] });
    },
  });

  if (isLoading) return <LoadingState />;

  const agents = data ?? [];

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Agent pipeline</h3>
        </div>
        {!isViewer && agents.length > 0 && (
          <button
            type="button"
            disabled={saveMutation.isPending}
            onClick={() => saveMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            Save
          </button>
        )}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Choose which assigned agents run for this project, then start a pipeline run below.
      </p>

      {message && (
        <p className="mt-3 text-xs text-emerald-600">{message}</p>
      )}

      {agents.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">
          No agents assigned to you. Ask your admin to assign agents from Team settings.
        </p>
      ) : (
        <ol className="mt-4 space-y-2">
          {agents.map((agent) => (
            <li
              key={agent.agentKey}
              className="flex items-center justify-between gap-3 rounded-md border px-3 py-2.5"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                  {agent.stepOrder}
                </span>
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted">
                  <AgentIcon agentKey={agent.agentKey} className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium">{agent.name}</p>
                  <p className="text-xs capitalize text-muted-foreground">
                    {agent.group ?? agentCategoryLabels[agent.category as keyof typeof agentCategoryLabels]}
                  </p>
                </div>
              </div>
              <input
                type="checkbox"
                disabled={isViewer}
                checked={enabled[agent.agentKey] ?? agent.isEnabled}
                onChange={(e) =>
                  setEnabled((prev) => ({ ...prev, [agent.agentKey]: e.target.checked }))
                }
                className="h-4 w-4"
              />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
