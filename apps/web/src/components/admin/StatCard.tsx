import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon: LucideIcon;
  trend?: { value: string; positive: boolean };
  className?: string;
}

export function StatCard({ label, value, subtext, icon: Icon, trend, className }: StatCardProps) {
  return (
    <div className={cn("rounded-lg border bg-card p-5", className)}>
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold tracking-tight">{value}</p>
          {subtext && <p className="text-xs text-muted-foreground">{subtext}</p>}
          {trend && (
            <p className={cn("text-xs font-medium", trend.positive ? "text-emerald-600" : "text-red-600")}>
              {trend.value}
            </p>
          )}
        </div>
        <div className="rounded-md bg-primary/10 p-2.5">
          <Icon className="h-5 w-5 text-primary" />
        </div>
      </div>
    </div>
  );
}
