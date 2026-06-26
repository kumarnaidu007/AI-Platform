import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { isTeamLead } from "@/types/roles";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";

export function CompanySettingsPage() {
  const { company } = useAuth();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isTeamLead(company?.role)) {
    return <Navigate to="/workspace" replace />;
  }

  const { data, isLoading, isError, error: loadError } = useQuery({
    queryKey: ["company-settings"],
    queryFn: companyApi.getSettings,
  });

  const saveMutation = useMutation({
    mutationFn: (domain: string) => companyApi.updateSettings(domain),
    onSuccess: () => {
      setMessage("Company email domain saved");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["company-settings"] });
      queryClient.invalidateQueries({ queryKey: ["company-dashboard"] });
    },
    onError: (err: unknown) => {
      const msg =
        err && typeof err === "object" && "response" in err
          ? String((err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Failed to save")
          : "Failed to save";
      setError(msg);
    },
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(loadError)} />;

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <PageHeader
        title="Company settings"
        description="Set the email domain for your organization. Only employees with this domain can be added and sign in."
      />

      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>
      )}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>
      )}

      <form
        className="space-y-5 rounded-lg border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault();
          const domain = String(new FormData(e.currentTarget).get("email_domain") ?? "");
          saveMutation.mutate(domain);
        }}
      >
        <div>
          <label htmlFor="email_domain" className="block text-sm font-medium">
            Company email domain
          </label>
          <div className="mt-1.5 flex">
            <span className="inline-flex items-center rounded-l-md border border-r-0 bg-muted px-3 text-sm text-muted-foreground">
              @
            </span>
            <input
              id="email_domain"
              name="email_domain"
              type="text"
              required
              placeholder="acme.com"
              defaultValue={data?.emailDomain ?? ""}
              className="h-10 w-full rounded-r-md border bg-background px-3 text-sm"
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Employees must use emails like <span className="font-mono">name@{data?.emailDomain || "yourcompany.com"}</span> to
            sign in and connect integrations.
          </p>
        </div>
        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          {saveMutation.isPending ? "Saving..." : "Save domain"}
        </button>
      </form>
    </div>
  );
}
