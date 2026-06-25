import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "@/context/AuthContext";
import { LoadingState } from "./LoadingState";
import type { Portal } from "@/services/authApi";

export function ProtectedRoute({ children, portal }: { children: ReactNode; portal: Portal }) {
  const { portal: sessionPortal, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState />
      </div>
    );
  }

  if (sessionPortal !== portal) {
    const loginPath = portal === "admin" ? "/login" : "/login";
    return <Navigate to={loginPath} state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}
