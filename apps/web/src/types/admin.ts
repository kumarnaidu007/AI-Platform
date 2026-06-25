export type CompanyStatus = "active" | "suspended" | "trial";

export interface Plan {
  id: string;
  name: string;
  maxProjects: number;
  maxParallelPipelines: number;
  monthlyTokenBudgetUsd: number;
  isActive: boolean;
  companiesCount: number;
  integrationKeys?: string[];
}

export interface Company {
  id: string;
  name: string;
  slug: string;
  status: CompanyStatus;
  planId: string;
  planName: string;
  usersCount: number;
  projectsCount: number;
  activePipelines: number;
  monthlyUsageUsd: number;
  createdAt: string;
}

export interface CompanyDetail extends Company {
  adminEmail: string | null;
  adminName: string | null;
  limitsOverride: {
    maxProjects: number | null;
    maxParallelPipelines: number | null;
    monthlyTokenBudgetUsd: number | null;
  };
  recentProjects: { id: string; name: string; status: string; stack: string }[];
}

export interface CompanyIntegrationAccess {
  integrationKey: string;
  name: string;
  category: string;
  isEnabled: boolean;
  platformEnabled: boolean;
  platformConnected: boolean;
  assignable: boolean;
  connectionStatus: string;
}

export interface CompanyServiceAccess {
  serviceKey: string;
  displayName: string;
  isEnabled: boolean;
  platformEnabled: boolean;
  platformConfigured: boolean;
  assignable: boolean;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  resourceType: string;
  resourceName: string;
  companyName: string | null;
  ipAddress: string;
}

export interface SystemService {
  name: string;
  status: "healthy" | "degraded" | "down";
  latencyMs: number | null;
  message: string;
}

export interface PlatformMetrics {
  totalCompanies: number;
  activeCompanies: number;
  trialCompanies: number;
  suspendedCompanies: number;
  activePipelines: number;
  monthlyPlatformCostUsd: number;
  monthlyTokenUsageM: number;
  failedPipelines24h: number;
}

export interface PipelineActivity {
  id: string;
  companyName: string;
  projectName: string;
  step: string;
  status: "running" | "completed" | "failed";
  startedAt: string;
}
