import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  LogOut,
  MessageSquare,
  Plug,
  RefreshCw,
  Send,
  Users,
} from "lucide-react";
import { PageHeader } from "@/components/admin/PageHeader";
import { LoadingState, ErrorState } from "@/components/admin/LoadingState";
import { teamsApi } from "@/services/teamsApi";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

function formatTime(iso: string | null) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function CompanyTeamsPage() {
  const { slug } = useParams<{ slug: string }>();
  const { company } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [banner, setBanner] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isViewer = company?.role === "viewer";

  useEffect(() => {
    if (searchParams.get("teams_connected") === "1") {
      setBanner("Microsoft Teams connected successfully.");
      searchParams.delete("teams_connected");
      setSearchParams(searchParams, { replace: true });
      queryClient.invalidateQueries({ queryKey: ["teams-status"] });
      queryClient.invalidateQueries({ queryKey: ["teams-chats"] });
    }
    const err = searchParams.get("teams_error");
    if (err) {
      setBanner(`Teams connection failed: ${err}`);
      searchParams.delete("teams_error");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, queryClient]);

  const statusQuery = useQuery({
    queryKey: ["teams-status"],
    queryFn: teamsApi.getStatus,
  });

  const chatsQuery = useQuery({
    queryKey: ["teams-chats"],
    queryFn: () => teamsApi.getChats(true),
    enabled: statusQuery.data?.isConnected === true,
  });

  const messagesQuery = useQuery({
    queryKey: ["teams-messages", selectedChatId],
    queryFn: () => teamsApi.getMessages(selectedChatId!),
    enabled: !!selectedChatId,
  });

  useEffect(() => {
    if (chatsQuery.data?.length && !selectedChatId) {
      setSelectedChatId(chatsQuery.data[0].graphChatId);
    }
  }, [chatsQuery.data, selectedChatId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messagesQuery.data]);

  const oauthMutation = useMutation({
    mutationFn: () =>
      teamsApi.startOAuth(`${window.location.origin}/c/${slug}/teams`),
    onSuccess: ({ authorizeUrl }) => {
      window.location.href = authorizeUrl;
    },
    onError: (err) => setBanner(String(err)),
  });

  const disconnectMutation = useMutation({
    mutationFn: teamsApi.disconnect,
    onSuccess: () => {
      setBanner("Microsoft Teams disconnected.");
      setSelectedChatId(null);
      queryClient.invalidateQueries({ queryKey: ["teams-status"] });
      queryClient.invalidateQueries({ queryKey: ["teams-chats"] });
    },
    onError: (err) => setBanner(String(err)),
  });

  const syncMutation = useMutation({
    mutationFn: teamsApi.sync,
    onSuccess: (res) => {
      setBanner(`Synced ${res.chatsSynced} chats and ${res.messagesSynced} messages.`);
      queryClient.invalidateQueries({ queryKey: ["teams-chats"] });
      queryClient.invalidateQueries({ queryKey: ["teams-messages", selectedChatId] });
      queryClient.invalidateQueries({ queryKey: ["teams-status"] });
    },
    onError: (err) => setBanner(String(err)),
  });

  const sendMutation = useMutation({
    mutationFn: (content: string) => teamsApi.sendMessage(selectedChatId!, content),
    onSuccess: () => {
      setDraft("");
      queryClient.invalidateQueries({ queryKey: ["teams-messages", selectedChatId] });
      queryClient.invalidateQueries({ queryKey: ["teams-chats"] });
    },
    onError: (err) => setBanner(String(err)),
  });

  if (statusQuery.isLoading) return <LoadingState />;
  if (statusQuery.isError) return <ErrorState message={String(statusQuery.error)} />;

  const status = statusQuery.data!;

  if (!status.isAssigned) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Microsoft Teams"
          description="View and send Teams chats from your workspace."
        />
        <div className="rounded-lg border border-dashed p-8 text-center">
          <Users className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="mt-4 text-sm text-muted-foreground">
            Microsoft Teams has not been assigned to your account.
          </p>
          {company?.role === "admin" ? (
            <p className="mt-2 text-sm text-muted-foreground">
              Go to{" "}
              <Link to={`/c/${slug}/team`} className="text-primary hover:underline">
                Team
              </Link>{" "}
              to assign Teams to yourself or employees.
            </p>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">
              Ask your company admin to assign Microsoft Teams to you.
            </p>
          )}
        </div>
      </div>
    );
  }

  if (!status.isConnected) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Microsoft Teams"
          description="Connect your Microsoft account to view and reply to Teams chats."
        />
        {banner && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
            {banner}
          </div>
        )}
        <div className="rounded-lg border bg-card p-8 text-center">
          <MessageSquare className="mx-auto h-12 w-12 text-primary" />
          <h2 className="mt-4 text-lg font-semibold">Connect Microsoft Teams</h2>
          <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">
            Sign in with your own Microsoft account (personal or work). Your OAuth tokens are stored
            securely and only used for your assigned Teams access.
          </p>
          {status.oauthAvailable ? (
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                disabled={oauthMutation.isPending || isViewer}
                onClick={() => oauthMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                <Plug className="h-4 w-4" />
                {oauthMutation.isPending ? "Redirecting…" : "Connect with Microsoft"}
              </button>
            </div>
          ) : (
            <div className="mx-auto mt-6 max-w-lg rounded-lg border border-dashed bg-muted/30 p-4 text-left text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Platform OAuth not configured yet</p>
              <p className="mt-2">{status.message}</p>
              <p className="mt-3">
                Add <code className="rounded bg-muted px-1">TEAMS_CLIENT_ID</code> and{" "}
                <code className="rounded bg-muted px-1">TEAMS_CLIENT_SECRET</code> to your{" "}
                <code className="rounded bg-muted px-1">.env</code> file (see{" "}
                <code className="rounded bg-muted px-1">.env.example</code>), then restart the API.
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  const chats = chatsQuery.data ?? [];
  const selectedChat = chats.find((c) => c.graphChatId === selectedChatId);
  const messages = messagesQuery.data ?? [];

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col gap-4">
      <div className="flex shrink-0 items-start justify-between gap-4">
        <PageHeader
          title="Microsoft Teams"
          description={
            status.microsoftEmail
              ? `Connected as ${status.microsoftEmail}`
              : "Your Teams chats"
          }
        />
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            disabled={syncMutation.isPending}
            onClick={() => syncMutation.mutate()}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
          >
            <RefreshCw className={cn("h-4 w-4", syncMutation.isPending && "animate-spin")} />
            Sync
          </button>
          {!isViewer && (
            <button
              type="button"
              disabled={disconnectMutation.isPending}
              onClick={() => disconnectMutation.mutate()}
              className="inline-flex items-center gap-2 rounded-md border border-destructive/30 px-3 py-2 text-sm text-destructive hover:bg-destructive/5 disabled:opacity-50"
            >
              <LogOut className="h-4 w-4" />
              Disconnect
            </button>
          )}
        </div>
      </div>

      {banner && (
        <div className="shrink-0 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-100">
          {banner}
        </div>
      )}

      <div className="flex min-h-0 flex-1 overflow-hidden rounded-lg border bg-card">
        <aside className="flex w-72 shrink-0 flex-col border-r">
          <div className="border-b px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Chats</p>
            {status.lastSyncedAt && (
              <p className="mt-1 text-xs text-muted-foreground">
                Last sync {formatTime(status.lastSyncedAt)}
              </p>
            )}
          </div>
          <div className="flex-1 overflow-y-auto">
            {chatsQuery.isLoading ? (
              <p className="p-4 text-sm text-muted-foreground">Loading chats…</p>
            ) : chats.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">No chats yet. Try syncing.</p>
            ) : (
              chats.map((chat) => (
                <button
                  key={chat.id}
                  type="button"
                  onClick={() => setSelectedChatId(chat.graphChatId)}
                  className={cn(
                    "w-full border-b px-4 py-3 text-left transition-colors hover:bg-muted/50",
                    selectedChatId === chat.graphChatId && "bg-muted"
                  )}
                >
                  <p className="truncate text-sm font-medium">{chat.displayName}</p>
                  {chat.lastMessagePreview && (
                    <p className="mt-1 truncate text-xs text-muted-foreground">{chat.lastMessagePreview}</p>
                  )}
                  {chat.lastMessageAt && (
                    <p className="mt-1 text-[10px] text-muted-foreground">{formatTime(chat.lastMessageAt)}</p>
                  )}
                </button>
              ))
            )}
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          {selectedChat ? (
            <>
              <div className="border-b px-5 py-3">
                <p className="font-medium">{selectedChat.displayName}</p>
                <p className="text-xs capitalize text-muted-foreground">{selectedChat.chatType}</p>
              </div>
              <div className="flex-1 space-y-3 overflow-y-auto p-5">
                {messagesQuery.isLoading ? (
                  <p className="text-sm text-muted-foreground">Loading messages…</p>
                ) : messages.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No messages in this chat.</p>
                ) : (
                  messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={cn("flex", msg.isOwnMessage ? "justify-end" : "justify-start")}
                    >
                      <div
                        className={cn(
                          "max-w-[75%] rounded-lg px-3 py-2 text-sm",
                          msg.isOwnMessage
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-foreground"
                        )}
                      >
                        {!msg.isOwnMessage && msg.senderName && (
                          <p className="mb-1 text-xs font-semibold opacity-80">{msg.senderName}</p>
                        )}
                        <p className="whitespace-pre-wrap">{msg.bodyText}</p>
                        <p
                          className={cn(
                            "mt-1 text-[10px]",
                            msg.isOwnMessage ? "text-primary-foreground/70" : "text-muted-foreground"
                          )}
                        >
                          {formatTime(msg.messageCreatedAt)}
                        </p>
                      </div>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>
              {!isViewer && (
                <form
                  className="flex gap-2 border-t p-4"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const text = draft.trim();
                    if (!text || !selectedChatId) return;
                    sendMutation.mutate(text);
                  }}
                >
                  <input
                    type="text"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder="Type a message…"
                    className="flex-1 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                  />
                  <button
                    type="submit"
                    disabled={!draft.trim() || sendMutation.isPending}
                    className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  >
                    <Send className="h-4 w-4" />
                    Send
                  </button>
                </form>
              )}
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
              Select a chat to view messages
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
