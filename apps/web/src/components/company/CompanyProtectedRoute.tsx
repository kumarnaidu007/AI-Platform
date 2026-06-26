import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { LoadingState } from "@/components/admin/LoadingState";

export function CompanyProtectedRoute() {
  const { portal, workspace, company, isLoading } = useAuth();
  const ctx = workspace ?? company;

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState />
      </div>
    );
  }

  if ((portal !== "workspace" && portal !== "company") || !ctx) {
    return <Navigate to="/workspace/login" replace />;
  }

  return <Outlet />;
}
