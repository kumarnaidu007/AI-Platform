import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  authApi,
  getStoredSession,
  setStoredSession,
  type AuthSession,
  type CompanyContext,
  type Portal,
} from "@/services/authApi";

interface AuthContextValue {
  session: AuthSession | null;
  user: AuthSession["user"] | null;
  company: CompanyContext | null;
  portal: Portal | null;
  isLoading: boolean;
  adminLogin: (email: string, password: string) => Promise<void>;
  companyLogin: (email: string, password: string, companySlug: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(() => getStoredSession());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = getStoredSession();
    if (!stored?.token) {
      setIsLoading(false);
      return;
    }
    authApi
      .me(stored.token)
      .then((me) => {
        setSession({
          portal: me.portal,
          token: stored.token,
          user: me.user,
          company: me.company,
        });
        setStoredSession({
          portal: me.portal,
          token: stored.token,
          user: me.user,
          company: me.company,
        });
      })
      .catch(() => {
        setStoredSession(null);
        setSession(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const adminLogin = useCallback(async (email: string, password: string) => {
    setStoredSession(null);
    const next = await authApi.adminLogin(email.trim(), password);
    setStoredSession(next);
    setSession(next);
  }, []);

  const companyLogin = useCallback(async (email: string, password: string, companySlug: string) => {
    setStoredSession(null);
    const next = await authApi.companyLogin(email.trim(), password, companySlug);
    setStoredSession(next);
    setSession(next);
  }, []);

  const logout = useCallback(async () => {
    try {
      if (session?.token) {
        await authApi.logout();
      }
    } catch {
      // clear local session even if API fails
    } finally {
      setStoredSession(null);
      setSession(null);
    }
  }, [session?.token]);

  const value = useMemo(
    () => ({
      session,
      user: session?.user ?? null,
      company: session?.company ?? null,
      portal: session?.portal ?? null,
      isLoading,
      adminLogin,
      companyLogin,
      logout,
    }),
    [session, isLoading, adminLogin, companyLogin, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export { getStoredSession, getStoredToken } from "@/services/authApi";
