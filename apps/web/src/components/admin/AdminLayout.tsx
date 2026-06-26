import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bot,
  Users,
  BarChart3,
  LayoutDashboard,
  Plug,
  ScrollText,
  Server,
  Settings,
  Shield,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { AdminHeader } from "./AdminHeader";
import { adminApi } from "@/services/adminApi";

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean };

const platformNav: NavItem[] = [
  { to: "/admin/integrations", label: "Integrations", icon: Plug },
  { to: "/admin/platform-services", label: "AI Services", icon: Sparkles },
  { to: "/admin/agents", label: "AI Agents", icon: Bot },
  { to: "/admin/platform-settings", label: "Platform Settings", icon: Settings },
];

const operationsNav: NavItem[] = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/system-health", label: "System Health", icon: Server },
  { to: "/admin/audit-log", label: "Audit Log", icon: ScrollText },
];

const tenantsNav: NavItem[] = [
  { to: "/admin/teams", label: "Teams", icon: Users },
  { to: "/admin/usage", label: "Token Usage", icon: BarChart3 },
];

function NavSection({ title, items }: { title: string; items: NavItem[] }) {
  return (
    <div className="space-y-1">
      <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            )
          }
        >
          <Icon className="h-4 w-4 shrink-0" />
          {label}
        </NavLink>
      ))}
    </div>
  );
}

export function AdminLayout() {
  const { data: dashboard } = useQuery({
    queryKey: ["dashboard"],
    queryFn: adminApi.getDashboard,
    refetchInterval: 60_000,
  });

  const connected = dashboard?.platformStats.connectedIntegrations ?? 0;
  const total = dashboard?.platformStats.totalIntegrations ?? 0;

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r bg-card">
        <div className="flex h-16 items-center gap-2.5 border-b px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary">
            <Shield className="h-4 w-4 text-primary-foreground" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-none">AI Dev Platform</p>
            <p className="mt-0.5 text-xs text-muted-foreground">Super Admin</p>
          </div>
        </div>

        <nav className="flex-1 space-y-5 overflow-y-auto p-3">
          <NavSection title="Platform" items={platformNav} />
          <NavSection title="Operations" items={operationsNav} />
          <NavSection title="Organization" items={tenantsNav} />
        </nav>

        <div className="border-t p-4">
          <div className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2">
            <Activity className="h-4 w-4 text-emerald-600" />
            <div className="min-w-0">
              <p className="truncate text-xs font-medium">Platform Online</p>
              <p className="text-xs text-muted-foreground">
                {connected}/{total} integrations connected
              </p>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex flex-1 flex-col pl-64">
        <AdminHeader />
        <main className="flex-1 p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
