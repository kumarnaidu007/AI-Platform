import { AgentIcon } from "@/components/admin/AgentIcon";
import type { ProjectAgentItem } from "@/types/agents";
import {
  agentsForImplementationRun,
  sortedCategoryGroups,
} from "@/lib/agentRunUtils";
import { cn } from "@/lib/utils";

interface AgentRunPickerProps {
  agents: ProjectAgentItem[];
  selected: Record<string, boolean>;
  onChange: (next: Record<string, boolean>) => void;
  disabled?: boolean;
  hint?: string;
}

export function AgentRunPicker({ agents, selected, onChange, disabled, hint }: AgentRunPickerProps) {
  const runAgents = agentsForImplementationRun(agents);
  const runKeySet = new Set(runAgents.map((a) => a.agentKey));
  const groups = sortedCategoryGroups(runAgents);

  if (agents.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No agents assigned to you. Ask your team lead to assign agents under Team.
      </p>
    );
  }

  if (runAgents.length === 0) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
        Enable implementation agents in the <strong>Agent pipeline</strong> tab first (e.g. Code Writer, Review,
        Deploy).
      </div>
    );
  }

  const selectedCount = runAgents.filter((a) => selected[a.agentKey]).length;

  return (
    <div className="space-y-3">
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}

      {groups.map(([group, items]) => (
        <div key={group}>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{group}</p>
          <div className="flex flex-wrap gap-2">
            {items.map((agent) => {
              const on = selected[agent.agentKey] ?? false;
              return (
                <button
                  key={agent.agentKey}
                  type="button"
                  disabled={disabled}
                  onClick={() => onChange({ ...selected, [agent.agentKey]: !on })}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-all",
                    on
                      ? "border-primary bg-primary text-primary-foreground shadow-sm"
                      : "border-border bg-card text-foreground hover:border-primary/40 hover:bg-muted/40",
                    disabled && "opacity-50"
                  )}
                >
                  <AgentIcon agentKey={agent.agentKey} className="h-4 w-4 shrink-0" />
                  <span className="font-medium">{agent.name.replace(/ Agent$/, "")}</span>
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-semibold",
                      on ? "bg-primary-foreground/20" : "bg-muted text-muted-foreground"
                    )}
                  >
                    {agent.stepOrder}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-2">
        <p className="text-[11px] text-muted-foreground">
          {selectedCount} of {runAgents.length} selected for this run
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              const next: Record<string, boolean> = { ...selected };
              for (const a of runAgents) next[a.agentKey] = true;
              onChange(next);
            }}
            className="text-[11px] font-medium text-primary hover:underline disabled:opacity-50"
          >
            Select all
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              const next: Record<string, boolean> = { ...selected };
              for (const a of runAgents) next[a.agentKey] = false;
              onChange(next);
            }}
            className="text-[11px] font-medium text-muted-foreground hover:underline disabled:opacity-50"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Hide planning agents note only if we filtered any */}
      {agents.some((a) => a.isEnabled && !runKeySet.has(a.agentKey) && !selected[a.agentKey]) && (
        <p className="text-[10px] text-muted-foreground">
          Planning agents are configured in the pipeline tab and are skipped for ticket implementation runs.
        </p>
      )}
    </div>
  );
}
