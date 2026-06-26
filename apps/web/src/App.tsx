import { Navigate, Route, Routes } from "react-router-dom";

import { AdminLayout } from "@/components/admin/AdminLayout";

import { ProtectedRoute } from "@/components/admin/ProtectedRoute";

import { CompanyLayout } from "@/components/company/CompanyLayout";

import { CompanyProtectedRoute } from "@/components/company/CompanyProtectedRoute";

import { DashboardPage } from "@/pages/admin/DashboardPage";

import { TeamsPage } from "@/pages/admin/TeamsPage";

import { TeamDetailPage } from "@/pages/admin/TeamDetailPage";

import { CreateTeamPage } from "@/pages/admin/CreateTeamPage";

import { AdminUsagePage } from "@/pages/admin/AdminUsagePage";

import { AuditLogPage } from "@/pages/admin/AuditLogPage";

import { SystemHealthPage } from "@/pages/admin/SystemHealthPage";

import { IntegrationsPage } from "@/pages/admin/IntegrationsPage";

import { IntegrationConnectPage } from "@/pages/admin/IntegrationConnectPage";

import { PlatformServicesPage } from "@/pages/admin/PlatformServicesPage";

import { PlatformAgentsPage } from "@/pages/admin/PlatformAgentsPage";

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

import { CompanyMyAgentsPage } from "@/pages/company/CompanyMyAgentsPage";

import { CompanyAgentsPage } from "@/pages/company/CompanyAgentsPage";

import { MemberAgentsPage } from "@/pages/company/MemberAgentsPage";



export default function App() {

  return (

    <Routes>

      <Route path="/login" element={<AdminLoginPage />} />

      <Route path="/workspace/login" element={<CompanyLoginPage />} />



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

        <Route path="agents" element={<PlatformAgentsPage />} />

        <Route path="platform-settings" element={<PlatformSettingsPage />} />

        <Route path="teams" element={<TeamsPage />} />

        <Route path="teams/new" element={<CreateTeamPage />} />

        <Route path="teams/:teamId" element={<TeamDetailPage />} />

        <Route path="workspace" element={<Navigate to="/admin/teams" replace />} />

        <Route path="team" element={<Navigate to="/admin/teams" replace />} />

        <Route path="companies" element={<Navigate to="/admin/teams" replace />} />

        <Route path="companies/*" element={<Navigate to="/admin/teams" replace />} />

        <Route path="usage" element={<AdminUsagePage />} />

        <Route path="audit-log" element={<AuditLogPage />} />

        <Route path="system-health" element={<SystemHealthPage />} />

      </Route>



      <Route path="/workspace" element={<CompanyProtectedRoute />}>

        <Route element={<CompanyLayout />}>

          <Route index element={<CompanyHomePage />} />

          <Route path="projects" element={<CompanyProjectsPage />} />

          <Route path="projects/new" element={<CompanyCreateProjectPage />} />

          <Route path="projects/:projectId" element={<CompanyProjectDetailPage />} />

          <Route path="integrations" element={<CompanyIntegrationsPage />} />

          <Route path="integrations/:key" element={<CompanyIntegrationConnectPage />} />

          <Route path="services" element={<CompanyServicesPage />} />

          <Route path="agents" element={<CompanyAgentsPage />} />

          <Route path="my-agents" element={<CompanyMyAgentsPage />} />

          <Route path="profile" element={<CompanyProfilePage />} />

          <Route path="team" element={<CompanyTeamPage />} />

          <Route path="team/new" element={<CompanyCreateMemberPage />} />

          <Route path="team/:memberId" element={<MemberIntegrationsPage />} />

          <Route path="team/:memberId/agents" element={<MemberAgentsPage />} />

          <Route path="settings" element={<CompanySettingsPage />} />

        </Route>

      </Route>



      <Route path="/c/:slug/login" element={<CompanyLoginPage />} />

      <Route path="/c/:slug/*" element={<Navigate to="/workspace" replace />} />



      <Route path="/" element={<Navigate to="/workspace/login" replace />} />

      <Route path="*" element={<Navigate to="/workspace/login" replace />} />

    </Routes>

  );

}

