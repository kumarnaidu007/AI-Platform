import { Navigate, Outlet, useParams } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { LoadingState } from "@/components/admin/LoadingState";

export function CompanyProtectedRoute() {
  const { slug } = useParams<{ slug: string }>();
  const { portal, company, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState />
      </div>
    );
  }

  if (portal !== "company" || !company || company.slug !== slug) {
    return <Navigate to={`/c/${slug}/login`} replace />;
  }

  return <Outlet />;
}
