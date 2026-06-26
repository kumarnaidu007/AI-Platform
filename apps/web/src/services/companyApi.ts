import { api } from "@/services/authApi";
import type { ConnectionStatus, IntegrationAuthType, IntegrationCategory } from "@/types/platform";
import type {
  CompanyAgentCatalogItem,
  MemberAgentAccess,
  MyAgentItem,
  ProjectAgentItem,
} from "@/types/agents";

export interface CompanyDashboard {
  companyName: string;
  companySlug: string;
  role: string;
  emailDomain: string | null;
  projectsCount: number;
  integrationsEnabled: number;
  servicesEnabled: number;
  teamCount: number;
}

export interface UserDashboard {
  companyName: string;
  companySlug: string;
  role: string;
  emailDomain: string | null;
  myProjectsCount: number;
  companyProjectsCount: number;
  integrationsAssigned: number;
  integrationsConnected: number;
  servicesEnabled: number;
  recentProjects: ProjectSummary[];
  integrationStatus: IntegrationStatusSummary[];
}

export interface IntegrationStatusSummary {
  integrationKey: string;
  name: string;
  isConnected: boolean;
  connectionStatus: ConnectionStatus;
}

export interface ProjectSummary {
  id: string;
  name: string;
  status: string;
  frontendStack?: string;
  backendStack?: string;
  createdAt: string;
  createdByName?: string;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  status: string;
  frontendStack?: string;
  backendStack?: string;
  dbType?: string;
  vcsProvider?: string;
  repoUrl?: string;
  pmTool?: string;
  notificationChannels: string[];
  monthlyTokenBudgetUsd?: number;
  createdBy: string;
  createdByName?: string;
  createdAt: string;
  updatedAt: string;
  pipelineRunsCount: number;
  activePipelineRuns: number;
}

export interface PipelineRun {
  id: string;
  status: string;
  currentStep?: string;
  startedAt?: string;
  finishedAt?: string;
  errorMessage?: string;
  createdAt: string;
  approvalPlan?: Record<string, unknown>;
}

export interface PipelineAgentLog {
  id: string;
  agentName: string;
  outputJson?: Record<string, unknown>;
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
  modelName?: string;
  createdAt: string;
}

export interface PipelineStep {
  id: string;
  stepName: string;
  stepOrder: number;
  status: string;
  retryCount: number;
  startedAt?: string;
  finishedAt?: string;
  errorMessage?: string;
  logs: PipelineAgentLog[];
}

export interface PipelineRunDetail {
  id: string;
  projectId: string;
  status: string;
  currentStep?: string;
  startedAt?: string;
  finishedAt?: string;
  errorMessage?: string;
  createdAt: string;
  approvalPlan?: Record<string, unknown>;
  steps: PipelineStep[];
  artifacts: Record<string, unknown>;
}

export interface UserProfile {
  id: string;
  email: string;
  fullName: string;
  role: string;
  isActive: boolean;
  joinedAt: string;
  integrationsAssigned: number;
  integrationsConnected: number;
}

export interface CompanyService {
  serviceKey: string;
  displayName: string;
  isGranted: boolean;
}

export interface CompanySettings {
  emailDomain: string | null;
  timezone: string;
}

export interface IntegrationCatalogItem {
  integrationKey: string;
  name: string;
  description: string;
  category: IntegrationCategory;
  authType: IntegrationAuthType;
  isGranted: boolean;
}

export interface MyIntegration {
  integrationKey: string;
  name: string;
  description: string;
  category: IntegrationCategory;
  authType: IntegrationAuthType;
  isAssigned: boolean;
  isConnected: boolean;
  connectionStatus: ConnectionStatus;
  connectionName?: string;
  configSchema: { fields: Array<{ key: string; label: string; type: string; required: boolean; default?: string | number }> };
  configMetadata: Record<string, string>;
  lastTestedAt?: string;
  lastTestStatus?: boolean;
  lastErrorMessage?: string;
}

export interface CompanyMember {
  id: string;
  userId: string;
  email: string;
  fullName: string;
  role: string;
  isActive: boolean;
  integrationsAssigned: number;
  agentsAssigned: number;
  joinedAt: string;
}

export interface MemberIntegrationAccess {
  integrationKey: string;
  name: string;
  category: string;
  isConnected: boolean;
  isAssigned: boolean;
}

