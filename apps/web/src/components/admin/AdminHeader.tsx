import { Bell, LogOut, Search } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useNavigate } from "react-router-dom";

export function AdminHeader() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const initials = user?.fullName
    ?.split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() ?? "SA";

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-card/80 px-6 backdrop-blur-sm lg:px-8">
      <div className="relative w-full max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          placeholder="Search companies, projects..."
          className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none ring-ring placeholder:text-muted-foreground focus:ring-2"
        />
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          className="relative rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label="Notifications"
        >
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-destructive" />
        </button>
        <div className="flex items-center gap-3 border-l pl-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            {initials}
          </div>
          <div className="hidden sm:block">
            <p className="text-sm font-medium leading-none">{user?.fullName ?? "Super Admin"}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{user?.email}</p>
          </div>
          <button
            type="button"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
            className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
