import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";

export function CompanyServicesPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["company-services"],
    queryFn: companyApi.getServices,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(error)} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI services"
        description="Platform AI services granted to your company. Agents use these for LLM and automation tasks."
      />

      {(data ?? []).length === 0 ? (
        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          No AI services granted yet. Contact your platform administrator.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {(data ?? []).map((service) => (
            <div key={service.serviceKey} className="flex items-start gap-3 rounded-lg border bg-card p-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <Sparkles className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium">{service.displayName}</p>
                <p className="mt-0.5 font-mono text-xs text-muted-foreground">{service.serviceKey}</p>
                <span className="mt-2 inline-block rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
                  Available
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
