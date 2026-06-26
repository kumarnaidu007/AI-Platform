import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { companyApi } from "@/services/companyApi";
import { githubApi } from "@/services/githubApi";
import { getApiErrorMessage } from "@/services/authApi";

export function CompanyCreateProjectPage() {
  useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [repoUrl, setRepoUrl] = useState("");
  const [repoMessage, setRepoMessage] = useState<string | null>(null);

  const verifyRepoMutation = useMutation({
    mutationFn: () => githubApi.verifyRepo(repoUrl),
    onSuccess: (info) => setRepoMessage(`Repository verified — default branch: ${info.defaultBranch}`),
    onError: (err: unknown) => setRepoMessage(getApiErrorMessage(err, "Could not verify repository")),
  });

  const createMutation = useMutation({
    mutationFn: (form: FormData) =>
      companyApi.createProject({
        name: String(form.get("name")),
        description: String(form.get("description") || "") || undefined,
        frontendStack: String(form.get("frontend_stack") || "") || undefined,
        backendStack: String(form.get("backend_stack") || "") || undefined,
        dbType: String(form.get("db_type") || "") || undefined,
        vcsProvider: "github",
        repoUrl: String(form.get("repo_url") || "") || undefined,
        pmTool: String(form.get("pm_tool") || "") || undefined,
      }),    onSuccess: (project) => navigate(`/workspace/projects/${project.id}`),
    onError: (err: unknown) => {
      const msg =
        err && typeof err === "object" && "response" in err
          ? String((err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Failed")
          : "Failed to create project";
      setError(msg);
    },
  });

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Link
        to={`/workspace/projects`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to projects
      </Link>

      <PageHeader title="New project" description="Configure a new AI automation project." />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>
      )}

      <form
        className="space-y-5 rounded-lg border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          createMutation.mutate(new FormData(e.currentTarget));
        }}
      >
        <div>
          <label htmlFor="name" className="block text-sm font-medium">
            Project name
          </label>
          <input id="name" name="name" required className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm" />
        </div>
        <div>
          <label htmlFor="description" className="block text-sm font-medium">
            Description
          </label>
          <textarea
            id="description"
            name="description"
            rows={3}
            className="mt-1.5 w-full rounded-md border bg-background px-3 py-2 text-sm"
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="frontend_stack" className="block text-sm font-medium">
              Frontend stack
            </label>
            <input
              id="frontend_stack"
              name="frontend_stack"
              placeholder="React, Vue..."
              className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm"
            />
          </div>
          <div>
            <label htmlFor="backend_stack" className="block text-sm font-medium">
              Backend stack
            </label>
            <input
              id="backend_stack"
              name="backend_stack"
              placeholder="FastAPI, Node..."
              className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm"
            />
          </div>
          <div>
            <label htmlFor="db_type" className="block text-sm font-medium">
              Database
            </label>
            <input
              id="db_type"
              name="db_type"
              placeholder="PostgreSQL..."
              className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm"
            />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="repo_url" className="block text-sm font-medium">
              GitHub repository URL
            </label>
            <div className="mt-1.5 flex gap-2">
              <input
                id="repo_url"
                name="repo_url"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/org/my-repo"
                required
                className="h-10 flex-1 rounded-md border bg-background px-3 text-sm"
              />
              <button
                type="button"
                disabled={!repoUrl.trim() || verifyRepoMutation.isPending}
                onClick={() => verifyRepoMutation.mutate()}
                className="rounded-md border px-3 text-sm font-medium"
              >
                Verify
              </button>
            </div>
            {repoMessage && <p className="mt-1 text-xs text-muted-foreground">{repoMessage}</p>}
            <p className="mt-1 text-xs text-muted-foreground">
              Connect GitHub under My Integrations first. Agents will branch from develop (or the repo default).
            </p>
          </div>
        </div>
        <div>
          <label htmlFor="pm_tool" className="block text-sm font-medium">
            PM tool
          </label>
          <input
            id="pm_tool"
            name="pm_tool"
            placeholder="jira, linear..."
            className="mt-1.5 h-10 w-full rounded-md border bg-background px-3 text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          {createMutation.isPending ? "Creating..." : "Create project"}
        </button>
      </form>
    </div>
  );
}