function mapCatalog(raw: Record<string, unknown>): IntegrationCatalogItem {
  return {
    integrationKey: String(raw.integration_key),
    name: String(raw.name),
    description: String(raw.description ?? ""),
    category: raw.category as IntegrationCategory,
    authType: raw.auth_type as IntegrationAuthType,
    isGranted: Boolean(raw.is_granted),
  };
}

function mapMyIntegration(raw: Record<string, unknown>): MyIntegration {
  return {
    integrationKey: String(raw.integration_key),
    name: String(raw.name),
    description: String(raw.description ?? ""),
    category: raw.category as IntegrationCategory,
    authType: raw.auth_type as IntegrationAuthType,
    isAssigned: Boolean(raw.is_assigned),
    isConnected: Boolean(raw.is_connected),
    connectionStatus: (raw.connection_status as ConnectionStatus) ?? "not_configured",
    connectionName: raw.connection_name as string | undefined,
    configSchema: (raw.config_schema as MyIntegration["configSchema"]) ?? { fields: [] },
    configMetadata: (raw.config_metadata as Record<string, string>) ?? {},
    lastTestedAt: raw.last_tested_at as string | undefined,
    lastTestStatus: raw.last_test_status as boolean | undefined,
    lastErrorMessage: raw.last_error_message as string | undefined,
  };
}

function mapProjectSummary(raw: Record<string, unknown>): ProjectSummary {
  return {
    id: String(raw.id),
    name: String(raw.name),
    status: String(raw.status),
    frontendStack: raw.frontend_stack as string | undefined,
    backendStack: raw.backend_stack as string | undefined,
    createdAt: String(raw.created_at),
    createdByName: raw.created_by_name as string | undefined,
  };
}

function mapProject(raw: Record<string, unknown>): Project {
  return {
    id: String(raw.id),
    name: String(raw.name),
    description: raw.description as string | undefined,
    status: String(raw.status),
    frontendStack: raw.frontend_stack as string | undefined,
    backendStack: raw.backend_stack as string | undefined,
    dbType: raw.db_type as string | undefined,
    vcsProvider: raw.vcs_provider as string | undefined,
    repoUrl: raw.repo_url as string | undefined,
    pmTool: raw.pm_tool as string | undefined,
    notificationChannels: (raw.notification_channels as string[]) ?? [],
    monthlyTokenBudgetUsd: raw.monthly_token_budget_usd != null ? Number(raw.monthly_token_budget_usd) : undefined,
    createdBy: String(raw.created_by),
    createdByName: raw.created_by_name as string | undefined,
    createdAt: String(raw.created_at),
    updatedAt: String(raw.updated_at),
    pipelineRunsCount: Number(raw.pipeline_runs_count ?? 0),
    activePipelineRuns: Number(raw.active_pipeline_runs ?? 0),
  };
}

function mapPipelineRun(raw: Record<string, unknown>): PipelineRun {
  return {
    id: String(raw.id),
    status: String(raw.status),
    currentStep: raw.current_step as string | undefined,
    startedAt: raw.started_at as string | undefined,
    finishedAt: raw.finished_at as string | undefined,
    errorMessage: raw.error_message as string | undefined,
    createdAt: String(raw.created_at),
    approvalPlan: raw.approval_plan as Record<string, unknown> | undefined,
  };
}

function mapPipelineRunDetail(raw: Record<string, unknown>): PipelineRunDetail {
  const steps = Array.isArray(raw.steps) ? raw.steps : [];
  return {
    id: String(raw.id),
    projectId: String(raw.project_id),
    status: String(raw.status),
    currentStep: raw.current_step as string | undefined,
    startedAt: raw.started_at as string | undefined,
    finishedAt: raw.finished_at as string | undefined,
    errorMessage: raw.error_message as string | undefined,
    createdAt: String(raw.created_at),
    approvalPlan: raw.approval_plan as Record<string, unknown> | undefined,
    steps: steps.map((step) => {
      const s = step as Record<string, unknown>;
      const logs = Array.isArray(s.logs) ? s.logs : [];
      return {
        id: String(s.id),
        stepName: String(s.step_name),
        stepOrder: Number(s.step_order),
        status: String(s.status),
        retryCount: Number(s.retry_count ?? 0),
        startedAt: s.started_at as string | undefined,
        finishedAt: s.finished_at as string | undefined,
        errorMessage: s.error_message as string | undefined,
        logs: logs.map((log) => {
          const l = log as Record<string, unknown>;
          return {
            id: String(l.id),
            agentName: String(l.agent_name),
            outputJson: l.output_json as Record<string, unknown> | undefined,
            inputTokens: Number(l.input_tokens ?? 0),
            outputTokens: Number(l.output_tokens ?? 0),
            costUsd: Number(l.cost_usd ?? 0),
            modelName: l.model_name as string | undefined,
            createdAt: String(l.created_at),
          };
        }),
      };
    }),
    artifacts: (raw.artifacts as Record<string, unknown>) ?? {},
  };
}

