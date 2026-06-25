import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";

export function CreateCompanyPage() {
  const navigate = useNavigate();
  const { data: plans, isLoading, isError, error } = useQuery({ queryKey: ["plans"], queryFn: adminApi.getPlans });

  const createMutation = useMutation({
    mutationFn: adminApi.createCompany,
    onSuccess: (c) => navigate(`/admin/companies/${c.id}`),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Link to="/admin/companies" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />
        Back to companies
      </Link>

      <PageHeader
        title="Create Company"
        description="Onboard a new tenant. Integrations and AI services are granted from the selected plan — you can adjust access on the company detail page."
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
            status: String(fd.get("status")),
            emailDomain: String(fd.get("email_domain") || ""),
            adminName: String(fd.get("admin_name") || ""),
            adminEmail: String(fd.get("admin_email") || ""),
            adminPassword: String(fd.get("admin_password") || ""),
          });
        }}
      >
        <div>
          <label htmlFor="name" className="block text-sm font-medium">Company name</label>
          <input id="name" name="name" required className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm" />
        </div>
        <div>
          <label htmlFor="slug" className="block text-sm font-medium">URL slug</label>
          <input id="slug" name="slug" required placeholder="acme-corp" className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm" />
        </div>
        <div>
          <label htmlFor="plan_id" className="block text-sm font-medium">Plan</label>
          <select id="plan_id" name="plan_id" required className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm">
            {(plans ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} — {p.maxProjects} projects, ${p.monthlyTokenBudgetUsd}/mo, {(p.integrationKeys ?? []).length} integrations
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="status" className="block text-sm font-medium">Initial status</label>
          <select id="status" name="status" className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm">
            <option value="trial">Trial</option>
            <option value="active">Active</option>
          </select>
        </div>
        <div>
          <label htmlFor="email_domain" className="block text-sm font-medium">Company email domain (optional)</label>
          <input
            id="email_domain"
            name="email_domain"
            placeholder="acme.com"
            className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Only employees with this domain can sign in. Company admin can also set this later.
          </p>
        </div>
        <div className="rounded-md border border-dashed p-4">
          <p className="text-sm font-medium">Company admin (optional)</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Creates a company admin account. Admin email must match the company domain if provided.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="admin_name" className="block text-sm font-medium">Admin name</label>
              <input id="admin_name" name="admin_name" className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm" />
            </div>
            <div>
              <label htmlFor="admin_email" className="block text-sm font-medium">Admin email</label>
              <input id="admin_email" name="admin_email" type="email" className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm" />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="admin_password" className="block text-sm font-medium">Admin password</label>
              <input
                id="admin_password"
                name="admin_password"
                type="password"
                minLength={8}
                placeholder="Required if admin email is set"
                className="mt-1.5 h-10 w-full rounded-md border px-3 text-sm"
              />
            </div>
          </div>
        </div>
        {createMutation.isError && (
          <p className="text-sm text-red-600">
            {createMutation.error instanceof Error ? createMutation.error.message : String(createMutation.error)}
          </p>
        )}
        <div className="flex justify-end gap-3 border-t pt-4">
          <Link to="/admin/companies" className="rounded-md border px-4 py-2 text-sm font-medium">Cancel</Link>
          <button type="submit" disabled={createMutation.isPending} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
            {createMutation.isPending ? "Creating..." : "Create Company"}
          </button>
        </div>
      </form>
    </div>
  );
}
