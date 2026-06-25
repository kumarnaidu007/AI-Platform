import { useAuth } from "@/context/AuthContext";
import { CompanyDashboardPage } from "@/pages/company/CompanyDashboardPage";
import { UserDashboardPage } from "@/pages/company/UserDashboardPage";

export function CompanyHomePage() {
  const { company } = useAuth();
  if (company?.role === "admin") {
    return <CompanyDashboardPage />;
  }
  return <UserDashboardPage />;
}
