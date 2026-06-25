import { Navigate, Route, Routes } from "react-router-dom";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { ProtectedRoute } from "@/components/admin/ProtectedRoute";
import { CompanyLayout } from "@/components/company/CompanyLayout";
import { CompanyProtectedRoute } from "@/components/company/CompanyProtectedRoute";
import { DashboardPage } from "@/pages/admin/DashboardPage";
import { CompaniesPage } from "@/pages/admin/CompaniesPage";
import { CompanyDetailPage } from "@/pages/admin/CompanyDetailPage";
import { CreateCompanyPage } from "@/pages/admin/CreateCompanyPage";
import { PlansPage } from "@/pages/admin/PlansPage";
import { AuditLogPage } from "@/pages/admin/AuditLogPage";
import { SystemHealthPage } from "@/pages/admin/SystemHealthPage";
import { IntegrationsPage } from "@/pages/admin/IntegrationsPage";
import { IntegrationConnectPage } from "@/pages/admin/IntegrationConnectPage";
import { PlatformServicesPage } from "@/pages/admin/PlatformServicesPage";
import { PlatformSettingsPage } from "@/pages/admin/PlatformSettingsPage";
import { AdminLoginPage } from "@/pages/admin/AdminLoginPage";
import { CompanyLoginPage } from "@/pages/company/CompanyLoginPage";
import { CompanyHomePage } from "@/pages/company/CompanyHomePage";
import { CompanyIntegrationsPage } from "@/pages/company/CompanyIntegrationsPage";
import { CompanyIntegrationConnectPage } from "@/pages/company/CompanyIntegrationConnectPage";
import { CompanyTeamPage } from "@/pages/company/CompanyTeamPage";
import { CompanyCreateMemberPage } from "@/pages/company/CompanyCreateMemberPage";
import { MemberIntegrationsPage } from "@/pages/company/MemberIntegrationsPage";
import { CompanySettingsPage } from "@/pages/company/CompanySettingsPage";
import { CompanyProfilePage } from "@/pages/company/CompanyProfilePage";
import { CompanyProjectsPage } from "@/pages/company/CompanyProjectsPage";
import { CompanyCreateProjectPage } from "@/pages/company/CompanyCreateProjectPage";
import { CompanyProjectDetailPage } from "@/pages/company/CompanyProjectDetailPage";
import { CompanyServicesPage } from "@/pages/company/CompanyServicesPage";
import { CompanyTeamsPage } from "@/pages/company/CompanyTeamsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AdminLoginPage />} />

      <Route
        path="/admin"
        element={
          <ProtectedRoute portal="admin">
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="integrations/:key" element={<IntegrationConnectPage />} />
        <Route path="platform-services" element={<PlatformServicesPage />} />
        <Route path="platform-settings" element={<PlatformSettingsPage />} />
        <Route path="companies" element={<CompaniesPage />} />
        <Route path="companies/new" element={<CreateCompanyPage />} />
        <Route path="companies/:id" element={<CompanyDetailPage />} />
        <Route path="plans" element={<PlansPage />} />
        <Route path="audit-log" element={<AuditLogPage />} />
        <Route path="system-health" element={<SystemHealthPage />} />
      </Route>

      <Route path="/c/:slug/login" element={<CompanyLoginPage />} />
      <Route path="/c/:slug" element={<CompanyProtectedRoute />}>
        <Route element={<CompanyLayout />}>
          <Route index element={<CompanyHomePage />} />
          <Route path="projects" element={<CompanyProjectsPage />} />
          <Route path="projects/new" element={<CompanyCreateProjectPage />} />
          <Route path="projects/:projectId" element={<CompanyProjectDetailPage />} />
          <Route path="integrations" element={<CompanyIntegrationsPage />} />
          <Route path="integrations/:key" element={<CompanyIntegrationConnectPage />} />
          <Route path="teams" element={<CompanyTeamsPage />} />
          <Route path="services" element={<CompanyServicesPage />} />
          <Route path="profile" element={<CompanyProfilePage />} />
          <Route path="team" element={<CompanyTeamPage />} />
          <Route path="team/new" element={<CompanyCreateMemberPage />} />
          <Route path="team/:memberId" element={<MemberIntegrationsPage />} />
          <Route path="settings" element={<CompanySettingsPage />} />
        </Route>
      </Route>

      <Route path="/" element={<Navigate to="/admin" replace />} />
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  );
}
