import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { AgentIcon } from "@/components/admin/AgentIcon";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import { agentCategoryLabels } from "@/types/agents";
import { cn } from "@/lib/utils";

export function PlatformAgentsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["platform-agents"],
    queryFn: adminApi.getAgents,
  });

  const mutation = useMutation({
    mutationFn: ({ key, isEnabled }: { key: string; isEnabled: boolean }) =>
      adminApi.updateAgent(key, { isEnabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["platform-agents"] }),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const agents = data ?? [];
  const enabledCount = agents.filter((a) => a.isEnabled).length;

  return (
    <div className="space-y-8">
      <PageHeader
        title="AI Agents"
        description="Platform agent catalog. Enable agents here, then grant them to companies."
      />

      <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3 text-sm">
        <Bot className="h-5 w-5 text-primary" />
        <span>
          <strong>{enabledCount}</strong> of <strong>{agents.length}</strong> agents enabled platform-wide
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {agents.map((agent) => (
          <div
            key={agent.agentKey}
            className={cn(
              "rounded-lg border bg-card p-5 transition-opacity",
              !agent.isEnabled && "opacity-60"
            )}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <AgentIcon agentKey={agent.agentKey} className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold">{agent.name}</h3>
                  <p className="text-xs text-muted-foreground">
                    {agent.group ?? agentCategoryLabels[agent.category]} · Step {agent.defaultStepOrder}
                  </p>
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={agent.isEnabled}
                  disabled={mutation.isPending}
                  onChange={(e) =>
                    mutation.mutate({ key: agent.agentKey, isEnabled: e.target.checked })
                  }
                />
                Enabled
              </label>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{agent.description}</p>
            {agent.artifact && (
              <p className="mt-2 text-xs text-muted-foreground">
                Output: <code className="rounded bg-muted px-1">{agent.artifact}</code>
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
