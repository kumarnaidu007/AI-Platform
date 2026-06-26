import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Plug, Sparkles } from "lucide-react";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import type { CompanyIntegrationAccess, CompanyServiceAccess } from "@/types/admin";
import type { CompanyAgentAccess } from "@/types/agents";

function AccessToggle({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange?: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange?.(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"
      } ${checked ? "bg-primary" : "bg-muted"}`}
    >
      <span
        className={`inline-block h-5 w-5 translate-y-0.5 rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-5" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

export function IntegrationsAccessSection({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["company-integrations-access", workspaceId],
    queryFn: () => adminApi.getCompanyIntegrationsAccess(workspaceId),
  });

  const mutation = useMutation({
    mutationFn: (integrations: CompanyIntegrationAccess[]) =>
      adminApi.updateCompanyIntegrationsAccess(
        workspaceId,
        integrations.map((i) => ({ integrationKey: i.integrationKey, isEnabled: i.isEnabled }))
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["company-integrations-access", workspaceId] }),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const enabledCount = (data ?? []).filter((i) => i.isEnabled && i.assignable).length;
  const assignable = (data ?? []).filter((i) => i.assignable);
  const blocked = (data ?? []).filter((i) => !i.assignable);

  return (
    <div className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Plug className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Integration access</h3>
        </div>
        <span className="text-xs text-muted-foreground">{enabledCount} enabled for workspace</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Toggle which integrations this specific team may use. Team leads assign them to individual members.
      </p>
      <div className="mt-4 space-y-2">
        {assignable.map((item) => (
          <div
            key={item.integrationKey}
            className="flex items-center justify-between gap-3 rounded-md border px-3 py-2.5"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium">{item.name}</p>
              <p className="text-xs text-muted-foreground capitalize">{item.category} · connected</p>
            </div>
            <AccessToggle
              checked={item.isEnabled}
              disabled={mutation.isPending}
              onChange={(isEnabled) => {
                const next = (data ?? []).map((row) =>
                  row.integrationKey === item.integrationKey ? { ...row, isEnabled } : row
                );
                mutation.mutate(next);
              }}
            />
          </div>
        ))}
        {assignable.length === 0 && blocked.length === 0 && (
          <p className="text-sm text-muted-foreground">No integrations available.</p>
        )}
        {blocked.length > 0 && (
          <div className="pt-2">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Connect these in Platform → Integrations first
            </p>
            {blocked.map((item) => (
              <div
                key={item.integrationKey}
                className="mb-2 flex items-center justify-between gap-3 rounded-md border border-dashed bg-muted/30 px-3 py-2.5 opacity-70"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">{item.name}</p>
                  <p className="text-xs text-muted-foreground capitalize">
                    {item.category} · {item.connectionStatus.replace(/_/g, " ")}
                  </p>
                </div>
                <AccessToggle checked={false} disabled />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function ServicesAccessSection({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["company-services-access", workspaceId],
    queryFn: () => adminApi.getCompanyServicesAccess(workspaceId),
  });

  const mutation = useMutation({
    mutationFn: (services: CompanyServiceAccess[]) =>
      adminApi.updateCompanyServicesAccess(
        workspaceId,
        services.map((s) => ({ serviceKey: s.serviceKey, isEnabled: s.isEnabled }))
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["company-services-access", workspaceId] }),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const enabledCount = (data ?? []).filter((s) => s.isEnabled && s.assignable).length;
  const assignable = (data ?? []).filter((s) => s.assignable);
  const blocked = (data ?? []).filter((s) => !s.assignable);

  return (
    <div className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">AI services access</h3>
        </div>
        <span className="text-xs text-muted-foreground">{enabledCount} enabled</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Grant LLM and runtime services (OpenAI, Anthropic, etc.) to this workspace.
      </p>
      <div className="mt-4 space-y-2">
        {assignable.map((item) => (
          <div
            key={item.serviceKey}
            className="flex items-center justify-between gap-3 rounded-md border px-3 py-2.5"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium">{item.displayName}</p>
              <p className="text-xs text-muted-foreground">Uses platform credentials</p>
            </div>
            <AccessToggle
              checked={item.isEnabled}
              disabled={mutation.isPending}
              onChange={(isEnabled) => {
                const next = (data ?? []).map((row) =>
                  row.serviceKey === item.serviceKey ? { ...row, isEnabled } : row
                );
                mutation.mutate(next);
              }}
            />
          </div>
        ))}
        {blocked.length > 0 && (
          <div className="pt-2">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Configure in Platform → AI Services first</p>
            {blocked.map((item) => (
              <div
                key={item.serviceKey}
                className="mb-2 flex items-center justify-between gap-3 rounded-md border border-dashed bg-muted/30 px-3 py-2.5 opacity-70"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">{item.displayName}</p>
                  <p className="text-xs text-muted-foreground">Not configured</p>
                </div>
                <AccessToggle checked={false} disabled />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function AgentsAccessSection({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["company-agents-access", workspaceId],
    queryFn: () => adminApi.getCompanyAgentsAccess(workspaceId),
  });

  const mutation = useMutation({
    mutationFn: (agents: CompanyAgentAccess[]) =>
      adminApi.updateCompanyAgentsAccess(
        workspaceId,
        agents.map((a) => ({ agentKey: a.agentKey, isEnabled: a.isEnabled }))
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["company-agents-access", workspaceId] }),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const enabledCount = (data ?? []).filter((a) => a.isEnabled && a.assignable).length;
  const assignable = (data ?? []).filter((a) => a.assignable);
  const blocked = (data ?? []).filter((a) => !a.assignable);

  return (
    <div className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">AI agents access</h3>
        </div>
        <span className="text-xs text-muted-foreground">{enabledCount} granted</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Enable pipeline agents for this team. Team leads assign agents per member.
      </p>
      <div className="mt-4 space-y-2">
        {assignable.map((item) => (
          <div
            key={item.agentKey}
            className="flex items-center justify-between gap-3 rounded-md border px-3 py-2.5"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium">{item.name}</p>
              <p className="text-xs text-muted-foreground capitalize">
                {item.group ?? item.category} · Step {item.defaultStepOrder}
              </p>
            </div>
            <AccessToggle
              checked={item.isEnabled}
              disabled={mutation.isPending}
              onChange={(isEnabled) => {
                const next = (data ?? []).map((row) =>
                  row.agentKey === item.agentKey ? { ...row, isEnabled } : row
                );
                mutation.mutate(next);
              }}
            />
          </div>
        ))}
        {blocked.length > 0 && (
          <div className="pt-2">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Enable in Platform → AI Agents first</p>
            {blocked.map((item) => (
              <div
                key={item.agentKey}
                className="mb-2 flex items-center justify-between gap-3 rounded-md border border-dashed bg-muted/30 px-3 py-2.5 opacity-70"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">{item.name}</p>
                  <p className="text-xs text-muted-foreground">Disabled platform-wide</p>
                </div>
                <AccessToggle checked={false} disabled />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
