import { useState } from "react";
import { ChevronDown, ChevronRight, FileCode } from "lucide-react";
import type { PendingChanges, ApprovePrPayload } from "@/services/intakeApi";
import { cn } from "@/lib/utils";

interface PendingChangesReviewProps {
  pending: PendingChanges;
  repoUrl: string | null;
  busy: boolean;
  onApprove: (payload: ApprovePrPayload) => void;
}

function FilePreview({ path, content }: { path: string; content: string }) {
  const [open, setOpen] = useState(false);
  const lines = content.split("\n").length;

  return (
    <div className="rounded-md border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted/50"
      >
        {open ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
        <FileCode className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="font-mono text-xs">{path}</span>
        <span className="ml-auto text-[10px] text-muted-foreground">{lines} lines</span>
      </button>
      {open && (
        <pre className="max-h-80 overflow-auto border-t bg-muted/30 p-3 text-[11px] leading-relaxed">
          <code>{content}</code>
        </pre>
      )}
    </div>
  );
}

export function PendingChangesReview({ pending, repoUrl, busy, onApprove }: PendingChangesReviewProps) {
  const [branchName, setBranchName] = useState(pending.branchName);
  const [baseBranch, setBaseBranch] = useState(pending.baseBranch);
  const [prTitle, setPrTitle] = useState(pending.prTitle);
  const [reviewers, setReviewers] = useState("");
  const [mergeAfter, setMergeAfter] = useState(false);
  const [comment, setComment] = useState("");

  return (
    <div className="mt-4 space-y-4 rounded-lg border border-amber-200 bg-amber-50/50 p-4">
      <div>
        <h3 className="text-sm font-semibold text-amber-950">Proposed code changes</h3>
        <p className="mt-1 text-xs text-amber-900/80">
          Nothing has been pushed to GitHub yet. Review the files below, then create the branch and pull request when
          you are ready.
        </p>
        {pending.summary && <p className="mt-2 text-xs text-muted-foreground">{pending.summary}</p>}
        {repoUrl && (
          <p className="mt-1 truncate text-xs text-muted-foreground">
            Repository: <span className="font-mono">{repoUrl}</span>
          </p>
        )}
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">
          {pending.files.length} file{pending.files.length === 1 ? "" : "s"} changed
        </p>
        {pending.files.map((file) => (
          <FilePreview key={file.path} path={file.path} content={file.content} />
        ))}
      </div>

      <div className="grid gap-3 border-t border-amber-200/80 pt-4 sm:grid-cols-2">
        <label className="block text-xs">
          <span className="font-medium">Feature branch</span>
          <input
            className="mt-1 w-full rounded-md border bg-background px-2 py-1.5 font-mono text-xs"
            value={branchName}
            onChange={(e) => setBranchName(e.target.value)}
            disabled={busy}
          />
        </label>
        <label className="block text-xs">
          <span className="font-medium">Target branch (PR base)</span>
          <input
            className="mt-1 w-full rounded-md border bg-background px-2 py-1.5 font-mono text-xs"
            value={baseBranch}
            onChange={(e) => setBaseBranch(e.target.value)}
            disabled={busy}
          />
        </label>
        <label className="block text-xs sm:col-span-2">
          <span className="font-medium">Pull request title</span>
          <input
            className="mt-1 w-full rounded-md border bg-background px-2 py-1.5 text-xs"
            value={prTitle}
            onChange={(e) => setPrTitle(e.target.value)}
            disabled={busy}
          />
        </label>
        <label className="block text-xs sm:col-span-2">
          <span className="font-medium">Request reviewers (GitHub usernames, comma-separated)</span>
          <input
            className="mt-1 w-full rounded-md border bg-background px-2 py-1.5 text-xs"
            placeholder="e.g. teammate1, teammate2"
            value={reviewers}
            onChange={(e) => setReviewers(e.target.value)}
            disabled={busy}
          />
        </label>
        <label className="flex items-center gap-2 text-xs sm:col-span-2">
          <input
            type="checkbox"
            checked={mergeAfter}
            onChange={(e) => setMergeAfter(e.target.checked)}
            disabled={busy}
          />
          Merge pull request immediately after creation
        </label>
        <label className="block text-xs sm:col-span-2">
          <span className="font-medium">Comment (optional)</span>
          <textarea
            className="mt-1 w-full rounded-md border bg-background px-2 py-1.5 text-xs"
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={busy}
          />
        </label>
      </div>

      <button
        type="button"
        disabled={busy || !branchName.trim() || !baseBranch.trim() || !prTitle.trim()}
        onClick={() =>
          onApprove({
            branchName: branchName.trim(),
            baseBranch: baseBranch.trim(),
            prTitle: prTitle.trim(),
            reviewers: reviewers
              .split(",")
              .map((r) => r.trim())
              .filter(Boolean),
            merge: mergeAfter,
            comment: comment.trim() || undefined,
          })
        }
        className={cn(
          "rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground",
          busy && "opacity-70"
        )}
      >
        {busy ? "Creating PR & pushing…" : "Create PR & push"}
      </button>
    </div>
  );
}
