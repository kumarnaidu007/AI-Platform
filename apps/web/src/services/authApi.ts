import axios, { isAxiosError } from "axios";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export const SESSION_KEY = "ai_dev_session";

export type Portal = "admin" | "workspace" | "company";

export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  isSuperAdmin: boolean;
  isActive: boolean;
}

export interface WorkspaceContext {
  id: string;
  name: string;
  slug: string;
  status: string;
  planName: string;
  role: string;
  emailDomain: string | null;
}

/** @deprecated use WorkspaceContext */
export type CompanyContext = WorkspaceContext;

export interface AuthSession {
  portal: Portal;
  token: string;
  user: AuthUser;
  workspace: WorkspaceContext | null;
  /** @deprecated use workspace */
  company: WorkspaceContext | null;
}

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

export function getStoredSession(): AuthSession | null {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed.workspace && parsed.company) {
      parsed.workspace = parsed.company;
    }
    if (!parsed.company && parsed.workspace) {
      parsed.company = parsed.workspace;
    }
    if (parsed.portal === "company") {
      parsed.portal = "workspace";
    }
    return parsed;
  } catch {
    return null;
  }
}

export function setStoredSession(session: AuthSession | null) {
  if (session) {
    const normalized: AuthSession = {
      ...session,
      portal: session.portal === "company" ? "workspace" : session.portal,
      workspace: session.workspace ?? session.company,
      company: session.workspace ?? session.company,
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(normalized));
  } else {
    localStorage.removeItem(SESSION_KEY);
  }
}

export function getStoredToken(): string | null {
  return getStoredSession()?.token ?? null;
}

api.interceptors.request.use((config) => {
  const url = config.url ?? "";
  const isLogin =
    url.includes("/api/auth/admin/login") ||
    url.includes("/api/auth/workspace/login") ||
    url.includes("/api/auth/company/login");
  if (!isLogin) {
    const token = getStoredToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    const url = error.config?.url ?? "";
    const isAuthRoute = url.includes("/api/auth/");
    if (error.response?.status === 401 && !isAuthRoute) {
      const session = getStoredSession();
      setStoredSession(null);
      const path = window.location.pathname;
      if (session?.portal === "workspace" || session?.portal === "company") {
        if (!path.includes("/login")) {
          window.location.href = "/workspace/login";
        }
      } else if (!path.includes("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

function mapUser(raw: Record<string, unknown>): AuthUser {
  return {
    id: String(raw.id),
    email: String(raw.email),
    fullName: String(raw.full_name),
    isSuperAdmin: Boolean(raw.is_super_admin),
    isActive: Boolean(raw.is_active),
  };
}

function mapWorkspace(raw: Record<string, unknown> | null | undefined): WorkspaceContext | null {
  if (!raw) return null;
  return {
    id: String(raw.id),
    name: String(raw.name),
    slug: String(raw.slug),
    status: String(raw.status),
    planName: String(raw.plan_name),
    role: String(raw.role),
    emailDomain: (raw.email_domain as string | null) ?? null,
  };
}

function mapTokenResponse(data: Record<string, unknown>): AuthSession {
  const workspace = mapWorkspace(
    (data.workspace as Record<string, unknown> | undefined) ??
      (data.company as Record<string, unknown> | undefined)
  );
  const portal = data.portal === "company" ? "workspace" : (data.portal as Portal);
  return {
    portal,
    token: String(data.access_token),
    user: mapUser(data.user as Record<string, unknown>),
    workspace,
    company: workspace,
  };
}

export function getApiErrorMessage(error: unknown, fallback = "Request failed"): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
    if (error.response?.status === 401) return "Invalid email or password";
    if (error.response?.status === 403) return "Access denied";
    if (!error.response) return "Cannot reach API — is the backend running on port 8000?";
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

export const authApi = {
  adminLogin: async (email: string, password: string) => {
    const { data } = await api.post<Record<string, unknown>>("/api/auth/admin/login", { email, password });
    return mapTokenResponse(data);
  },

  workspaceLogin: async (email: string, password: string) => {
    const { data } = await api.post<Record<string, unknown>>("/api/auth/workspace/login", {
      email,
      password,
    });
    return mapTokenResponse(data);
  },

  /** @deprecated use workspaceLogin */
  companyLogin: async (email: string, password: string, _companySlug?: string) => {
    return authApi.workspaceLogin(email, password);
  },

  logout: async () => {
    await api.post("/api/auth/logout");
  },

  me: async (token?: string) => {
    const { data } = await api.get<Record<string, unknown>>("/api/auth/me", {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    const workspace = mapWorkspace(
      (data.workspace as Record<string, unknown> | undefined) ??
        (data.company as Record<string, unknown> | undefined)
    );
    const portal = data.portal === "company" ? "workspace" : (data.portal as Portal);
    return {
      portal,
      user: mapUser(data.user as Record<string, unknown>),
      workspace,
      company: workspace,
    };
  },
};