function mapProfile(raw: Record<string, unknown>): UserProfile {
  return {
    id: String(raw.id),
    email: String(raw.email),
    fullName: String(raw.full_name),
    role: String(raw.role),
    isActive: Boolean(raw.is_active),
    joinedAt: String(raw.joined_at),
    integrationsAssigned: Number(raw.integrations_assigned ?? 0),
    integrationsConnected: Number(raw.integrations_connected ?? 0),
  };
}

function mapMember(raw: Record<string, unknown>): CompanyMember {
  return {
    id: String(raw.id),
    userId: String(raw.user_id),
    email: String(raw.email),
    fullName: String(raw.full_name),
    role: String(raw.role),
    isActive: Boolean(raw.is_active),
    integrationsAssigned: Number(raw.integrations_assigned ?? 0),
    agentsAssigned: Number(raw.agents_assigned ?? 0),
    joinedAt: String(raw.joined_at),
  };
}

function mapMemberIntegration(raw: Record<string, unknown>): MemberIntegrationAccess {
  return {
    integrationKey: String(raw.integration_key),
    name: String(raw.name),
    category: String(raw.category),
    isConnected: Boolean(raw.is_connected),
    isAssigned: Boolean(raw.is_assigned),
  };
}

function mapUserDashboard(raw: Record<string, unknown>): UserDashboard {
  return {
    companyName: String(raw.company_name),
    companySlug: String(raw.company_slug),
    role: String(raw.role),
    emailDomain: (raw.email_domain as string | null) ?? null,
    myProjectsCount: Number(raw.my_projects_count ?? 0),
    companyProjectsCount: Number(raw.company_projects_count ?? 0),
    integrationsAssigned: Number(raw.integrations_assigned ?? 0),
    integrationsConnected: Number(raw.integrations_connected ?? 0),
    servicesEnabled: Number(raw.services_enabled ?? 0),
    recentProjects: ((raw.recent_projects as Record<string, unknown>[]) ?? []).map(mapProjectSummary),
    integrationStatus: ((raw.integration_status as Record<string, unknown>[]) ?? []).map((row) => ({
      integrationKey: String(row.integration_key),
      name: String(row.name),
      isConnected: Boolean(row.is_connected),
      connectionStatus: (row.connection_status as ConnectionStatus) ?? "not_configured",
    })),
  };
}

