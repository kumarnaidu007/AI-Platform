import { Link, Navigate, useParams } from "react-router-dom";

import { isTeamLead } from "@/types/roles";

import { useQuery } from "@tanstack/react-query";

import { Bot, Plug, Plus, UserPlus } from "lucide-react";

import { PageHeader } from "@/components/admin/PageHeader";

import { LoadingState, ErrorState } from "@/components/admin/LoadingState";

import { companyApi } from "@/services/companyApi";

import { useAuth } from "@/context/AuthContext";



export function CompanyTeamPage() {

  useParams<{ slug: string }>();

  const { company } = useAuth();



  if (!isTeamLead(company?.role)) {

    return <Navigate to={`/workspace`} replace />;

  }



  const { data, isLoading, isError, error } = useQuery({

    queryKey: ["company-members"],

    queryFn: companyApi.getMembers,

  });



  if (isLoading) return <LoadingState />;

  if (isError) return <ErrorState message={String(error)} />;



  return (

    <div className="space-y-6">

      <PageHeader

        title="Team"

        description="Add employees and assign which integrations and AI agents each person can use."

        actions={

          <Link

            to={`/workspace/team/new`}

            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"

          >

            <UserPlus className="h-4 w-4" />

            Add employee

          </Link>

        }

      />



      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">

        <p className="font-medium">How assignment works</p>

        <ol className="mt-2 list-inside list-decimal space-y-1 text-xs">

          <li>Platform admin grants GitHub, Jira, and agents to your team (per team)</li>

          <li>You assign integrations & agents to each team member below</li>

          <li>Members connect their own GitHub/Jira under My Integrations</li>

        </ol>

      </div>



      {(data ?? []).length === 0 ? (

        <div className="rounded-lg border border-dashed p-10 text-center">

          <p className="text-sm text-muted-foreground">No team members yet.</p>

          <Link

            to={`/workspace/team/new`}

            className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-primary"

          >

            <Plus className="h-4 w-4" />

            Create first employee

          </Link>

        </div>

      ) : (

        <div className="overflow-hidden rounded-lg border">

          <table className="w-full text-sm">

            <thead className="border-b bg-muted/40">

              <tr>

                <th className="px-4 py-3 text-left font-medium">Name</th>

                <th className="px-4 py-3 text-left font-medium">Email</th>

                <th className="px-4 py-3 text-left font-medium">Role</th>

                <th className="px-4 py-3 text-left font-medium">Integrations</th>

                <th className="px-4 py-3 text-left font-medium">Agents</th>

                <th className="px-4 py-3 text-left font-medium">Status</th>

                <th className="px-4 py-3 text-right font-medium">Actions</th>

              </tr>

            </thead>

            <tbody>

              {(data ?? []).map((member) => (

                <tr key={member.id} className="border-b last:border-0 hover:bg-muted/20">

                  <td className="px-4 py-3 font-medium">{member.fullName}</td>

                  <td className="px-4 py-3 text-muted-foreground">{member.email}</td>

                  <td className="px-4 py-3 capitalize">{member.role.replace(/_/g, " ")}</td>

                  <td className="px-4 py-3">{member.integrationsAssigned}</td>

                  <td className="px-4 py-3">{member.agentsAssigned}</td>

                  <td className="px-4 py-3">

                    <span

                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${

                        member.isActive ? "bg-emerald-100 text-emerald-800" : "bg-muted text-muted-foreground"

                      }`}

                    >

                      {member.isActive ? "Active" : "Inactive"}

                    </span>

                  </td>

                  <td className="px-4 py-3">

                    <div className="flex justify-end gap-2">

                      <Link

                        to={`/workspace/team/${member.id}`}

                        className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-accent"

                      >

                        <Plug className="h-3.5 w-3.5" />

                        Integrations

                      </Link>

                      <Link

                        to={`/workspace/team/${member.id}/agents`}

                        className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-accent"

                      >

                        <Bot className="h-3.5 w-3.5" />

                        Agents

                      </Link>

                    </div>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

      )}

    </div>

  );

}

