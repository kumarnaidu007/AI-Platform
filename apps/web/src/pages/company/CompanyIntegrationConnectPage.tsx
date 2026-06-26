import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Eye, EyeOff, PlayCircle, Plug, Save, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { ConnectionStatusBadge } from "@/components/admin/ConnectionStatusBadge";
import { IntegrationIcon } from "@/components/admin/IntegrationIcon";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { githubApi } from "@/services/githubApi";
import { jiraApi } from "@/services/jiraApi";
import { authTypeLabels, categoryLabels } from "@/types/platform";

export function CompanyIntegrationConnectPage() {
  const { key } = useParams<{ key: string }>();
  const queryClient = useQueryClient();
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    if (searchParams.get("github_connected") === "1") {
      setMessage("GitHub connected successfully.");
      searchParams.delete("github_connected");
      setSearchParams(searchParams, { replace: true });
      queryClient.invalidateQueries({ queryKey: ["company-my-integration", key] });
      queryClient.invalidateQueries({ queryKey: ["github-status"] });
    }
    if (searchParams.get("jira_connected") === "1") {
      setMessage("Jira connected successfully.");
      searchParams.delete("jira_connected");
      setSearchParams(searchParams, { replace: true });
      queryClient.invalidateQueries({ queryKey: ["company-my-integration", key] });
      queryClient.invalidateQueries({ queryKey: ["jira-status"] });
    }
    const githubErr = searchParams.get("github_error");
    if (githubErr) {
      setMessage(`GitHub connection failed: ${githubErr}`);
      searchParams.delete("github_error");
      setSearchParams(searchParams, { replace: true });
    }
    const jiraErr = searchParams.get("jira_error");
    if (jiraErr) {
      setMessage(`Jira connection failed: ${jiraErr}`);
      searchParams.delete("jira_error");
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

  const githubOAuthMutation = useMutation({
    mutationFn: () =>
      githubApi.startOAuth(`${window.location.origin}/workspace/integrations/${key}`),
    onSuccess: ({ authorizeUrl }) => {
      window.location.href = authorizeUrl;
    },
    onError: (err) => setMessage(String(err)),
  });

  const jiraOAuthMutation = useMutation({
    mutationFn: () =>
      jiraApi.startOAuth(`${window.location.origin}/workspace/integrations/${key}`),
    onSuccess: ({ authorizeUrl }) => {
      window.location.href = authorizeUrl;
    },
    onError: (err) => setMessage(String(err)),
  });

  const githubDisconnectMutation = useMutation({
    mutationFn: githubApi.disconnect,
    onSuccess: () => {
      setMessage("GitHub disconnected");
      queryClient.invalidateQueries({ queryKey: ["company-my-integration", key] });
      queryClient.invalidateQueries({ queryKey: ["company-my-integrations"] });
      queryClient.invalidateQueries({ queryKey: ["github-status"] });
    },
  });

  const jiraDisconnectMutation = useMutation({
    mutationFn: jiraApi.disconnect,
    onSuccess: () => {
      setMessage("Jira disconnected");
      queryClient.invalidateQueries({ queryKey: ["company-my-integration", key] });
      queryClient.invalidateQueries({ queryKey: ["company-my-integrations"] });
      queryClient.invalidateQueries({ queryKey: ["jira-status"] });
    },
  });

  const isGitHubOAuth = key === "github" && integration?.authType === "oauth2";
  const isJiraOAuth = key === "jira" && integration?.authType === "oauth2";

  if (isLoading) return <LoadingState />;
  if (isError || !integration) return <ErrorState message={String(error ?? "Integration not assigned to you")} />;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to="/workspace/integrations"
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

      {isGitHubOAuth ? (
        <div className="space-y-6 rounded-lg border bg-card p-6">
          <div>
            <h3 className="text-sm font-semibold">GitHub sign-in</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Connect your GitHub account so agents can create branches, commit code, and open pull requests.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 border-t pt-4">
            {integration.connectionStatus !== "connected" ? (
              <button
                type="button"
                disabled={githubOAuthMutation.isPending}
                onClick={() => githubOAuthMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              >
                <Plug className="h-4 w-4" />
                {githubOAuthMutation.isPending ? "Redirecting…" : "Connect with GitHub"}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => githubDisconnectMutation.mutate()}
                  disabled={githubDisconnectMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-md border border-destructive/30 px-4 py-2 text-sm font-medium text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                  Disconnect GitHub
                </button>
                <button
                  type="button"
                  onClick={() => testMutation.mutate()}
                  disabled={testMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium"
                >
                  <PlayCircle className="h-4 w-4" />
                  Test connection
                </button>
              </>
            )}
          </div>
        </div>
      ) : isJiraOAuth ? (
        <div className="space-y-6 rounded-lg border bg-card p-6">
          <div>
            <h3 className="text-sm font-semibold">Jira sign-in</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Connect your Atlassian account so agents can read and create Jira issues for your projects.
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              Admin callback URL:{" "}
              <code className="rounded bg-muted px-1">
                {import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/oauth/jira/callback
              </code>
            </p>
          </div>
          <div className="flex flex-wrap gap-3 border-t pt-4">
            {integration.connectionStatus !== "connected" ? (
              <button
                type="button"
                disabled={jiraOAuthMutation.isPending}
                onClick={() => jiraOAuthMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              >
                <Plug className="h-4 w-4" />
                {jiraOAuthMutation.isPending ? "Redirecting…" : "Connect with Jira"}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => jiraDisconnectMutation.mutate()}
                  disabled={jiraDisconnectMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-md border border-destructive/30 px-4 py-2 text-sm font-medium text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                  Disconnect Jira
                </button>
                <button
                  type="button"
                  onClick={() => testMutation.mutate()}
                  disabled={testMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium"
                >
                  <PlayCircle className="h-4 w-4" />
                  Test connection
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