export const companyApi = {
  getDashboard: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/workspace/dashboard");
    return {
      companyName: String(data.company_name),
      companySlug: String(data.company_slug),
      role: String(data.role),
      emailDomain: (data.email_domain as string | null) ?? null,
      projectsCount: Number(data.projects_count),
      integrationsEnabled: Number(data.integrations_enabled),
      servicesEnabled: Number(data.services_enabled),
      teamCount: Number(data.team_count ?? 0),
    } as CompanyDashboard;
  },

  getUserDashboard: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/workspace/user-dashboard");
    return mapUserDashboard(data);
  },

  getProfile: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/workspace/profile");
    return mapProfile(data);
  },

  updateProfile: async (fullName: string) => {
    const { data } = await api.patch<Record<string, unknown>>("/api/workspace/profile", { full_name: fullName });
    return mapProfile(data);
  },

  changePassword: async (currentPassword: string, newPassword: string) => {
    const { data } = await api.post<{ success: boolean; message: string }>("/api/workspace/profile/password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return data;
  },

  getSettings: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/workspace/settings");
    return {
      emailDomain: (data.email_domain as string | null) ?? null,
      timezone: String(data.timezone ?? "UTC"),
    } as CompanySettings;
  },

  updateSettings: async (emailDomain: string) => {
    const { data } = await api.patch<Record<string, unknown>>("/api/workspace/settings", {
      email_domain: emailDomain,
    });
    return {
      emailDomain: (data.email_domain as string | null) ?? null,
      timezone: String(data.timezone ?? "UTC"),
    } as CompanySettings;
  },

  getIntegrationCatalog: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/integrations");
    return data.map(mapCatalog);
  },

  getMyIntegrations: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/my-integrations");
    return data.map(mapMyIntegration);
  },

  getMyIntegration: async (key: string) => {
    const { data } = await api.get<Record<string, unknown>>(`/api/workspace/my-integrations/${key}`);
    return mapMyIntegration(data);
  },

  saveMyIntegrationConnection: async (key: string, connectionName: string, config: Record<string, string>) => {
    const { data } = await api.put<Record<string, unknown>>(`/api/workspace/my-integrations/${key}/connection`, {
      connection_name: connectionName,
      config,
    });
    return mapMyIntegration(data);
  },

  testMyIntegration: async (key: string) => {
    const { data } = await api.post<{ success: boolean; message: string }>(
      `/api/workspace/my-integrations/${key}/test`
    );
    return data;
  },

  deleteMyIntegrationConnection: async (key: string) => {
    const { data } = await api.delete<Record<string, unknown>>(`/api/workspace/my-integrations/${key}/connection`);
    return mapMyIntegration(data);
  },

  getServices: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/services");
    return data.map(
      (row): CompanyService => ({
        serviceKey: String(row.service_key),
        displayName: String(row.display_name),
        isGranted: Boolean(row.is_granted),
      })
    );
  },

  getProjects: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/projects");
    return data.map(mapProjectSummary);
  },

  getProject: async (projectId: string) => {
    const { data } = await api.get<Record<string, unknown>>(`/api/workspace/projects/${projectId}`);
    return mapProject(data);
  },

  createProject: async (payload: {
    name: string;
    description?: string;
    frontendStack?: string;
    backendStack?: string;
    dbType?: string;
    vcsProvider?: string;
    repoUrl?: string;
    pmTool?: string;
  }) => {
    const { data } = await api.post<Record<string, unknown>>("/api/workspace/projects", {
      name: payload.name,
      description: payload.description,
      frontend_stack: payload.frontendStack,
      backend_stack: payload.backendStack,
      db_type: payload.dbType,
      vcs_provider: payload.vcsProvider ?? "github",
      repo_url: payload.repoUrl,
      pm_tool: payload.pmTool,
    });
    return mapProject(data);
  },

  updateProject: async (
    projectId: string,
    payload: { name?: string; description?: string; status?: string; repoUrl?: string }
  ) => {
    const { data } = await api.patch<Record<string, unknown>>(`/api/workspace/projects/${projectId}`, {
      name: payload.name,
      description: payload.description,
      status: payload.status,
      repo_url: payload.repoUrl,
    });
    return mapProject(data);
  },

  getProjectRuns: async (projectId: string) => {
    const { data } = await api.get<Record<string, unknown>[]>(`/api/workspace/projects/${projectId}/runs`);
    return data.map(mapPipelineRun);
  },

  startPipelineRun: async (
    projectId: string,
    options: {
      requirementsText?: string;
      jiraIssueKey?: string;
      agentKeys?: string[];
    }
  ) => {
    const { data } = await api.post<Record<string, unknown>>(`/api/workspace/projects/${projectId}/runs`, {
      requirements_text: options.requirementsText ?? "",
      jira_issue_key: options.jiraIssueKey,
      agent_keys: options.agentKeys,
    });
    return mapPipelineRun(data);
  },

  getPipelineRunDetail: async (projectId: string, runId: string) => {
    const { data } = await api.get<Record<string, unknown>>(
      `/api/workspace/projects/${projectId}/runs/${runId}`
    );
    return mapPipelineRunDetail(data);
  },

  approvePipelineRun: async (projectId: string, runId: string, comment?: string) => {
    const { data } = await api.post<Record<string, unknown>>(
      `/api/workspace/projects/${projectId}/runs/${runId}/approve`,
      { comment }
    );
    return mapPipelineRun(data);
  },

  rejectPipelineRun: async (projectId: string, runId: string, comment?: string) => {
    const { data } = await api.post<Record<string, unknown>>(
      `/api/workspace/projects/${projectId}/runs/${runId}/reject`,
      { comment }
    );
    return mapPipelineRun(data);
  },

  getMembers: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/members");
    return data.map(mapMember);
  },

  getMember: async (memberId: string) => {
    const { data } = await api.get<Record<string, unknown>>(`/api/workspace/members/${memberId}`);
    return mapMember(data);
  },

  createMember: async (payload: { email: string; fullName: string; password: string; role: string }) => {
    const { data } = await api.post<Record<string, unknown>>("/api/workspace/members", {
      email: payload.email,
      full_name: payload.fullName,
      password: payload.password,
      role: payload.role,
    });
    return mapMember(data);
  },

  updateMember: async (memberId: string, payload: { role?: string; isActive?: boolean }) => {
    const { data } = await api.patch<Record<string, unknown>>(`/api/workspace/members/${memberId}`, {
      role: payload.role,
      is_active: payload.isActive,
    });
    return mapMember(data);
  },

  getMemberIntegrations: async (memberId: string) => {
    const { data } = await api.get<Record<string, unknown>[]>(`/api/workspace/members/${memberId}/integrations`);
    return data.map(mapMemberIntegration);
  },

  updateMemberIntegrations: async (
    memberId: string,
    integrations: Array<{ integrationKey: string; isAssigned: boolean }>
  ) => {
    const { data } = await api.put<Record<string, unknown>[]>(`/api/workspace/members/${memberId}/integrations`, {
      integrations: integrations.map((i) => ({
        integration_key: i.integrationKey,
        is_assigned: i.isAssigned,
      })),
    });
    return data.map(mapMemberIntegration);
  },

  getAgentCatalog: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/agents");
    return data.map(
      (row): CompanyAgentCatalogItem => ({
        agentKey: String(row.agent_key),
        name: String(row.name),
        description: row.description != null ? String(row.description) : null,
        category: String(row.category),
        group: row.group != null ? String(row.group) : null,
        defaultStepOrder: Number(row.default_step_order),
        isGranted: Boolean(row.is_granted ?? true),
      })
    );
  },

  getMyAgents: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/my-agents");
    return data.map(
      (row): MyAgentItem => ({
        agentKey: String(row.agent_key),
        name: String(row.name),
        description: row.description != null ? String(row.description) : null,
        category: String(row.category),
        group: row.group != null ? String(row.group) : null,
        defaultStepOrder: Number(row.default_step_order),
        isAssigned: Boolean(row.is_assigned),
        isEnabledOnPlatform: Boolean(row.is_enabled_on_platform ?? true),
      })
    );
  },

  getMemberAgents: async (memberId: string) => {
    const { data } = await api.get<Record<string, unknown>[]>(`/api/workspace/members/${memberId}/agents`);
    return data.map(
      (row): MemberAgentAccess => ({
        agentKey: String(row.agent_key),
        name: String(row.name),
        category: String(row.category),
        group: row.group != null ? String(row.group) : null,
        defaultStepOrder: Number(row.default_step_order),
        isAssigned: Boolean(row.is_assigned),
      })
    );
  },

  updateMemberAgents: async (
    memberId: string,
    agents: Array<{ agentKey: string; isAssigned: boolean }>
  ) => {
    const { data } = await api.put<Record<string, unknown>[]>(`/api/workspace/members/${memberId}/agents`, {
      agents: agents.map((a) => ({
        agent_key: a.agentKey,
        is_assigned: a.isAssigned,
      })),
    });
    return data.map(
      (row): MemberAgentAccess => ({
        agentKey: String(row.agent_key),
        name: String(row.name),
        category: String(row.category),
        group: row.group != null ? String(row.group) : null,
        defaultStepOrder: Number(row.default_step_order),
        isAssigned: Boolean(row.is_assigned),
      })
    );
  },

  getProjectAgents: async (projectId: string) => {
    const { data } = await api.get<Record<string, unknown>[]>(`/api/workspace/projects/${projectId}/agents`);
    return data.map(
      (row): ProjectAgentItem => ({
        agentKey: String(row.agent_key),
        name: String(row.name),
        category: String(row.category),
        group: row.group != null ? String(row.group) : null,
        stepOrder: Number(row.step_order),
        isEnabled: Boolean(row.is_enabled),
        isAssigned: Boolean(row.is_assigned),
        defaultStepOrder: Number(row.default_step_order),
      })
    );
  },

  updateProjectAgents: async (
    projectId: string,
    agents: Array<{ agentKey: string; isEnabled: boolean; stepOrder?: number }>
  ) => {
    const { data } = await api.put<Record<string, unknown>[]>(`/api/workspace/projects/${projectId}/agents`, {
      agents: agents.map((a) => ({
        agent_key: a.agentKey,
        is_enabled: a.isEnabled,
        step_order: a.stepOrder,
      })),
    });
    return data.map(
      (row): ProjectAgentItem => ({
        agentKey: String(row.agent_key),
        name: String(row.name),
        category: String(row.category),
        group: row.group != null ? String(row.group) : null,
        stepOrder: Number(row.step_order),
        isEnabled: Boolean(row.is_enabled),
        isAssigned: Boolean(row.is_assigned),
        defaultStepOrder: Number(row.default_step_order),
      })
    );
  },
};
