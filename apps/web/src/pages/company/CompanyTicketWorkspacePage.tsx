import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { CheckCircle2, Loader2, MessageSquare, FileText, Lock, Play, ShieldCheck } from "lucide-react";
import { AgentRunPicker } from "@/components/company/AgentRunPicker";
import { PipelineRunTracker } from "@/components/company/PipelineRunTracker";
import { PendingChangesReview } from "@/components/company/PendingChangesReview";
import { intakeApi, type ApprovePrPayload, type ClarificationQuestion } from "@/services/intakeApi";
import { companyApi } from "@/services/companyApi";
import { getApiErrorMessage } from "@/services/authApi";
import { defaultRunSelection, selectedAgentKeys } from "@/lib/agentRunUtils";
import { POLL_INTAKE_MS, shouldPollIntake } from "@/lib/polling";
import { cn } from "@/lib/utils";

const CATEGORIES = ["repo", "api", "db", "auth", "validation", "exception", "scope", "general"] as const;
const DOC_TYPES = ["overview", "db", "api", "auth", "validation", "exception"] as const;

const DOC_LABELS: Record<string, string> = {
  overview: "Overview",
  db: "Database",
  api: "APIs",
  auth: "Authentication",
  validation: "Validations",
  exception: "Exceptions",
};

type Step = "questions" | "documents" | "plan" | "implement";

function QuestionCard({
  question,
  onAnswer,
  busy,
}: {
  question: ClarificationQuestion;
  onAnswer: (selectedOption?: string, customAnswer?: string) => Promise<void>;
  busy: boolean;
}) {
  const savedSelected = question.answer?.selectedOption ?? "";
  const savedCustom = question.answer?.customAnswer ?? "";
  const [custom, setCustom] = useState(savedCustom);
  const [selected, setSelected] = useState(savedSelected);
  const [saved, setSaved] = useState(question.status === "answered");

  useEffect(() => {
    setCustom(savedCustom);
    setSelected(savedSelected);
    setSaved(question.status === "answered");
  }, [question.id, savedCustom, savedSelected, question.status]);

  const dirty =
    selected !== savedSelected || custom.trim() !== savedCustom.trim();

  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="rounded bg-muted px-2 py-0.5 text-[10px] font-semibold uppercase">{question.category}</span>
          <p className="mt-2 text-sm font-medium">{question.questionText}</p>
          {question.rationale && <p className="mt-1 text-xs text-muted-foreground">{question.rationale}</p>}
        </div>
        {saved && !dirty && <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />}
      </div>
      <div className="mt-3 space-y-2">
        {question.options.map((opt) => (
          <label key={opt} className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="radio"
              name={question.id}
              checked={selected === opt}
              onChange={() => {
                setSelected(opt);
                setSaved(false);
              }}
              disabled={busy}
            />
            {opt}
          </label>
        ))}
        {question.allowCustomAnswer && (
          <textarea
            className="mt-2 w-full rounded-md border bg-background px-3 py-2 text-sm"
            rows={2}
            placeholder="Or type your own answer…"
            value={custom}
            onChange={(e) => {
              setCustom(e.target.value);
              setSaved(false);
            }}
            disabled={busy}
          />
        )}
        {dirty ? (
          <button
            type="button"
            disabled={busy || (!selected && !custom.trim())}
            onClick={async () => {
              await onAnswer(selected || undefined, custom.trim() || undefined);
              setSaved(true);
            }}
            className="mt-2 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
          >
            {busy ? "Saving…" : "Save answer"}
          </button>
        ) : saved ? (
          <p className="mt-2 text-xs font-medium text-emerald-600">Saved</p>
        ) : null}
      </div>
    </div>
  );
}

