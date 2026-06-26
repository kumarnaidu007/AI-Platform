import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Box, Brain, Cloud, Eye, EyeOff, PlayCircle, Save, Search } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import { cn } from "@/lib/utils";

const serviceIcons: Record<string, typeof Bot> = {
  azure_foundry: Cloud,
  anthropic: Brain,
  openai: Bot,
  e2b: Box,
  langsmith: Search,
  pgvector: Brain,
};

export function PlatformServicesPage() {
  const queryClient = useQueryClient();
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [metadata, setMetadata] = useState<Record<string, Record<string, string>>>({});

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["platform-services"],
    queryFn: adminApi.getPlatformServices,
  });

  const updateMutation = useMutation({
    mutationFn: ({
      key,
      isEnabled,
      apiKey,
      configMetadata,
    }: {
      key: string;
      isEnabled?: boolean;
      apiKey?: string;
      configMetadata?: Record<string, string>;
    }) => adminApi.updatePlatformService(key, { isEnabled, apiKey, configMetadata }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["platform-services"] }),
  });

  const testMutation = useMutation({
    mutationFn: (key: string) => adminApi.testPlatformService(key),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const getMeta = (serviceKey: string, field: string, fallback = "") => {
    if (metadata[serviceKey]?.[field] !== undefined) return metadata[serviceKey][field];
    const svc = (data ?? []).find((s) => s.serviceKey === serviceKey);
    const value = svc?.configMetadata?.[field];
    return value !== undefined && value !== null ? String(value) : fallback;
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="AI Platform Services"
        description="Core services that power agents for all tenants. Use Microsoft Foundry for Azure-deployed models."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        {(data ?? []).map((service) => {
          const Icon = serviceIcons[service.serviceKey] ?? Box;
          const isFoundry = service.serviceKey === "azure_foundry";
          return (
            <div key={service.id} className="rounded-lg border bg-card p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold">{service.displayName}</h3>
                    <p className="text-xs text-muted-foreground">{service.serviceKey}</p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={service.isEnabled}
                  onChange={(e) => updateMutation.mutate({ key: service.serviceKey, isEnabled: e.target.checked })}
                />
              </div>
              <p className="mt-3 text-sm text-muted-foreground">{service.description}</p>

              {isFoundry && (
                <div className="mt-4 space-y-3 rounded-md border border-blue-200 bg-blue-50/50 p-3 text-xs text-blue-900 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-100">
                  <p className="font-medium">Microsoft Foundry setup</p>
                  <p>
                    Copy from Foundry → Models → your deployment: <strong>Project endpoint</strong>,{" "}
                    <strong>API key</strong>, and <strong>deployment name</strong> (e.g. claude-sonnet-4-6).
                  </p>
                  <p>
                    Then set Platform Settings → Default LLM Provider to <code>azure_foundry</code>.
                  </p>
                </div>
              )}

              {isFoundry && (
                <div className="mt-4 space-y-3">
                  <div>
                    <label className="text-xs font-medium">Project endpoint URL</label>
                    <input
                      type="text"
                      placeholder="https://your-resource.services.ai.azure.com/api/projects/..."
                      value={getMeta(service.serviceKey, "endpoint")}
                      onChange={(e) =>
                        setMetadata((p) => ({
                          ...p,
                          [service.serviceKey]: { ...p[service.serviceKey], endpoint: e.target.value },
                        }))
                      }
                      className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium">Chat deployment name</label>
                    <input
                      type="text"
                      placeholder="claude-sonnet-4-6"
                      value={getMeta(service.serviceKey, "deployment_name", "claude-sonnet-4-6")}
                      onChange={(e) =>
                        setMetadata((p) => ({
                          ...p,
                          [service.serviceKey]: { ...p[service.serviceKey], deployment_name: e.target.value },
                        }))
                      }
                      className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium">Embedding deployment name</label>
                    <input
                      type="text"
                      placeholder="text-embedding-3-small"
                      value={getMeta(service.serviceKey, "embedding_deployment", "text-embedding-3-small")}
                      onChange={(e) =>
                        setMetadata((p) => ({
                          ...p,
                          [service.serviceKey]: {
                            ...p[service.serviceKey],
                            embedding_deployment: e.target.value,
                          },
                        }))
                      }
                      className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm"
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      Use an embedding model deployment (e.g. text-embedding-3-small), not a chat model.
                    </p>
                  </div>
                </div>
              )}

              <div className="relative mt-4">
                <label className="text-xs font-medium">API key</label>
                <input
                  type={showKeys[service.serviceKey] ? "text" : "password"}
                  placeholder={service.isConfigured ? "••••••••••••••••" : "Enter API key"}
                  value={apiKeys[service.serviceKey] ?? ""}
                  onChange={(e) => setApiKeys((p) => ({ ...p, [service.serviceKey]: e.target.value }))}
                  className="mt-1 h-9 w-full rounded-md border bg-background px-3 pr-10 text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowKeys((p) => ({ ...p, [service.serviceKey]: !p[service.serviceKey] }))}
                  className="absolute right-2 top-7 text-muted-foreground"
                >
                  {showKeys[service.serviceKey] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              <div className="mt-4 flex items-center justify-between border-t pt-4">
                <span
                  className={cn(
                    "text-xs font-medium",
                    service.isConfigured ? "text-emerald-600" : "text-muted-foreground"
                  )}
                >
                  {service.isConfigured ? "Configured" : "Not configured"}
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => testMutation.mutate(service.serviceKey)}
                    className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium"
                  >
                    <PlayCircle className="h-3.5 w-3.5" />
                    Test
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const patch: {
                        key: string;
                        apiKey?: string;
                        configMetadata?: Record<string, string>;
                      } = { key: service.serviceKey };
                      if (apiKeys[service.serviceKey]) patch.apiKey = apiKeys[service.serviceKey];
                      if (isFoundry) {
                        patch.configMetadata = {
                          endpoint: getMeta(service.serviceKey, "endpoint"),
                          deployment_name: getMeta(service.serviceKey, "deployment_name", "claude-sonnet-4-6"),
                          embedding_deployment: getMeta(
                            service.serviceKey,
                            "embedding_deployment",
                            "text-embedding-3-small"
                          ),
                        };
                      }
                      updateMutation.mutate(patch);
                    }}
                    className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                  >
                    <Save className="h-3.5 w-3.5" />
                    Save
                  </button>
                </div>
              </div>
              {testMutation.data && testMutation.variables === service.serviceKey && (
                <p
                  className={cn(
                    "mt-2 text-xs",
                    testMutation.data.success ? "text-emerald-600" : "text-red-600"
                  )}
                >
                  {testMutation.data.message}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
