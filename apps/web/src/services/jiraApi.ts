import { api } from "@/services/authApi";

export interface JiraConnectionStatus {
  isAssigned: boolean;
  isConnected: boolean;
  connectionStatus: string;
  jiraSiteName: string | null;
  oauthAvailable: boolean;
  message: string | null;
}

export interface JiraProject {
  id: string | null;
  key: string | null;
  name: string | null;
}

export interface JiraIssue {
  id: string | null;
  key: string | null;
  summary: string | null;
  description: string | null;
  issueType: string | null;
  status: string | null;
  priority: string | null;
  assignee: string | null;
  reporter: string | null;
  projectKey: string | null;
  projectName: string | null;
  url: string | null;
}

function mapIssue(row: Record<string, unknown>): JiraIssue {
  return {
    id: row.id != null ? String(row.id) : null,
    key: row.key != null ? String(row.key) : null,
    summary: row.summary != null ? String(row.summary) : null,
    description: row.description != null ? String(row.description) : null,
    issueType: row.issue_type != null ? String(row.issue_type) : null,
    status: row.status != null ? String(row.status) : null,
    priority: row.priority != null ? String(row.priority) : null,
    assignee: row.assignee != null ? String(row.assignee) : null,
    reporter: row.reporter != null ? String(row.reporter) : null,
    projectKey: row.project_key != null ? String(row.project_key) : null,
    projectName: row.project_name != null ? String(row.project_name) : null,
    url: row.url != null ? String(row.url) : null,
  };
}

function mapStatus(row: Record<string, unknown>): JiraConnectionStatus {
  return {
    isAssigned: Boolean(row.is_assigned),
    isConnected: Boolean(row.is_connected),
    connectionStatus: String(row.connection_status ?? "not_configured"),
    jiraSiteName: row.jira_site_name != null ? String(row.jira_site_name) : null,
    oauthAvailable: Boolean(row.oauth_available),
    message: row.message != null ? String(row.message) : null,
  };
}

export const jiraApi = {
  getStatus: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/workspace/jira/status");
    return mapStatus(data);
  },

  startOAuth: async (redirectPath?: string) => {
    const { data } = await api.get<Record<string, unknown>>("/api/workspace/jira/oauth/start", {
      params: redirectPath ? { redirect_path: redirectPath } : undefined,
    });
    return { authorizeUrl: String(data.authorize_url) };
  },

  disconnect: async () => {
    const { data } = await api.post<Record<string, unknown>>("/api/workspace/jira/disconnect");
    return mapStatus(data);
  },

  listProjects: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/jira/projects");
    return data.map(
      (row): JiraProject => ({
        id: row.id != null ? String(row.id) : null,
        key: row.key != null ? String(row.key) : null,
        name: row.name != null ? String(row.name) : null,
      })
    );
  },

  listIssues: async (params?: { projectKey?: string; jql?: string; maxResults?: number }) => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/jira/issues", {
      params: {
        project_key: params?.projectKey,
        jql: params?.jql,
        max_results: params?.maxResults,
      },
    });
    return data.map(mapIssue);
  },

  getIssue: async (issueKey: string) => {
    const { data } = await api.get<Record<string, unknown>>(`/api/workspace/jira/issues/${issueKey}`);
    return mapIssue(data);
  },
};