export function CompanyTicketWorkspacePage() {
  const { issueKey } = useParams<{ issueKey: string }>();
  const queryClient = useQueryClient();
  const [activeCategory, setActiveCategory] = useState<string>("repo");
  const [activeDoc, setActiveDoc] = useState<string>("overview");
  const [viewStep, setViewStep] = useState<Step | null>(null);
  const [chatMessage, setChatMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [savingQuestionId, setSavingQuestionId] = useState<string | null>(null);
  const [selectedAgents, setSelectedAgents] = useState<Record<string, boolean>>({});

  const intakeQuery = useQuery({
    queryKey: ["intake", issueKey],
    queryFn: () => intakeApi.getByKey(issueKey!),
    enabled: !!issueKey,
    staleTime: 10_000,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return shouldPollIntake(s) ? POLL_INTAKE_MS : false;
    },
  });

  const intake = intakeQuery.data;

  const projectAgentsQuery = useQuery({
    queryKey: ["project-agents", intake?.projectId],
    queryFn: () => companyApi.getProjectAgents(intake!.projectId!),
    enabled: !!intake?.projectId,
  });

  useEffect(() => {
    const agents = projectAgentsQuery.data;
    if (!agents?.length) return;
    setSelectedAgents((prev) => {
      if (Object.values(prev).some(Boolean)) return prev;
      return defaultRunSelection(agents);
    });
  }, [projectAgentsQuery.data]);

  const step: Step = useMemo(() => {
    if (!intake) return "questions";
    if (["synced", "analyzing", "awaiting_answers"].includes(intake.status)) return "questions";
    if (["drafting_specs", "awaiting_review", "locked"].includes(intake.status)) return "documents";
    if (["awaiting_plan_approval", "approved"].includes(intake.status)) return "plan";
    return "implement";
  }, [intake]);

  const currentStep = viewStep ?? step;

  useEffect(() => {
    setViewStep(null);
  }, [intake?.status]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["intake", issueKey] });
    queryClient.invalidateQueries({ queryKey: ["jira-portal"] });
  };

  const invalidateWithNotifications = () => {
    invalidate();
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
    queryClient.invalidateQueries({ queryKey: ["notifications-unread"] });
  };

  const analyze = useMutation({
    mutationFn: () => intakeApi.analyze(intake!.id),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (e: unknown) => setError(getApiErrorMessage(e, "Analysis failed")),
  });

  const submitAnswers = useMutation({
    mutationFn: () => intakeApi.submitAnswers(intake!.id),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (e: unknown) => setError(getApiErrorMessage(e, "Submit failed")),
  });

  const lock = useMutation({
    mutationFn: () => intakeApi.lock(intake!.id),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (e: unknown) => setError(getApiErrorMessage(e, "Lock failed")),
  });

  const rejectPlan = useMutation({
    mutationFn: () => intakeApi.rejectPlan(intake!.id),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (e: unknown) => setError(getApiErrorMessage(e, "Revise failed")),
  });

  const approvePlan = useMutation({
    mutationFn: () => intakeApi.approvePlan(intake!.id),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (e: unknown) => setError(getApiErrorMessage(e, "Approve failed")),
  });

  const startImpl = useMutation({
    mutationFn: () => {
      const keys = selectedAgentKeys(selectedAgents);
      return intakeApi.startImplementation(intake!.id, keys.length > 0 ? keys : undefined);
    },
    onSuccess: () => {
      setError(null);
      invalidateWithNotifications();
      if (intake?.projectId) {
        queryClient.invalidateQueries({ queryKey: ["company-project-runs", intake.projectId] });
      }
    },
    onError: (e: unknown) => setError(getApiErrorMessage(e, "Start failed")),
  });

  const approvePr = useMutation({
    mutationFn: (payload: ApprovePrPayload) => intakeApi.approvePr(intake!.id, payload),
    onSuccess: () => { setError(null); invalidateWithNotifications(); },
    onError: (e: unknown) => setError(getApiErrorMessage(e, "PR approve failed")),
  });

  const recoverPending = useMutation({
    mutationFn: () => intakeApi.recoverPendingChanges(intake!.id),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (e: unknown) => setError(getApiErrorMessage(e, "Could not recover changes")),
  });

  const resetForReimplementation = useMutation({
    mutationFn: () => intakeApi.resetForReimplementation(intake!.id),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (e: unknown) => setError(getApiErrorMessage(e, "Reset failed")),
  });

  const sendChat = useMutation({
    mutationFn: () => intakeApi.postConversation(intake!.id, chatMessage),
    onSuccess: () => { setChatMessage(""); setError(null); invalidate(); },
    onError: (e: unknown) => setError(getApiErrorMessage(e, "Message failed")),
  });

  const questionsByCategory = useMemo(() => {
    const map: Record<string, ClarificationQuestion[]> = {};
    for (const q of intake?.questions ?? []) {
      (map[q.category] ??= []).push(q);
    }
    return map;
  }, [intake?.questions]);

  const activeQuestions = questionsByCategory[activeCategory] ?? [];
  const activeDocument = intake?.documents.find((d) => d.docType === activeDoc);

  if (intakeQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading ticket workspace…
      </div>
    );
  }

  if (!intake) {
    return (
      <p className="text-sm text-muted-foreground">
        Intake not found. <Link to="/workspace/jira" className="text-primary underline">Back to Jira Portal</Link>
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/workspace/jira" className="text-xs text-primary hover:underline">← Jira Portal</Link>
          <h1 className="mt-1 text-2xl font-semibold">
            {intake.jiraIssueKey}
            <span className="ml-2 text-base font-normal text-muted-foreground">{intake.jiraSummary}</span>
          </h1>
          <p className="mt-1 text-sm capitalize text-muted-foreground">Status: {intake.status.replace(/_/g, " ")}</p>
        </div>
        {intake.jiraUrl && (
          <a href={intake.jiraUrl} target="_blank" rel="noreferrer" className="text-sm text-primary underline">
            Open in Jira
          </a>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {(["questions", "documents", "plan", "implement"] as Step[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setViewStep(s)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium capitalize",
              currentStep === s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {s}
          </button>
        ))}
      </div>

      {intake.status === "awaiting_plan_approval" && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
          Review the implementation plan below, then click <strong>Confirm plan</strong> to proceed. After that, click{" "}
          <strong>Start implementation</strong> to run the agents.
        </div>
      )}
      {intake.status === "approved" && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          Plan confirmed. Choose agents below, then click <strong>Start implementation</strong>.
        </div>
      )}
      {intake.status === "implementation_failed" && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
          Implementation failed. Review the error below, then retry from the <strong>Plan</strong> or{" "}
          <strong>Implement</strong> tab.
        </div>
      )}
      {intake.status === "awaiting_pr_review" && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          Implementation finished. Review the proposed code changes below — nothing is pushed to GitHub until you click{" "}
          <strong>Create PR &amp; push</strong>.
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* QUESTIONS */}
      {currentStep === "questions" && intake.questions.length > 0 && (
        <section className="rounded-lg border bg-card p-6">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <MessageSquare className="h-4 w-4" /> Clarification questions
            </h2>
            <span className="text-xs text-muted-foreground">
              {intake.questionsAnswered}/{intake.questionsTotal} answered
            </span>
          </div>

          {intake.status === "synced" && (
            <button
              type="button"
              onClick={() => analyze.mutate()}
              disabled={analyze.isPending}
              className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              {analyze.isPending ? "Analyzing ticket…" : "Generate clarification questions"}
            </button>
          )}

          {intake.questions.length > 0 && (
            <>
              <div className="mt-4 flex flex-wrap gap-1 border-b pb-2">
                {CATEGORIES.filter((c) => (questionsByCategory[c]?.length ?? 0) > 0).map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setActiveCategory(cat)}
                    className={cn(
                      "rounded-md px-3 py-1 text-xs font-medium capitalize",
                      activeCategory === cat ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted"
                    )}
                  >
                    {cat} ({questionsByCategory[cat]?.length ?? 0})
                  </button>
                ))}
              </div>
              <div className="mt-4 space-y-3">
                {activeQuestions.map((q) => (
                  <QuestionCard
                    key={q.id}
                    question={q}
                    busy={savingQuestionId === q.id}
                    onAnswer={async (selectedOption, customAnswer) => {
                      setSavingQuestionId(q.id);
                      try {
                        await intakeApi.answerQuestion(intake.id, q.id, { selectedOption, customAnswer });
                        invalidate();
                      } finally {
                        setSavingQuestionId(null);
                      }
                    }}
                  />
                ))}
              </div>
              {intake.status === "awaiting_answers" && (
                <button
                  type="button"
                  onClick={() => submitAnswers.mutate()}
                  disabled={submitAnswers.isPending}
                  className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
                >
                  {submitAnswers.isPending ? "Generating specs…" : "Submit answers & generate specs"}
                </button>
              )}
            </>
          )}
        </section>
      )}

      {/* DOCUMENTS */}
      {currentStep === "documents" && intake.documents.length > 0 && (
        <section className="rounded-lg border bg-card p-6">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <FileText className="h-4 w-4" /> Requirement documents (separate per domain)
          </h2>
          <div className="mt-4 flex flex-wrap gap-1 border-b pb-2">
            {DOC_TYPES.filter((t) => intake.documents.some((d) => d.docType === t)).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setActiveDoc(t)}
                className={cn(
                  "rounded-md px-3 py-1 text-xs font-medium",
                  activeDoc === t ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted"
                )}
              >
                {DOC_LABELS[t] ?? t}
              </button>
            ))}
          </div>
          {activeDocument && (
            <div className="mt-4">
              <h3 className="text-sm font-medium">{activeDocument.title}</h3>
              <pre className="mt-2 max-h-96 overflow-auto rounded-md bg-muted p-4 text-xs">
                {JSON.stringify(activeDocument.contentJson, null, 2)}
              </pre>
            </div>
          )}
          {intake.status === "awaiting_review" && (
            <button
              type="button"
              onClick={() => lock.mutate()}
              disabled={lock.isPending}
              className="mt-4 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              <Lock className="h-4 w-4" />
              {lock.isPending ? "Locking…" : "Lock requirements & propose plan"}
            </button>
          )}
        </section>
      )}

      {/* DISCUSSION */}
      <section className="rounded-lg border bg-card p-6">
        <h2 className="text-sm font-semibold">Discussion</h2>
        <div className="mt-3 max-h-48 space-y-2 overflow-y-auto">
          {intake.conversations.map((c) => (
            <div
              key={c.id}
              className={cn(
                "rounded-md px-3 py-2 text-sm",
                c.authorType === "agent" ? "bg-muted" : "bg-primary/5"
              )}
            >
              <span className="text-xs font-semibold capitalize">{c.authorType}</span>
              <p className="mt-0.5">{c.message}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <input
            className="flex-1 rounded-md border px-3 py-2 text-sm"
            placeholder="Ask a follow-up or request a spec change…"
            value={chatMessage}
            onChange={(e) => setChatMessage(e.target.value)}
          />
          <button
            type="button"
            disabled={!chatMessage.trim() || sendChat.isPending}
            onClick={() => sendChat.mutate()}
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </section>

      {/* PLAN */}
      {(currentStep === "plan" || intake.implementationPlan) && intake.implementationPlan && (
        <section className="rounded-lg border bg-card p-6">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4" /> Implementation plan
          </h2>
          <pre className="mt-3 max-h-64 overflow-auto rounded-md bg-muted p-4 text-xs">
            {JSON.stringify(intake.implementationPlan, null, 2)}
          </pre>
          {intake.status === "awaiting_plan_approval" && (
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => approvePlan.mutate()}
                disabled={approvePlan.isPending}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              >
                {approvePlan.isPending ? "Confirming…" : "Confirm plan"}
              </button>
              <button
                type="button"
                onClick={() => rejectPlan.mutate()}
                disabled={rejectPlan.isPending}
                className="rounded-md border px-4 py-2 text-sm font-medium"
              >
                {rejectPlan.isPending ? "Revising…" : "Revise requirements"}
              </button>
            </div>
          )}
          {(intake.status === "approved" || intake.status === "implementation_failed") && (
            <div className="mt-4 space-y-4 border-t pt-4">
              {!intake.projectId ? (
                <p className="text-sm text-amber-700">
                  Link a platform project with a repository before starting implementation (set when you began this ticket in Jira Portal).
                </p>
              ) : (
                <>
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Agents for this run
                    </h3>
                    <div className="mt-2">
                      <AgentRunPicker
                        agents={projectAgentsQuery.data ?? []}
                        selected={selectedAgents}
                        onChange={setSelectedAgents}
                        disabled={startImpl.isPending || projectAgentsQuery.isLoading}
                        hint="Only implementation agents enabled on your project are shown (not planning agents)."
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => startImpl.mutate()}
                    disabled={
                      startImpl.isPending ||
                      selectedAgentKeys(selectedAgents).length === 0 ||
                      projectAgentsQuery.isLoading
                    }
                    className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                  >
                    <Play className="h-4 w-4" />
                    {startImpl.isPending
                      ? "Starting…"
                      : intake.status === "implementation_failed"
                        ? "Retry implementation"
                        : "Start implementation"}
                  </button>
                </>
              )}
            </div>
          )}
        </section>
      )}

      {/* IMPLEMENT / PR */}
      {(currentStep === "implement" ||
        intake.status === "implementing" ||
        intake.status === "implementation_failed" ||
        intake.status === "awaiting_pr_review" ||
        intake.status === "completed") && (
        <section className="rounded-lg border bg-card p-6">
          <h2 className="text-sm font-semibold">Implementation</h2>
          {intake.status === "implementing" && (
            <p className="mt-1 text-xs text-muted-foreground">Agents are running. Progress updates automatically.</p>
          )}
          {intake.status === "implementation_failed" && (
            <div className="mt-3 space-y-3 rounded-lg border border-red-200 bg-red-50/80 p-4 text-sm text-red-950">
              <p className="font-medium">The agent pipeline failed before code was ready for review.</p>
              <p className="text-xs text-red-800">
                Common causes: LLM timeout, invalid model output, or GitHub connection issues. Go to the{" "}
                <strong>Plan</strong> tab to retry with the same agents.
              </p>
            </div>
          )}
          {intake.pipelineRunId && intake.projectId ? (
            <div className="mt-4">
              <PipelineRunTracker
                projectId={intake.projectId}
                runId={intake.pipelineRunId}
                compact
                enablePolling={intake.status === "implementing"}
                intakeQueryKey={["intake", issueKey]}
              />
              <Link
                to={`/workspace/projects/${intake.projectId}`}
                className="mt-3 inline-block text-xs text-primary underline"
              >
                Open full pipeline view in project
              </Link>
            </div>
          ) : intake.projectId ? (
            <Link
              to={`/workspace/projects/${intake.projectId}`}
              className="mt-2 inline-block text-sm text-primary underline"
            >
              View project pipeline
            </Link>
          ) : null}
          {intake.status === "awaiting_pr_review" && intake.pendingChanges && (
            <PendingChangesReview
              pending={intake.pendingChanges}
              repoUrl={intake.repoUrl}
              busy={approvePr.isPending}
              onApprove={(payload) => approvePr.mutate(payload)}
            />
          )}
          {intake.status === "awaiting_pr_review" && !intake.pendingChanges && (
            <div className="mt-4 space-y-3 rounded-lg border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-950">
              <p>
                No local copy of the file changes was saved for this run (it was created before the review fix). We can
                try to recover the files from GitHub using the previous pull request, or you can re-run implementation.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => recoverPending.mutate()}
                  disabled={recoverPending.isPending || resetForReimplementation.isPending}
                  className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                >
                  {recoverPending.isPending ? "Recovering…" : "Recover changes from GitHub"}
                </button>
                <button
                  type="button"
                  onClick={() => resetForReimplementation.mutate()}
                  disabled={recoverPending.isPending || resetForReimplementation.isPending}
                  className="rounded-md border bg-background px-3 py-1.5 text-xs font-medium"
                >
                  {resetForReimplementation.isPending ? "Resetting…" : "Re-run implementation"}
                </button>
              </div>
            </div>
          )}
          {intake.status === "completed" && (
            <div className="mt-2 space-y-1 text-sm text-emerald-600">
              <p>Ticket workflow completed.</p>
              {intake.prUrl && (
                <a href={intake.prUrl} target="_blank" rel="noreferrer" className="text-primary underline">
                  View pull request on GitHub
                </a>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
