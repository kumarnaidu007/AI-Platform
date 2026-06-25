import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { companyApi } from "@/services/companyApi";
import { useAuth } from "@/context/AuthContext";

export function CompanyProfilePage() {
  const { user, company } = useAuth();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const isViewer = company?.role === "viewer";

  const { data, isLoading, isError, error: loadError } = useQuery({
    queryKey: ["user-profile"],
    queryFn: companyApi.getProfile,
  });

  const profileMutation = useMutation({
    mutationFn: (fullName: string) => companyApi.updateProfile(fullName),
    onSuccess: () => {
      setMessage("Profile updated");
      setProfileError(null);
      queryClient.invalidateQueries({ queryKey: ["user-profile"] });
    },
    onError: () => setProfileError("Failed to update profile"),
  });

  const passwordMutation = useMutation({
    mutationFn: ({ current, next }: { current: string; next: string }) =>
      companyApi.changePassword(current, next),
    onSuccess: (res) => {
      setMessage(res.message);
      setProfileError(null);
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Failed")
          : "Failed to change password";
      setProfileError(msg);
    },
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={String(loadError)} />;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title="My profile" description="Your account in this company workspace." />

      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>
      )}
      {profileError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{profileError}</div>
      )}

      <div className="rounded-lg border bg-card p-6">
        <h3 className="text-sm font-semibold">Account details</h3>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Email</dt>
            <dd className="font-medium">{data?.email ?? user?.email}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Role</dt>
            <dd className="font-medium capitalize">{data?.role}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Integrations</dt>
            <dd className="font-medium">
              {data?.integrationsConnected}/{data?.integrationsAssigned} connected
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Member since</dt>
            <dd className="font-medium">{data?.joinedAt ? new Date(data.joinedAt).toLocaleDateString() : "—"}</dd>
          </div>
        </dl>
      </div>

      {!isViewer && (
        <form
          className="space-y-4 rounded-lg border bg-card p-6"
          onSubmit={(e) => {
            e.preventDefault();
            setMessage(null);
            setProfileError(null);
            profileMutation.mutate(String(new FormData(e.currentTarget).get("full_name")));
          }}
        >
          <h3 className="text-sm font-semibold">Display name</h3>
          <input
            name="full_name"
            type="text"
            required
            defaultValue={data?.fullName}
            className="h-10 w-full rounded-md border bg-background px-3 text-sm"
          />
          <button
            type="submit"
            disabled={profileMutation.isPending}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            {profileMutation.isPending ? "Saving..." : "Save name"}
          </button>
        </form>
      )}

      <form
        className="space-y-4 rounded-lg border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault();
          setMessage(null);
          setProfileError(null);
          const fd = new FormData(e.currentTarget);
          passwordMutation.mutate({
            current: String(fd.get("current_password")),
            next: String(fd.get("new_password")),
          });
          e.currentTarget.reset();
        }}
      >
        <h3 className="text-sm font-semibold">Change password</h3>
        <input
          name="current_password"
          type="password"
          required
          placeholder="Current password"
          className="h-10 w-full rounded-md border bg-background px-3 text-sm"
        />
        <input
          name="new_password"
          type="password"
          required
          minLength={8}
          placeholder="New password (min 8 characters)"
          className="h-10 w-full rounded-md border bg-background px-3 text-sm"
        />
        <button
          type="submit"
          disabled={passwordMutation.isPending}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          {passwordMutation.isPending ? "Updating..." : "Update password"}
        </button>
      </form>
    </div>
  );
}
