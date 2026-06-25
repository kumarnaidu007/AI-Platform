import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";

export function CompanyCreateMemberPage() {
  const { slug } = useParams<{ slug: string }>();
  const { company } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["company-settings"],
    queryFn: companyApi.getSettings,
    enabled: company?.role === "admin",
  });

  const createMutation = useMutation({
    mutationFn: (form: FormData) =>
      companyApi.createMember({
        email: String(form.get("email")),
        fullName: String(form.get("full_name")),
        password: String(form.get("password")),
        role: String(form.get("role") || "member"),
      }),
    onSuccess: (member) => {
      navigate(`/c/${slug}/team/${member.id}`);
    },
    onError: (err: unknown) => {
      const msg =
        err && typeof err === "object" && "response" in err
          ? String(
              (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
                "Failed to create employee"
            )
          : "Failed to create employee";
      setError(msg);
    },
  });

  if (company?.role !== "admin") {
    return <Navigate to={`/c/${slug}`} replace />;
  }

  if (settingsQuery.isLoading) return <LoadingState />;

  const emailDomain = settingsQuery.data?.emailDomain;

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <Link
        to={`/c/${slug}/team`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to team
      </Link>

      <PageHeader
        title="Add employee"
        description={
          emailDomain
            ? `Only @${emailDomain} work emails can be added and sign in.`
            : "Configure your company email domain in Settings before adding employees."
        }
      />

      {!emailDomain && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          Set your company email domain first under{" "}
          <Link to={`/c/${slug}/settings`} className="font-medium text-primary hover:underline">
            Settings
          </Link>
          .
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>
      )}

      <form
        className="space-y-5 rounded-lg border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          createMutation.mutate(new FormData(e.currentTarget));
        }}
      >
        <div>
          <label htmlFor="full_name" className="block text-sm font-medium">
            Full name
          </label>
          <input
            id="full_name"
            name="full_name"
            type="text"
            required
            disabled={!emailDomain}
            className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm disabled:opacity-50"
          />
        </div>
        <div>
          <label htmlFor="email" className="block text-sm font-medium">
            Work email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            disabled={!emailDomain}
            placeholder={emailDomain ? `name@${emailDomain}` : "name@yourcompany.com"}
            className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm disabled:opacity-50"
          />
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium">
            Temporary password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            minLength={8}
            disabled={!emailDomain}
            className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm disabled:opacity-50"
          />
          <p className="mt-1 text-xs text-muted-foreground">Share this with the employee for their first login.</p>
        </div>
        <div>
          <label htmlFor="role" className="block text-sm font-medium">
            Role
          </label>
          <select
            id="role"
            name="role"
            defaultValue="member"
            disabled={!emailDomain}
            className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm disabled:opacity-50"
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
        <div className="flex gap-3 border-t pt-4">
          <button
            type="submit"
            disabled={!emailDomain || createMutation.isPending}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {createMutation.isPending ? "Creating..." : "Create employee"}
          </button>
          <Link
            to={`/c/${slug}/team`}
            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
