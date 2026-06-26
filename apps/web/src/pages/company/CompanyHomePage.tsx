import { useAuth } from "@/context/AuthContext";
import { isTeamLead } from "@/types/roles";
import { CompanyDashboardPage } from "@/pages/company/CompanyDashboardPage";
import { UserDashboardPage } from "@/pages/company/UserDashboardPage";

export function CompanyHomePage() {
  const { company } = useAuth();
  if (isTeamLead(company?.role)) {
    return <CompanyDashboardPage />;
  }
  return <UserDashboardPage />;
}
