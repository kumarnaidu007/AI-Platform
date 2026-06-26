import { api } from "@/services/authApi";
import type {
  ConnectionStatus,
  IntegrationAuthType,
  IntegrationCategory,
  PlatformIntegration,
  PlatformService,
  PlatformSetting,
} from "@/types/platform";
import type { AuditEvent, Company, CompanyDetail, CompanyIntegrationAccess, CompanyServiceAccess, Plan, PlatformMetrics } from "@/types/admin";
import type { CompanyAgentAccess, PlatformAgent } from "@/types/agents";

// api client with auth interceptors — see authApi.ts

// ─── Mappers (API snake_case → UI camelCase) ─────────────────────────────────

function mapIntegration(raw: Record<string, unknown>): PlatformIntegration {
  return {
    id: String(raw.id),
    integrationKey: String(raw.integration_key),
    name: String(raw.name),
    description: String(raw.description ?? ""),
    category: raw.category as IntegrationCategory,
    authType: raw.auth_type as IntegrationAuthType,
    isEnabled: Boolean(raw.is_enabled),
    configSchema: (raw.config_schema as PlatformIntegration["configSchema"]) ?? { fields: [] },
    documentationUrl: raw.documentation_url as string | undefined,
    connectionStatus: raw.connection_status as ConnectionStatus,
    connectionName: raw.connection_name as string | undefined,
    lastTestedAt: raw.last_tested_at as string | undefined,
    lastTestStatus: raw.last_test_status as boolean | undefined,
    lastErrorMessage: raw.last_error_message as string | undefined,
    configMetadata: (raw.config_metadata as Record<string, string>) ?? {},
  };
}

function mapService(raw: Record<string, unknown>): PlatformService {
  return {
    id: String(raw.id),
    serviceKey: String(raw.service_key),
    displayName: String(raw.display_name),
    description: String(raw.description ?? ""),
    isEnabled: Boolean(raw.is_enabled),
    isConfigured: Boolean(raw.is_configured),
    configMetadata: (raw.config_metadata as Record<string, string | number>) ?? {},
    lastTestedAt: raw.last_tested_at as string | undefined,
    lastTestStatus: raw.last_test_status as boolean | undefined,
    lastErrorMessage: raw.last_error_message as string | undefined,
  };
}

function mapSetting(raw: Record<string, unknown>): PlatformSetting {
  return {
    key: String(raw.key),
    label: String(raw.label),
    description: String(raw.description ?? ""),
    type: raw.type as PlatformSetting["type"],
    value: raw.value as string | boolean | number,
  };
}

function mapCompany(raw: Record<string, unknown>): Company {
  return {
    id: String(raw.id),
    name: String(raw.name),
    slug: String(raw.slug),
    status: raw.status as Company["status"],
    planId: String(raw.plan_id),
    planName: String(raw.plan_name),
    usersCount: Number(raw.users_count),
    projectsCount: Number(raw.projects_count),
    activePipelines: Number(raw.active_pipelines),
    monthlyUsageUsd: Number(raw.monthly_usage_usd),
    createdAt: String(raw.created_at).slice(0, 10),
  };
}

function mapPlan(raw: Record<string, unknown>): Plan {
  return {
    id: String(raw.id),
    name: String(raw.name),
    maxProjects: Number(raw.max_projects),
    maxParallelPipelines: Number(raw.max_parallel_pipelines),
    monthlyTokenBudgetUsd: Number(raw.monthly_token_budget_usd),
    isActive: Boolean(raw.is_active),
    companiesCount: Number(raw.companies_count),
    integrationKeys: (raw.integration_keys as string[]) ?? [],
  };
}

// ─── API calls ───────────────────────────────────────────────────────────────

