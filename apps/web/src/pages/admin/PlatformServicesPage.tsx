import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Box, Brain, Eye, EyeOff, PlayCircle, Save, Search } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import { cn } from "@/lib/utils";

const serviceIcons: Record<string, typeof Bot> = {
  anthropic: Brain, openai: Bot, e2b: Box, langsmith: Search, pgvector: Brain,
};

export function PlatformServicesPage() {
  const queryClient = useQueryClient();
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["platform-services"],
    queryFn: adminApi.getPlatformServices,
  });

  const updateMutation = useMutation({
    mutationFn: ({ key, isEnabled, apiKey }: { key: string; isEnabled?: boolean; apiKey?: string }) =>
      adminApi.updatePlatformService(key, { isEnabled, apiKey }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["platform-services"] }),
  });

  const testMutation = useMutation({
    mutationFn: (key: string) => adminApi.testPlatformService(key),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  return (
    <div className="space-y-8">
      <PageHeader title="AI Platform Services" description="Core services that power agents for all tenants." />
      <div className="grid gap-4 lg:grid-cols-2">
        {(data ?? []).map((service) => {
          const Icon = serviceIcons[service.serviceKey] ?? Box;
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
              <div className="relative mt-4">
                <input
                  type={showKeys[service.serviceKey] ? "text" : "password"}
                  placeholder={service.isConfigured ? "••••••••••••••••" : "Enter API key"}
                  value={apiKeys[service.serviceKey] ?? ""}
                  onChange={(e) => setApiKeys((p) => ({ ...p, [service.serviceKey]: e.target.value }))}
                  className="h-9 w-full rounded-md border bg-background px-3 pr-10 text-sm"
                />
                <button type="button" onClick={() => setShowKeys((p) => ({ ...p, [service.serviceKey]: !p[service.serviceKey] }))} className="absolute right-2 top-1/2 -translate-y-1/2">
                  {showKeys[service.serviceKey] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <div className="mt-4 flex items-center justify-between border-t pt-4">
                <span className={cn("text-xs font-medium", service.isConfigured ? "text-emerald-600" : "text-muted-foreground")}>
                  {service.isConfigured ? "Configured" : "Not configured"}
                </span>
                <div className="flex gap-2">
                  <button type="button" onClick={() => testMutation.mutate(service.serviceKey)} className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium">
                    <PlayCircle className="h-3.5 w-3.5" />
                    Test
                  </button>
                  <button
                    type="button"
                    onClick={() => updateMutation.mutate({ key: service.serviceKey, apiKey: apiKeys[service.serviceKey] })}
                    className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                  >
                    <Save className="h-3.5 w-3.5" />
                    Save
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
