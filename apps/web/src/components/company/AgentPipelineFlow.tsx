import { ArrowRight } from "lucide-react";
import { AgentIcon } from "@/components/admin/AgentIcon";
import type { ProjectAgentItem } from "@/types/agents";
import { enabledAgentsInOrder } from "@/lib/agentRunUtils";
import { cn } from "@/lib/utils";

interface ActivePipelinePreviewProps {
  agents: ProjectAgentItem[];
  enabled: Record<string, boolean>;
}

export function ActivePipelinePreview({ agents, enabled }: ActivePipelinePreviewProps) {
  const active = enabledAgentsInOrder(agents, enabled);

  if (active.length === 0) {
    return (
      <div className="rounded-lg border border-dashed bg-muted/30 px-4 py-6 text-center">
        <p className="text-sm text-muted-foreground">No agents enabled yet</p>
        <p className="mt-1 text-xs text-muted-foreground">Turn on agents below to build your pipeline.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-gradient-to-br from-primary/5 via-background to-background p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Active run order</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {active.map((agent, index) => (
          <div key={agent.agentKey} className="flex items-center gap-2">
            <div
              className={cn(
                "inline-flex items-center gap-2 rounded-full border border-primary/30 bg-background px-3 py-1.5 shadow-sm"
              )}
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                {agent.stepOrder}
              </span>
              <AgentIcon agentKey={agent.agentKey} className="h-3.5 w-3.5 text-primary" />
              <span className="text-xs font-medium">{agent.name.replace(/ Agent$/, "")}</span>
            </div>
            {index < active.length - 1 && (
              <ArrowRight className="hidden h-3.5 w-3.5 text-muted-foreground/60 sm:block" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative h-6 w-11 shrink-0 rounded-full transition-colors",
        checked ? "bg-primary" : "bg-muted-foreground/30",
        disabled && "cursor-not-allowed opacity-50"
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
          checked && "translate-x-5"
        )}
      />
    </button>
  );
}

interface AgentPipelineCardProps {
  agent: ProjectAgentItem;
  enabled: boolean;
  onToggle: (checked: boolean) => void;
  disabled?: boolean;
}

export function AgentPipelineCard({ agent, enabled, onToggle, disabled }: AgentPipelineCardProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-xl border p-3 transition-colors",
        enabled ? "border-primary/40 bg-primary/[0.03]" : "border-border bg-card hover:bg-muted/30"
      )}
    >
      <div
        className={cn(
          "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
          enabled ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
        )}
      >
        <AgentIcon agentKey={agent.agentKey} className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium leading-tight">{agent.name}</p>
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            Step {agent.stepOrder}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground capitalize">{agent.category}</p>
      </div>
      <Toggle
        checked={enabled}
        onChange={onToggle}
        disabled={disabled}
        label={`Toggle ${agent.name}`}
      />
    </div>
  );
}
