import axios, { isAxiosError } from "axios";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export const SESSION_KEY = "ai_dev_session";

export type Portal = "admin" | "company";

export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  isSuperAdmin: boolean;
  isActive: boolean;
}

export interface CompanyContext {
  id: string;
  name: string;
  slug: string;
  status: string;
  planName: string;
  role: string;
  emailDomain: string | null;
}

export interface AuthSession {
  portal: Portal;
  token: string;
  user: AuthUser;
  company: CompanyContext | null;
}

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

export function getStoredSession(): AuthSession | null {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthSession;
  } catch {
    return null;
  }
}

export function setStoredSession(session: AuthSession | null) {
  if (session) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
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
    url.includes("/api/auth/admin/login") || url.includes("/api/auth/company/login");
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
      if (session?.portal === "company" && session.company?.slug) {
        if (!path.includes("/login")) {
          window.location.href = `/c/${session.company.slug}/login`;
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

function mapCompany(raw: Record<string, unknown> | null | undefined): CompanyContext | null {
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
  return {
    portal: data.portal as Portal,
    token: String(data.access_token),
    user: mapUser(data.user as Record<string, unknown>),
    company: mapCompany(data.company as Record<string, unknown> | undefined),
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

  companyLogin: async (email: string, password: string, companySlug: string) => {
    const { data } = await api.post<Record<string, unknown>>("/api/auth/company/login", {
      email,
      password,
      company_slug: companySlug,
    });
    return mapTokenResponse(data);
  },

  logout: async () => {
    await api.post("/api/auth/logout");
  },

  me: async (token?: string) => {
    const { data } = await api.get<Record<string, unknown>>("/api/auth/me", {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    return {
      portal: data.portal as Portal,
      user: mapUser(data.user as Record<string, unknown>),
      company: mapCompany(data.company as Record<string, unknown> | undefined),
    };
  },
};