export const adminApi = {
  getIntegrations: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/admin/integrations");
    return data.map(mapIntegration);
  },

  getIntegration: async (key: string) => {
    const { data } = await api.get<Record<string, unknown>>(`/api/admin/integrations/${key}`);
    return mapIntegration(data);
  },

  saveIntegrationConnection: async (key: string, connectionName: string, config: Record<string, string>) => {
    const { data } = await api.put<Record<string, unknown>>(`/api/admin/integrations/${key}/connection`, {
      connection_name: connectionName,
      config,
    });
    return mapIntegration(data);
  },

  testIntegration: async (key: string) => {
    const { data } = await api.post<{ success: boolean; message: string }>(
      `/api/admin/integrations/${key}/test`
    );
    return data;
  },

  deleteIntegrationConnection: async (key: string) => {
    const { data } = await api.delete<Record<string, unknown>>(`/api/admin/integrations/${key}/connection`);
    return mapIntegration(data);
  },

  getPlatformServices: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/admin/platform-services");
    return data.map(mapService);
  },

  updatePlatformService: async (
    serviceKey: string,
    patch: { isEnabled?: boolean; apiKey?: string; configMetadata?: Record<string, string> }
  ) => {
    const { data } = await api.patch<Record<string, unknown>>(`/api/admin/platform-services/${serviceKey}`, {
      is_enabled: patch.isEnabled,
      api_key: patch.apiKey,
      config_metadata: patch.configMetadata,
    });
    return mapService(data);
  },

  testPlatformService: async (serviceKey: string) => {
    const { data } = await api.post<{ success: boolean; message: string }>(
      `/api/admin/platform-services/${serviceKey}/test`
    );
    return data;
  },

  getPlatformSettings: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/admin/platform-settings");
    return data.map(mapSetting);
  },

  updatePlatformSettings: async (settings: Record<string, unknown>) => {
    const { data } = await api.put<Record<string, unknown>[]>("/api/admin/platform-settings", {
      settings,
    });
    return data.map(mapSetting);
  },

  getPlans: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/admin/plans");
    return data.map(mapPlan);
  },

  getCompanies: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/admin/companies");
    return data.map(mapCompany);
  },

  getCompany: async (id: string) => {
    const { data } = await api.get<Record<string, unknown>>(`/api/admin/companies/${id}`);
    return {
      ...mapCompany(data),
      adminEmail: data.admin_email as string,
      adminName: data.admin_name as string,
      limitsOverride: (data.limits_override as CompanyDetail["limitsOverride"]) ?? {
        maxProjects: null,
        maxParallelPipelines: null,
        monthlyTokenBudgetUsd: null,
      },
      recentProjects: (data.recent_projects as CompanyDetail["recentProjects"]) ?? [],
    } as CompanyDetail;
  },

  getCompanyMembers: async (teamId: string) => {
    const { data } = await api.get<Record<string, unknown>[]>(`/api/admin/companies/${teamId}/members`);
    return data.map((row) => ({
      id: String(row.id),
      userId: String(row.user_id),
      email: String(row.email),
      fullName: String(row.full_name),
      role: String(row.role),
      isActive: Boolean(row.is_active),
      integrationsAssigned: Number(row.integrations_assigned ?? 0),
      agentsAssigned: Number(row.agents_assigned ?? 0),
      joinedAt: String(row.joined_at),
    }));
  },

  createCompany: async (body: {
    name: string;
    slug: string;
    planId: string;
    status: string;
    emailDomain?: string;
    adminName?: string;
    adminEmail?: string;
    adminPassword?: string;
  }) => {
    const { data } = await api.post<Record<string, unknown>>("/api/admin/companies", {
      name: body.name,
      slug: body.slug,
      plan_id: body.planId,
      status: body.status,
      email_domain: body.emailDomain,
      admin_name: body.adminName,
      admin_email: body.adminEmail,
      admin_password: body.adminPassword,
    });
    return mapCompany(data);
  },

  updateCompany: async (id: string, patch: { name?: string; status?: string; planId?: string }) => {
    const { data } = await api.patch<Record<string, unknown>>(`/api/admin/companies/${id}`, {
      name: patch.name,
      status: patch.status,
      plan_id: patch.planId,
    });
    return mapCompany(data);
  },

  getDashboard: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/admin/dashboard");
    const ps = data.platform_stats as Record<string, number>;
    return {
      platformStats: {
        totalIntegrations: ps.total_integrations,
        enabledIntegrations: ps.enabled_integrations,
        connectedIntegrations: ps.connected_integrations,
        errorIntegrations: ps.error_integrations,
        notConfiguredIntegrations: ps.not_configured_integrations,
        servicesEnabled: ps.services_enabled,
        totalServices: ps.total_services,
      },
      metrics: {
        totalCompanies: Number(data.total_companies),
        activeCompanies: Number(data.active_companies),
        trialCompanies: Number(data.trial_companies),
        suspendedCompanies: Number(data.suspended_companies),
        activePipelines: Number(data.active_pipelines),
        monthlyPlatformCostUsd: Number(data.monthly_platform_cost_usd),
        monthlyTokenUsageM: Number(data.monthly_token_usage_m),
        failedPipelines24h: Number(data.failed_pipelines_24h),
      } as PlatformMetrics,
    };
  },

  getPipelineActivity: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/admin/dashboard/pipeline-activity");
    return data.map((p) => ({
      id: String(p.id),
      companyName: String(p.company_name),
      projectName: String(p.project_name),
      step: String(p.step),
      status: p.status as "running" | "completed" | "failed",
      startedAt: String(p.started_at ?? ""),
    }));
  },

  getAuditLog: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/admin/audit-log");
    return data.map(
      (e): AuditEvent => ({
        id: String(e.id),
        timestamp: String(e.timestamp),
        user: String(e.user),
        action: String(e.action),
        resourceType: String(e.resource_type),
        resourceName: String(e.resource_name),
        companyName: e.company_name as string | null,
        ipAddress: String(e.ip_address ?? ""),
      })
    );
  },

  getSystemHealth: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/admin/system-health");
    return {
      healthy: Number(data.healthy),
      degraded: Number(data.degraded),
      down: Number(data.down),
      services: (data.services as Array<Record<string, unknown>>).map((s) => ({
        name: String(s.name),
        status: s.status as "healthy" | "degraded" | "down",
        latencyMs: s.latency_ms as number | null,
        message: String(s.message),
      })),
      queue: data.queue as Record<string, number>,
    };
  },

  getCompanyIntegrationsAccess: async (companyId: string) => {
    const { data } = await api.get<Record<string, unknown>[]>(
      `/api/admin/companies/${companyId}/integrations-access`
    );
    return data.map(
      (row): CompanyIntegrationAccess => ({
        integrationKey: String(row.integration_key),
        name: String(row.name),
        category: String(row.category),
        isEnabled: Boolean(row.is_enabled),
        platformEnabled: Boolean(row.platform_enabled),
        platformConnected: Boolean(row.platform_connected),
        assignable: Boolean(row.assignable),
        connectionStatus: String(row.connection_status),
      })
    );
  },

  updateCompanyIntegrationsAccess: async (
    companyId: string,
    integrations: { integrationKey: string; isEnabled: boolean }[]
  ) => {
    const { data } = await api.put<Record<string, unknown>[]>(
      `/api/admin/companies/${companyId}/integrations-access`,
      {
        integrations: integrations.map((i) => ({
          integration_key: i.integrationKey,
          is_enabled: i.isEnabled,
        })),
      }
    );
    return data.map(
      (row): CompanyIntegrationAccess => ({
        integrationKey: String(row.integration_key),
        name: String(row.name),
        category: String(row.category),
        isEnabled: Boolean(row.is_enabled),
        platformEnabled: Boolean(row.platform_enabled),
        platformConnected: Boolean(row.platform_connected),
        assignable: Boolean(row.assignable),
        connectionStatus: String(row.connection_status),
      })
    );
  },

  getCompanyServicesAccess: async (companyId: string) => {
    const { data } = await api.get<Record<string, unknown>[]>(
      `/api/admin/companies/${companyId}/services-access`
    );
    return data.map(
      (row): CompanyServiceAccess => ({
        serviceKey: String(row.service_key),
        displayName: String(row.display_name),
        isEnabled: Boolean(row.is_enabled),
        platformEnabled: Boolean(row.platform_enabled),
        platformConfigured: Boolean(row.platform_configured),
        assignable: Boolean(row.assignable),
      })
    );
  },

  updateCompanyServicesAccess: async (
    companyId: string,
    services: { serviceKey: string; isEnabled: boolean }[]
  ) => {
    const { data } = await api.put<Record<string, unknown>[]>(
      `/api/admin/companies/${companyId}/services-access`,
      {
        services: services.map((s) => ({
          service_key: s.serviceKey,
          is_enabled: s.isEnabled,
        })),
      }
    );
    return data.map(
      (row): CompanyServiceAccess => ({
        serviceKey: String(row.service_key),
        displayName: String(row.display_name),
        isEnabled: Boolean(row.is_enabled),
        platformEnabled: Boolean(row.platform_enabled),
        platformConfigured: Boolean(row.platform_configured),
        assignable: Boolean(row.assignable),
      })
    );
  },

  getAgents: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/admin/agents");
    return data.map(
      (row): PlatformAgent => ({
        id: String(row.id),
        agentKey: String(row.agent_key),
        name: String(row.name),
        description: row.description != null ? String(row.description) : null,
        category: row.category as PlatformAgent["category"],
        defaultStepOrder: Number(row.default_step_order),
        isEnabled: Boolean(row.is_enabled),
        group: row.group != null ? String(row.group) : null,
        artifact: row.artifact != null ? String(row.artifact) : null,
      })
    );
  },

  updateAgent: async (key: string, patch: { isEnabled?: boolean }) => {
    const { data } = await api.patch<Record<string, unknown>>(`/api/admin/agents/${key}`, {
      is_enabled: patch.isEnabled,
    });
    return {
      id: String(data.id),
      agentKey: String(data.agent_key),
      name: String(data.name),
      description: data.description != null ? String(data.description) : null,
      category: data.category as PlatformAgent["category"],
      defaultStepOrder: Number(data.default_step_order),
      isEnabled: Boolean(data.is_enabled),
      group: data.group != null ? String(data.group) : null,
      artifact: data.artifact != null ? String(data.artifact) : null,
    } satisfies PlatformAgent;
  },

  getCompanyAgentsAccess: async (companyId: string) => {
    const { data } = await api.get<Record<string, unknown>[]>(
      `/api/admin/companies/${companyId}/agents-access`
    );
    return data.map(
      (row): CompanyAgentAccess => ({
        agentKey: String(row.agent_key),
        name: String(row.name),
        category: String(row.category),
        group: row.group != null ? String(row.group) : null,
        defaultStepOrder: Number(row.default_step_order),
        isEnabled: Boolean(row.is_enabled),
        platformEnabled: Boolean(row.platform_enabled),
        assignable: Boolean(row.assignable),
      })
    );
  },

  updateCompanyAgentsAccess: async (
    companyId: string,
    agents: { agentKey: string; isEnabled: boolean }[]
  ) => {
    const { data } = await api.put<Record<string, unknown>[]>(
      `/api/admin/companies/${companyId}/agents-access`,
      {
        agents: agents.map((a) => ({
          agent_key: a.agentKey,
          is_enabled: a.isEnabled,
        })),
      }
    );
    return data.map(
      (row): CompanyAgentAccess => ({
        agentKey: String(row.agent_key),
        name: String(row.name),
        category: String(row.category),
        group: row.group != null ? String(row.group) : null,
        defaultStepOrder: Number(row.default_step_order),
        isEnabled: Boolean(row.is_enabled),
        platformEnabled: Boolean(row.platform_enabled),
        assignable: Boolean(row.assignable),
      })
    );
  },

  getWorkspace: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/admin/workspace");
    return {
      id: String(data.id),
      name: String(data.name),
      slug: String(data.slug),
      status: String(data.status),
      planName: String(data.plan_name),
      membersCount: Number(data.members_count ?? 0),
    };
  },

  getWorkspaceMembers: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/admin/workspace/members");
    return data.map((row) => ({
      id: String(row.id),
      userId: String(row.user_id),
      email: String(row.email),
      fullName: String(row.full_name),
      role: String(row.role),
      isActive: Boolean(row.is_active),
      joinedAt: String(row.joined_at),
    }));
  },

  getUsage: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/admin/usage");
    const totals = data.totals as Record<string, unknown>;
    const byUser = Array.isArray(data.by_user) ? data.by_user : [];
    const byProject = Array.isArray(data.by_project) ? data.by_project : [];
    return {
      totals: {
        inputTokens: Number(totals.input_tokens ?? 0),
        outputTokens: Number(totals.output_tokens ?? 0),
        totalTokens: Number(totals.total_tokens ?? 0),
        costUsd: Number(totals.cost_usd ?? 0),
        events: Number(totals.events ?? 0),
      },
      byUser: byUser.map((row) => {
        const r = row as Record<string, unknown>;
        return {
          userId: r.user_id != null ? String(r.user_id) : null,
          userName: String(r.user_name ?? "Unknown"),
          userEmail: r.user_email != null ? String(r.user_email) : null,
          inputTokens: Number(r.input_tokens ?? 0),
          outputTokens: Number(r.output_tokens ?? 0),
          totalTokens: Number(r.total_tokens ?? 0),
          costUsd: Number(r.cost_usd ?? 0),
          events: Number(r.events ?? 0),
        };
      }),
      byProject: byProject.map((row) => {
        const r = row as Record<string, unknown>;
        return {
          projectId: String(r.project_id),
          projectName: String(r.project_name ?? "Unknown"),
          inputTokens: Number(r.input_tokens ?? 0),
          outputTokens: Number(r.output_tokens ?? 0),
          totalTokens: Number(r.total_tokens ?? 0),
          costUsd: Number(r.cost_usd ?? 0),
          events: Number(r.events ?? 0),
        };
      }),
    };
  },
};
