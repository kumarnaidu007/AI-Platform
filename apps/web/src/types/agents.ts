export type AgentCategory = "planning" | "development" | "quality" | "delivery";

export interface PlatformAgent {
  id: string;
  agentKey: string;
  name: string;
  description: string | null;
  category: AgentCategory;
  defaultStepOrder: number;
  isEnabled: boolean;
  group: string | null;
  artifact: string | null;
}

export interface CompanyAgentAccess {
  agentKey: string;
  name: string;
  category: string;
  group: string | null;
  defaultStepOrder: number;
  isEnabled: boolean;
  platformEnabled: boolean;
  assignable: boolean;
}

export interface CompanyAgentCatalogItem {
  agentKey: string;
  name: string;
  description: string | null;
  category: string;
  group: string | null;
  defaultStepOrder: number;
  isGranted: boolean;
}

export interface MyAgentItem {
  agentKey: string;
  name: string;
  description: string | null;
  category: string;
  group: string | null;
  defaultStepOrder: number;
  isAssigned: boolean;
  isEnabledOnPlatform: boolean;
}

export interface MemberAgentAccess {
  agentKey: string;
  name: string;
  category: string;
  group: string | null;
  defaultStepOrder: number;
  isAssigned: boolean;
}

export interface ProjectAgentItem {
  agentKey: string;
  name: string;
  category: string;
  group: string | null;
  stepOrder: number;
  isEnabled: boolean;
  isAssigned: boolean;
  defaultStepOrder: number;
}

export const agentCategoryLabels: Record<AgentCategory, string> = {
  planning: "Planning",
  development: "Development",
  quality: "Quality",
  delivery: "Delivery",
};

export const agentGroupOrder = ["Planning", "Development", "Quality", "Delivery"] as const;
