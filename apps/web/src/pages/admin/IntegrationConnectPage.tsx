import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, Eye, EyeOff, PlayCircle, Save, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { ConnectionStatusBadge } from "@/components/admin/ConnectionStatusBadge";
import { IntegrationIcon } from "@/components/admin/IntegrationIcon";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import { authTypeLabels, categoryLabels } from "@/types/platform";

export function IntegrationConnectPage() {
  const { key } = useParams<{ key: string }>();
  const queryClient = useQueryClient();
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState<string | null>(null);

  const { data: integration, isLoading, isError, error } = useQuery({
    queryKey: ["integration", key],
    queryFn: () => adminApi.getIntegration(key!),
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
      return adminApi.saveIntegrationConnection(key!, connectionName, config);
    },
    onSuccess: () => {
      setMessage("Connection saved successfully");
      queryClient.invalidateQueries({ queryKey: ["integration", key] });
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    },
    onError: (err: unknown) => setMessage(`Save failed: ${String(err)}`),
  });

  const testMutation = useMutation({
    mutationFn: () => adminApi.testIntegration(key!),
    onSuccess: (res) => setMessage(res.success ? res.message : `Test failed: ${res.message}`),
    onError: (err: unknown) => setMessage(`Test failed: ${String(err)}`),
  });

  const deleteMutation = useMutation({
    mutationFn: () => adminApi.deleteIntegrationConnection(key!),
    onSuccess: () => {
      setMessage("Connection removed");
      queryClient.invalidateQueries({ queryKey: ["integration", key] });
    },
  });

  if (isLoading) return <LoadingState />;
  if (isError || !integration) return <ErrorState message={String(error ?? "Not found")} />;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to="/admin/integrations" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />
        Integrations catalog
      </Link>

      <div className="flex items-start gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-muted">
          <IntegrationIcon integrationKey={integration.integrationKey} className="h-7 w-7" />
        </div>
        <div className="flex-1">
          <PageHeader title={integration.name} description={integration.description} actions={<ConnectionStatusBadge status={integration.connectionStatus} />} />
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
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{integration.lastErrorMessage}</div>
      )}

      {message && <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}

      {(integration.integrationKey === "github" || integration.integrationKey === "jira") && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-100">
          <p className="font-medium">OAuth callback URL</p>
          <p className="mt-2">
            Register this redirect URI in your {integration.integrationKey === "github" ? "GitHub OAuth App" : "Atlassian developer app"}:
          </p>
          <code className="mt-2 block rounded bg-white/60 px-2 py-1 dark:bg-black/30">
            {import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/oauth/{integration.integrationKey}/callback
          </code>
        </div>
      )}

      <form
        className="space-y-6 rounded-lg border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault();
          saveMutation.mutate(new FormData(e.currentTarget));
        }}
      >
        <div>
          <label htmlFor="connection_name" className="block text-sm font-medium">Connection name</label>
          <input id="connection_name" name="connection_name" type="text" defaultValue={integration.connectionName ?? "Default"} className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm" />
        </div>

        {integration.configSchema.fields.map((field) => (
          <div key={field.key}>
            <label htmlFor={field.key} className="block text-sm font-medium">
              {field.label}{field.required && <span className="text-destructive"> *</span>}
            </label>
            <div className="relative mt-1.5">
              <input
                id={field.key}
                name={field.key}
                type={field.type === "secret" && !showSecrets[field.key] ? "password" : field.type === "number" ? "number" : "text"}
                placeholder={field.type === "secret" ? "••••••••••••" : field.default?.toString()}
                defaultValue={
                  field.type !== "secret"
                    ? (integration.configMetadata[field.key]?.toString() ?? field.default?.toString())
                    : undefined
                }
                className="h-10 w-full rounded-md border bg-background px-3 pr-10 text-sm"
              />
              {field.type === "secret" && (
                <button type="button" onClick={() => setShowSecrets((p) => ({ ...p, [field.key]: !p[field.key] }))} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground">
                  {showSecrets[field.key] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              )}
            </div>
          </div>
        ))}

        <div className="flex flex-wrap gap-3 border-t pt-4">
          <button type="submit" disabled={saveMutation.isPending} className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
            <Save className="h-4 w-4" />
            {saveMutation.isPending ? "Saving..." : "Save connection"}
          </button>
          <button type="button" onClick={() => testMutation.mutate()} disabled={testMutation.isPending} className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent">
            <PlayCircle className="h-4 w-4" />
            Test connection
          </button>
          {integration.connectionStatus === "connected" && (
            <button type="button" onClick={() => deleteMutation.mutate()} className="inline-flex items-center gap-2 rounded-md border border-destructive/30 px-4 py-2 text-sm font-medium text-destructive">
              <Trash2 className="h-4 w-4" />
              Remove
            </button>
          )}
          {integration.documentationUrl && (
            <a href={integration.documentationUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent">
              <ExternalLink className="h-4 w-4" />
              Setup guide
            </a>
          )}
        </div>
      </form>
    </div>
  );
}
