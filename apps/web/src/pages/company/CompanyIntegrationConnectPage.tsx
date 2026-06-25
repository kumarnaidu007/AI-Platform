import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Eye, EyeOff, PlayCircle, Plug, Save, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { ConnectionStatusBadge } from "@/components/admin/ConnectionStatusBadge";
import { IntegrationIcon } from "@/components/admin/IntegrationIcon";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { teamsApi } from "@/services/teamsApi";
import { useAuth } from "@/context/AuthContext";
import { authTypeLabels, categoryLabels } from "@/types/platform";

export function CompanyIntegrationConnectPage() {
  const { slug, key } = useParams<{ slug: string; key: string }>();
  const { company } = useAuth();
  const queryClient = useQueryClient();
  const isViewer = company?.role === "viewer";
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    if (searchParams.get("teams_connected") === "1") {
      setMessage("Microsoft Teams connected successfully.");
      searchParams.delete("teams_connected");
      setSearchParams(searchParams, { replace: true });
      queryClient.invalidateQueries({ queryKey: ["company-my-integration", key] });
      queryClient.invalidateQueries({ queryKey: ["teams-status"] });
    }
    const err = searchParams.get("teams_error");
    if (err) {
      setMessage(`Teams connection failed: ${err}`);
      searchParams.delete("teams_error");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, queryClient, key]);

  const { data: integration, isLoading, isError, error } = useQuery({
    queryKey: ["company-my-integration", key],
    queryFn: () => companyApi.getMyIntegration(key!),
    enabled: !!key,
  });

  const saveMutation = useMutation({
    mutationFn: (form: FormData) => {
      const connectionName = String(form.get("connection_name") || "Default");
      const config: Record<string, string> = {};
      integration?.configSchema.fields.forEach((f) => {
        const v = form.get(f.key);
        if (v) config[f.key] = String(v);
      });
      return companyApi.saveMyIntegrationConnection(key!, connectionName, config);
    },
    onSuccess: () => {
      setMessage("Your credentials were saved successfully");
      queryClient.invalidateQueries({ queryKey: ["company-my-integration", key] });
      queryClient.invalidateQueries({ queryKey: ["company-my-integrations"] });
    },
  });

  const testMutation = useMutation({
    mutationFn: () => companyApi.testMyIntegration(key!),
    onSuccess: (res) => {
      setMessage(res.message);
      queryClient.invalidateQueries({ queryKey: ["company-my-integration", key] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => companyApi.deleteMyIntegrationConnection(key!),
    onSuccess: () => {
      setMessage("Connection removed");
      queryClient.invalidateQueries({ queryKey: ["company-my-integration", key] });
      queryClient.invalidateQueries({ queryKey: ["company-my-integrations"] });
    },
  });

  const teamsOAuthMutation = useMutation({
    mutationFn: () =>
      teamsApi.startOAuth(`${window.location.origin}/c/${slug}/integrations/${key}`),
    onSuccess: ({ authorizeUrl }) => {
      window.location.href = authorizeUrl;
    },
    onError: (err) => setMessage(String(err)),
  });

  const teamsDisconnectMutation = useMutation({
    mutationFn: teamsApi.disconnect,
    onSuccess: () => {
      setMessage("Microsoft Teams disconnected");
      queryClient.invalidateQueries({ queryKey: ["company-my-integration", key] });
      queryClient.invalidateQueries({ queryKey: ["company-my-integrations"] });
      queryClient.invalidateQueries({ queryKey: ["teams-status"] });
    },
  });

  const isTeamsOAuth = key === "teams" && integration?.authType === "oauth2";

  if (isLoading) return <LoadingState />;
  if (isError || !integration) return <ErrorState message={String(error ?? "Integration not assigned to you")} />;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to={`/c/${slug}/integrations`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        My integrations
      </Link>

      <div className="flex items-start gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-muted">
          <IntegrationIcon integrationKey={integration.integrationKey} className="h-7 w-7" />
        </div>
        <div className="flex-1">
          <PageHeader
            title={integration.name}
            description={`Connect with your personal work account. ${integration.description}`}
            actions={<ConnectionStatusBadge status={integration.connectionStatus} />}
          />
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span className="rounded bg-muted px-2 py-0.5">{categoryLabels[integration.category]}</span>
            <span className="rounded bg-muted px-2 py-0.5">{authTypeLabels[integration.authType]}</span>
          </div>
        </div>
      </div>

      {integration.configMetadata && Object.keys(integration.configMetadata).length > 0 && (
        <div className="rounded-lg border bg-card p-5">
          <h3 className="text-sm font-semibold">Current connection (metadata only)</h3>
          <dl className="mt-4 space-y-2">
            {Object.entries(integration.configMetadata).map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm">
                <dt className="font-mono text-muted-foreground">{k}</dt>
                <dd className="font-mono">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {integration.lastErrorMessage && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {integration.lastErrorMessage}
        </div>
      )}

      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>
      )}

      {isViewer ? (
        <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">
          Viewer accounts have read-only access. You cannot connect or modify integration credentials.
        </div>
      ) : isTeamsOAuth ? (
        <div className="space-y-6 rounded-lg border bg-card p-6">
          <div>
            <h3 className="text-sm font-semibold">Microsoft sign-in</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Connect with your own Microsoft account (personal or work). OAuth tokens are stored
              per user — the platform never sees your Microsoft password.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 border-t pt-4">
            {integration.connectionStatus !== "connected" ? (
              <button
                type="button"
                disabled={teamsOAuthMutation.isPending}
                onClick={() => teamsOAuthMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              >
                <Plug className="h-4 w-4" />
                {teamsOAuthMutation.isPending ? "Redirecting…" : "Connect with Microsoft"}
              </button>
            ) : (
              <>
                <Link
                  to={`/c/${slug}/teams`}
                  className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
                >
                  Open Teams chats
                </Link>
                <button
                  type="button"
                  onClick={() => teamsDisconnectMutation.mutate()}
                  disabled={teamsDisconnectMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-md border border-destructive/30 px-4 py-2 text-sm font-medium text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                  Disconnect
                </button>
              </>
            )}
          </div>
        </div>
      ) : (
      <form
        className="space-y-6 rounded-lg border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault();
          saveMutation.mutate(new FormData(e.currentTarget));
        }}
      >
        <div>
          <label htmlFor="connection_name" className="block text-sm font-medium">
            Connection name
          </label>
          <input
            id="connection_name"
            name="connection_name"
            type="text"
            defaultValue={integration.connectionName ?? "Default"}
            className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm"
          />
        </div>

        {integration.configSchema.fields.map((field) => (
          <div key={field.key}>
            <label htmlFor={field.key} className="block text-sm font-medium">
              {field.label}
              {field.required && <span className="text-destructive"> *</span>}
            </label>
            <div className="relative mt-1.5">
              <input
                id={field.key}
                name={field.key}
                type={
                  field.type === "secret" && !showSecrets[field.key]
                    ? "password"
                    : field.type === "number"
                      ? "number"
                      : "text"
                }
                placeholder={field.type === "secret" ? "••••••••••••" : field.default?.toString()}
                defaultValue={field.type !== "secret" ? field.default?.toString() : undefined}
                className="h-10 w-full rounded-md border bg-background px-3 pr-10 text-sm"
              />
              {field.type === "secret" && (
                <button
                  type="button"
                  onClick={() => setShowSecrets((p) => ({ ...p, [field.key]: !p[field.key] }))}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                >
                  {showSecrets[field.key] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              )}
            </div>
          </div>
        ))}

        <div className="flex flex-wrap gap-3 border-t pt-4">
          <button
            type="submit"
            disabled={saveMutation.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            <Save className="h-4 w-4" />
            {saveMutation.isPending ? "Saving..." : "Save my credentials"}
          </button>
          <button
            type="button"
            onClick={() => testMutation.mutate()}
            disabled={testMutation.isPending}
            className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent"
          >
            <PlayCircle className="h-4 w-4" />
            Test connection
          </button>
          {integration.connectionStatus === "connected" && (
            <button
              type="button"
              onClick={() => deleteMutation.mutate()}
              className="inline-flex items-center gap-2 rounded-md border border-destructive/30 px-4 py-2 text-sm font-medium text-destructive"
            >
              <Trash2 className="h-4 w-4" />
              Remove
            </button>
          )}
        </div>
      </form>
      )}
    </div>
  );
}
