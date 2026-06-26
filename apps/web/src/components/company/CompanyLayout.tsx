import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Bot, FolderKanban, LayoutDashboard, LogOut, Plug, Settings, Sparkles, User, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { formatRole, isTeamLead } from "@/types/roles";

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean; teamLeadOnly?: boolean };

export function CompanyLayout() {
  const { user, workspace, company, logout } = useAuth();
  const ctx = workspace ?? company;
  const navigate = useNavigate();
  const teamLead = isTeamLead(ctx?.role);

  const initials = user?.fullName
    ?.split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() ?? "WS";

  const navItems: NavItem[] = [
    { to: "/workspace", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/workspace/projects", label: "Projects", icon: FolderKanban },
    { to: "/workspace/integrations", label: "My Integrations", icon: Plug },
    { to: "/workspace/my-agents", label: "My Agents", icon: Bot },
    { to: "/workspace/services", label: "AI Services", icon: Sparkles },
    { to: "/workspace/profile", label: "Profile", icon: User },
    { to: "/workspace/team", label: "Team", icon: Users, teamLeadOnly: true },
    { to: "/workspace/agents", label: "AI Agents", icon: Bot, teamLeadOnly: true },
    { to: "/workspace/settings", label: "Settings", icon: Settings, teamLeadOnly: true },
  ];

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r bg-card">
        <div className="flex h-16 shrink-0 items-center gap-3 border-b px-5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary">
            <LayoutDashboard className="h-4 w-4 text-primary-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold leading-tight">{ctx?.name ?? "Workspace"}</p>
            <p className="truncate text-xs text-muted-foreground">AI Dev Platform</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Workspace
          </p>
          {navItems
            .filter((item) => !item.teamLeadOnly || teamLead)
            .map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{label}</span>
              </NavLink>
            ))}
        </nav>

        <div className="shrink-0 border-t p-4">
          <div className="flex items-center gap-3 rounded-lg bg-muted/40 p-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium leading-tight">{user?.fullName}</p>
              <p className="truncate text-xs text-muted-foreground">{formatRole(ctx?.role ?? "")}</p>
            </div>
            <button
              type="button"
              onClick={async () => {
                await logout();
                navigate("/workspace/login");
              }}
              className="shrink-0 rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground"
              aria-label="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="flex-1 p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
