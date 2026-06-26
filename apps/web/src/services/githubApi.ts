import { api } from "@/services/authApi";

export interface GitHubConnectionStatus {
  isAssigned: boolean;
  isConnected: boolean;
  connectionStatus: string;
  githubLogin: string | null;
  oauthAvailable: boolean;
  message: string | null;
}

export interface GitHubRepo {
  fullName: string;
  htmlUrl: string;
  defaultBranch: string;
  private: boolean;
}

function mapStatus(row: Record<string, unknown>): GitHubConnectionStatus {
  return {
    isAssigned: Boolean(row.is_assigned),
    isConnected: Boolean(row.is_connected),
    connectionStatus: String(row.connection_status ?? "not_configured"),
    githubLogin: row.github_login != null ? String(row.github_login) : null,
    oauthAvailable: Boolean(row.oauth_available),
    message: row.message != null ? String(row.message) : null,
  };
}

export const githubApi = {
  getStatus: async () => {
    const { data } = await api.get<Record<string, unknown>>("/api/workspace/github/status");
    return mapStatus(data);
  },

  startOAuth: async (redirectPath?: string) => {
    const { data } = await api.get<Record<string, unknown>>("/api/workspace/github/oauth/start", {
      params: redirectPath ? { redirect_path: redirectPath } : undefined,
    });
    return { authorizeUrl: String(data.authorize_url) };
  },

  disconnect: async () => {
    const { data } = await api.post<Record<string, unknown>>("/api/workspace/github/disconnect");
    return mapStatus(data);
  },

  listRepos: async () => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/github/repos");
    return data.map(
      (row): GitHubRepo => ({
        fullName: String(row.full_name),
        htmlUrl: String(row.html_url),
        defaultBranch: String(row.default_branch ?? "main"),
        private: Boolean(row.private),
      })
    );
  },

  verifyRepo: async (repoUrl: string) => {
    const { data } = await api.get<Record<string, unknown>>("/api/workspace/github/repos/verify", {
      params: { repo_url: repoUrl },
    });
    return {
      owner: String(data.owner),
      repo: String(data.repo),
      fullName: String(data.full_name),
      defaultBranch: String(data.default_branch),
      private: Boolean(data.private),
      htmlUrl: data.html_url != null ? String(data.html_url) : undefined,
    };
  },
};
