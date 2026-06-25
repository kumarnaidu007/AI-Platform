import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { adminApi } from "@/services/adminApi";
import type { PlatformSetting } from "@/types/platform";
import { useState } from "react";

export function PlatformSettingsPage() {
  const queryClient = useQueryClient();
  const [local, setLocal] = useState<Record<string, PlatformSetting["value"]>>({});

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["platform-settings"],
    queryFn: adminApi.getPlatformSettings,
  });

  const saveMutation = useMutation({
    mutationFn: (settings: Record<string, unknown>) => adminApi.updatePlatformSettings(settings),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["platform-settings"] }),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  const settings = data ?? [];

  const getValue = (s: PlatformSetting) => (local[s.key] !== undefined ? local[s.key] : s.value);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title="Platform Settings" description="Global configuration for the AI Dev Platform." />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const payload: Record<string, unknown> = {};
          settings.forEach((s) => {
            payload[s.key] = getValue(s);
          });
          saveMutation.mutate(payload);
        }}
        className="space-y-4 rounded-lg border bg-card p-6"
      >
        {settings.map((setting) => (
          <div key={setting.key}>
            <label className="block text-sm font-medium">{setting.label}</label>
            <p className="mt-0.5 text-xs text-muted-foreground">{setting.description}</p>
            <div className="mt-2">
              {setting.type === "boolean" ? (
                <input
                  type="checkbox"
                  checked={Boolean(getValue(setting))}
                  onChange={(e) => setLocal((p) => ({ ...p, [setting.key]: e.target.checked }))}
                />
              ) : setting.type === "number" ? (
                <input
                  type="number"
                  value={Number(getValue(setting))}
                  onChange={(e) => setLocal((p) => ({ ...p, [setting.key]: Number(e.target.value) }))}
                  className="h-10 w-full rounded-md border px-3 text-sm"
                />
              ) : (
                <input
                  type="text"
                  value={String(getValue(setting))}
                  onChange={(e) => setLocal((p) => ({ ...p, [setting.key]: e.target.value }))}
                  className="h-10 w-full rounded-md border px-3 text-sm"
                />
              )}
            </div>
          </div>
        ))}
        <div className="flex justify-end border-t pt-4">
          <button type="submit" disabled={saveMutation.isPending} className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
            <Save className="h-4 w-4" />
            {saveMutation.isPending ? "Saving..." : "Save settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
