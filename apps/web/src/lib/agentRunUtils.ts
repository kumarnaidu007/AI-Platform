import { agentGroupOrder } from "@/types/agents";
import type { ProjectAgentItem } from "@/types/agents";
import { agentCategoryLabels } from "@/types/agents";

/** Agents used only during upfront planning — skipped for Jira intake implementation runs. */
export const PLANNING_AGENT_KEYS = new Set(["requirements", "architecture", "task_planner"]);

export const IMPLEMENTATION_AGENT_KEYS = new Set([
  "code_writer",
  "review",
  "test_writer",
  "deploy",
]);

export function isPlanningAgent(agentKey: string): boolean {
  return PLANNING_AGENT_KEYS.has(agentKey);
}

export function agentsForProjectPipeline(agents: ProjectAgentItem[]): ProjectAgentItem[] {
  return [...agents].sort((a, b) => a.stepOrder - b.stepOrder);
}

export function categoryLabel(agent: ProjectAgentItem): string {
  return (
    agent.group ??
    agentCategoryLabels[agent.category as keyof typeof agentCategoryLabels] ??
    agent.category
  );
}

/** Agents the user can pick for an implementation run (enabled on project, not planning-only). */
export function agentsForImplementationRun(agents: ProjectAgentItem[]): ProjectAgentItem[] {
  const enabled = agents.filter((a) => a.isEnabled);
  const impl = enabled.filter((a) => !isPlanningAgent(a.agentKey));
  return impl.length > 0 ? impl : enabled;
}

export function defaultRunSelection(agents: ProjectAgentItem[]): Record<string, boolean> {
  const runAgents = agentsForImplementationRun(agents);
  const next: Record<string, boolean> = {};
  for (const agent of runAgents) {
    next[agent.agentKey] = true;
  }
  if (!Object.values(next).some(Boolean) && runAgents.length > 0) {
    next[runAgents[0].agentKey] = true;
  }
  return next;
}

export function selectedAgentKeys(selection: Record<string, boolean>): string[] {
  return Object.entries(selection)
    .filter(([, on]) => on)
    .map(([key]) => key);
}

export function groupAgentsByCategory(agents: ProjectAgentItem[]): Map<string, ProjectAgentItem[]> {
  const map = new Map<string, ProjectAgentItem[]>();
  for (const agent of agents) {
    const label = categoryLabel(agent);
    (map.get(label) ?? map.set(label, []).get(label)!).push(agent);
  }
  for (const items of map.values()) {
    items.sort((a, b) => a.stepOrder - b.stepOrder);
  }
  return map;
}

export function sortedCategoryGroups(agents: ProjectAgentItem[]): Array<[string, ProjectAgentItem[]]> {
  const grouped = groupAgentsByCategory(agents);
  const order = new Map(agentGroupOrder.map((g, i) => [g, i]));
  return [...grouped.entries()].sort(([a], [b]) => {
    const ia = order.get(a as (typeof agentGroupOrder)[number]) ?? 99;
    const ib = order.get(b as (typeof agentGroupOrder)[number]) ?? 99;
    if (ia !== ib) return ia - ib;
    return a.localeCompare(b);
  });
}

export function enabledAgentsInOrder(
  agents: ProjectAgentItem[],
  enabled: Record<string, boolean>
): ProjectAgentItem[] {
  return agentsForProjectPipeline(agents).filter((a) => enabled[a.agentKey] ?? a.isEnabled);
}
