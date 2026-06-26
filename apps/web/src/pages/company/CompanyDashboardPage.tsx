import { Link, useParams } from "react-router-dom";
import { isTeamLead } from "@/types/roles";
import { useQuery } from "@tanstack/react-query";
import { FolderKanban, Plug, Sparkles, Users } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { StatCard } from "@/components/admin/StatCard";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";

export function CompanyDashboardPage() {
  useParams<{ slug: string }>();
  const { company } = useAuth();
  const isAdmin = isTeamLead(company?.role);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["company-dashboard"],
    queryFn: companyApi.getDashboard,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const needsDomain = isAdmin && !data?.emailDomain;

  return (
    <div className="space-y-8">
      <PageHeader
        title={`Welcome, ${company?.name}`}
        description={`${company?.planName} plan · Signed in as ${company?.role}${
          data?.emailDomain ? ` · @${data.emailDomain}` : ""
        }`}
      />

      {needsDomain && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          Complete setup: configure your company email domain in{" "}
          <Link to={`/workspace/settings`} className="font-medium text-primary hover:underline">
            Settings
          </Link>{" "}
          before adding employees. Only @{`yourcompany.com`} addresses will be allowed to sign in.
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Projects" value={data?.projectsCount ?? 0} icon={FolderKanban} />
        <StatCard label="Integrations granted" value={data?.integrationsEnabled ?? 0} icon={Plug} />
        <StatCard label="AI services granted" value={data?.servicesEnabled ?? 0} icon={Sparkles} />
        {isAdmin && <StatCard label="Team members" value={data?.teamCount ?? 0} icon={Users} />}
      </div>
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-base font-semibold">Getting started</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Company admins assign integrations to employees. Each employee connects with their own work account
          credentials.
        </p>
        <ul className="mt-4 space-y-2 text-sm">
          {isAdmin && (
            <>
              <li>
                <Link to={`/workspace/settings`} className="text-primary hover:underline">
                  Set company email domain
                </Link>{" "}
                — only @{data?.emailDomain || "yourcompany.com"} accounts can join
              </li>
              <li>
                <Link to={`/workspace/team`} className="text-primary hover:underline">
                  Add team members
                </Link>{" "}
                — create employee logins and assign integrations
              </li>
            </>
          )}
          <li>
            <Link to={`/workspace/integrations`} className="text-primary hover:underline">
              Connect your integrations
            </Link>{" "}
            — use your personal credentials for assigned tools
          </li>
        </ul>
      </div>
    </div>
  );
}
