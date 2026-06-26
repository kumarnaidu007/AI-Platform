import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";

export function CreateTeamPage() {
  const navigate = useNavigate();
  const { data: plans, isLoading, isError, error } = useQuery({ queryKey: ["plans"], queryFn: adminApi.getPlans });

  const createMutation = useMutation({
    mutationFn: adminApi.createCompany,
    onSuccess: (team) => navigate(`/admin/teams/${team.id}`),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Link to="/admin/teams" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />
        Back to teams
      </Link>

      <PageHeader
        title="Create team"
        description="Onboard a new team workspace. After creation, grant integrations and agents on the team detail page."
      />

      <form
        className="space-y-6 rounded-lg border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          createMutation.mutate({
            name: String(fd.get("name")),
            slug: String(fd.get("slug")),
            planId: String(fd.get("plan_id")),
            status: String(fd.get("status") || "active"),
            emailDomain: String(fd.get("email_domain") || "") || undefined,
            adminName: String(fd.get("admin_name") || "") || undefined,
            adminEmail: String(fd.get("admin_email") || "") || undefined,
            adminPassword: String(fd.get("admin_password") || "") || undefined,
          });
        }}
      >
        <div>
          <label htmlFor="name" className="block text-sm font-medium">
            Team name
          </label>
          <input id="name" name="name" required className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm" />
        </div>
        <div>
          <label htmlFor="slug" className="block text-sm font-medium">
            Slug
          </label>
          <input
            id="slug"
            name="slug"
            required
            pattern="[a-z0-9-]+"
            placeholder="acme-engineering"
            className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm"
          />
        </div>
        <div>
          <label htmlFor="plan_id" className="block text-sm font-medium">
            Plan
          </label>
          <select id="plan_id" name="plan_id" required className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm">
            {(plans ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="status" className="block text-sm font-medium">
            Status
          </label>
          <select id="status" name="status" defaultValue="active" className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm">
            <option value="active">Active</option>
            <option value="trial">Trial</option>
          </select>
        </div>
        <div>
          <label htmlFor="email_domain" className="block text-sm font-medium">
            Email domain (optional)
          </label>
          <input
            id="email_domain"
            name="email_domain"
            placeholder="acme.com"
            className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm"
          />
        </div>
        <fieldset className="space-y-4 rounded-md border p-4">
          <legend className="px-1 text-sm font-medium">Team lead (optional)</legend>
          <div>
            <label htmlFor="admin_name" className="block text-sm font-medium">
              Full name
            </label>
            <input id="admin_name" name="admin_name" className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm" />
          </div>
          <div>
            <label htmlFor="admin_email" className="block text-sm font-medium">
              Email
            </label>
            <input id="admin_email" name="admin_email" type="email" className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm" />
          </div>
          <div>
            <label htmlFor="admin_password" className="block text-sm font-medium">
              Password
            </label>
            <input
              id="admin_password"
              name="admin_password"
              type="password"
              className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm"
            />
          </div>
        </fieldset>
        {createMutation.isError && (
          <p className="text-sm text-red-600">{String(createMutation.error)}</p>
        )}
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="h-10 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {createMutation.isPending ? "Creating..." : "Create team"}
        </button>
      </form>
    </div>
  );
}
