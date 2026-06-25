import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { Building2, FolderKanban, LayoutDashboard, LogOut, MessageSquare, Plug, Settings, Sparkles, User, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean; adminOnly?: boolean };

export function CompanyLayout() {
  const { slug } = useParams<{ slug: string }>();
  const { user, company, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = company?.role === "admin";

  const initials = user?.fullName
    ?.split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() ?? "CO";

  const navItems: NavItem[] = [
    { to: `/c/${slug}`, label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: `/c/${slug}/projects`, label: "Projects", icon: FolderKanban },
    { to: `/c/${slug}/integrations`, label: "My Integrations", icon: Plug },
    { to: `/c/${slug}/teams`, label: "Teams", icon: MessageSquare },
    { to: `/c/${slug}/services`, label: "AI Services", icon: Sparkles },
    { to: `/c/${slug}/profile`, label: "Profile", icon: User },
    { to: `/c/${slug}/team`, label: "Team", icon: Users, adminOnly: true },
    { to: `/c/${slug}/settings`, label: "Settings", icon: Settings, adminOnly: true },
  ];

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r bg-card">
        <div className="flex h-16 shrink-0 items-center gap-3 border-b px-5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary">
            <Building2 className="h-4 w-4 text-primary-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold leading-tight">{company?.name}</p>
            <p className="truncate text-xs text-muted-foreground">/{slug}</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Workspace
          </p>
          {navItems
            .filter((item) => !item.adminOnly || isAdmin)
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
              <p className="truncate text-xs capitalize text-muted-foreground">{company?.role}</p>
            </div>
            <button
              type="button"
              onClick={async () => {
                await logout();
                navigate(`/c/${slug}/login`);
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
