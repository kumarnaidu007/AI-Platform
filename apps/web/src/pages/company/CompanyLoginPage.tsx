import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { Building2 } from "lucide-react";
import { PasswordInput } from "@/components/auth/PasswordInput";
import { useAuth } from "@/context/AuthContext";
import { getRememberedCompanyEmail, setRememberedCompanyEmail } from "@/lib/loginStorage";
import { getApiErrorMessage } from "@/services/authApi";

export function CompanyLoginPage() {
  const { slug } = useParams<{ slug: string }>();
  const { companyLogin, portal, company, isLoading } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [remember, setRemember] = useState(() => Boolean(slug && getRememberedCompanyEmail(slug)));
  const [email, setEmail] = useState(() => (slug ? getRememberedCompanyEmail(slug) : ""));

  if (!isLoading && portal === "company" && company?.slug === slug) {
    return <Navigate to={`/c/${slug}`} replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <div className="w-full max-w-md rounded-xl border bg-card p-8 shadow-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary">
            <Building2 className="h-6 w-6 text-primary-foreground" />
          </div>
          <h1 className="text-xl font-semibold">Company Portal</h1>
          <p className="mt-1 text-sm text-muted-foreground">Sign in to /{slug}</p>
        </div>

        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!slug) return;
            setError("");
            setSubmitting(true);
            const fd = new FormData(e.currentTarget);
            const emailValue = String(fd.get("email") ?? "").trim();
            const passwordValue = String(fd.get("password") ?? "");
            const rememberMe = fd.get("remember") === "on";
            try {
              await companyLogin(emailValue, passwordValue, slug);
              setRememberedCompanyEmail(slug, emailValue, rememberMe);
              navigate(`/c/${slug}`, { replace: true });
            } catch (err) {
              setError(getApiErrorMessage(err, "Login failed"));
            } finally {
              setSubmitting(false);
            }
          }}
        >
          <div>
            <label htmlFor="email" className="block text-sm font-medium">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="username"
              placeholder="admin@yourcompany.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium">Password</label>
            <PasswordInput id="password" autoComplete="current-password" />
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              name="remember"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-4 w-4 rounded border"
            />
            Remember email
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="h-10 w-full rounded-md bg-primary text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          <Link to="/login" className="underline hover:text-foreground">Super admin login</Link>
        </p>
      </div>
    </div>
  );
}
