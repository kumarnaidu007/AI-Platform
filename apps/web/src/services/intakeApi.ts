import { api } from "@/services/authApi";

export interface PortalIssue {
  id: string | null;
  key: string | null;
  summary: string | null;
  description: string | null;
  issueType: string | null;
  status: string | null;
  priority: string | null;
  assignee: string | null;
  reporter: string | null;
  projectKey: string | null;
  projectName: string | null;
  url: string | null;
  intakeId: string | null;
  intakeStatus: string | null;
}

export interface ClarificationAnswer {
  id: string;
  selectedOption: string | null;
  customAnswer: string | null;
  answeredByUserId: string;
  createdAt: string;
}

export interface ClarificationQuestion {
  id: string;
  category: string;
  questionText: string;
  options: string[];
  allowCustomAnswer: boolean;
  isRequired: boolean;
  sortOrder: number;
  rationale: string | null;
  status: string;
  answer: ClarificationAnswer | null;
}

export interface RequirementDocument {
  id: string;
  docType: string;
  title: string;
  contentJson: Record<string, unknown>;
  version: number;
  status: string;
  updatedAt: string;
}

export interface ConversationMessage {
  id: string;
  authorType: string;
  authorUserId: string | null;
  message: string;
  documentId: string | null;
  createdAt: string;
}

export interface IntakeApproval {
  id: string;
  approvalType: string;
  status: string;
  approverUserId: string | null;
  comment: string | null;
  decidedAt: string | null;
}

export interface PendingFile {
  path: string;
  content: string;
  message: string | null;
}

export interface PendingChanges {
  branchName: string;
  baseBranch: string;
  prTitle: string;
  prBody: string | null;
  summary: string | null;
  files: PendingFile[];
}

export interface ApprovePrPayload {
  branchName?: string;
  baseBranch?: string;
  prTitle?: string;
  reviewers?: string[];
  merge?: boolean;
  comment?: string;
}

export interface IntakeDetail {
  id: string;
  jiraIssueKey: string;
  jiraSummary: string | null;
  jiraStatus: string | null;
  jiraUrl: string | null;
  status: string;
  projectId: string | null;
  repoUrl: string | null;
  baseBranch: string | null;
  featureBranch: string | null;
  prUrl: string | null;
  pipelineRunId: string | null;
  lockedAt: string | null;
  createdAt: string;
  updatedAt: string;
  questionsTotal: number;
  questionsAnswered: number;
  questions: ClarificationQuestion[];
  documents: RequirementDocument[];
  conversations: ConversationMessage[];
  approvals: IntakeApproval[];
  implementationPlan: Record<string, unknown> | null;
  pendingChanges: PendingChanges | null;
}

function mapPortalIssue(row: Record<string, unknown>): PortalIssue {
  return {
    id: row.id != null ? String(row.id) : null,
    key: row.key != null ? String(row.key) : null,
    summary: row.summary != null ? String(row.summary) : null,
    description: row.description != null ? String(row.description) : null,
    issueType: row.issue_type != null ? String(row.issue_type) : null,
    status: row.status != null ? String(row.status) : null,
    priority: row.priority != null ? String(row.priority) : null,
    assignee: row.assignee != null ? String(row.assignee) : null,
    reporter: row.reporter != null ? String(row.reporter) : null,
    projectKey: row.project_key != null ? String(row.project_key) : null,
    projectName: row.project_name != null ? String(row.project_name) : null,
    url: row.url != null ? String(row.url) : null,
    intakeId: row.intake_id != null ? String(row.intake_id) : null,
    intakeStatus: row.intake_status != null ? String(row.intake_status) : null,
  };
}

function mapQuestion(row: Record<string, unknown>): ClarificationQuestion {
  const ans = row.answer as Record<string, unknown> | null | undefined;
  return {
    id: String(row.id),
    category: String(row.category),
    questionText: String(row.question_text),
    options: (row.options as string[]) ?? [],
    allowCustomAnswer: Boolean(row.allow_custom_answer),
    isRequired: Boolean(row.is_required),
    sortOrder: Number(row.sort_order),
    rationale: row.rationale != null ? String(row.rationale) : null,
    status: String(row.status),
    answer: ans
      ? {
          id: String(ans.id),
          selectedOption: ans.selected_option != null ? String(ans.selected_option) : null,
          customAnswer: ans.custom_answer != null ? String(ans.custom_answer) : null,
          answeredByUserId: String(ans.answered_by_user_id),
          createdAt: String(ans.created_at),
        }
      : null,
  };
}

function mapDocument(row: Record<string, unknown>): RequirementDocument {
  return {
    id: String(row.id),
    docType: String(row.doc_type),
    title: String(row.title),
    contentJson: (row.content_json as Record<string, unknown>) ?? {},
    version: Number(row.version),
    status: String(row.status),
    updatedAt: String(row.updated_at),
  };
}

function mapIntake(row: Record<string, unknown>): IntakeDetail {
  return {
    id: String(row.id),
    jiraIssueKey: String(row.jira_issue_key),
    jiraSummary: row.jira_summary != null ? String(row.jira_summary) : null,
    jiraStatus: row.jira_status != null ? String(row.jira_status) : null,
    jiraUrl: row.jira_url != null ? String(row.jira_url) : null,
    status: String(row.status),
    projectId: row.project_id != null ? String(row.project_id) : null,
    repoUrl: row.repo_url != null ? String(row.repo_url) : null,
    baseBranch: row.base_branch != null ? String(row.base_branch) : null,
    featureBranch: row.feature_branch != null ? String(row.feature_branch) : null,
    prUrl: row.pr_url != null ? String(row.pr_url) : null,
    pipelineRunId: row.pipeline_run_id != null ? String(row.pipeline_run_id) : null,
    lockedAt: row.locked_at != null ? String(row.locked_at) : null,
    createdAt: String(row.created_at),
    updatedAt: String(row.updated_at),
    questionsTotal: Number(row.questions_total ?? 0),
    questionsAnswered: Number(row.questions_answered ?? 0),
    questions: ((row.questions as Record<string, unknown>[]) ?? []).map(mapQuestion),
    documents: ((row.documents as Record<string, unknown>[]) ?? []).map(mapDocument),
    conversations: ((row.conversations as Record<string, unknown>[]) ?? []).map((c) => ({
      id: String(c.id),
      authorType: String(c.author_type),
      authorUserId: c.author_user_id != null ? String(c.author_user_id) : null,
      message: String(c.message),
      documentId: c.document_id != null ? String(c.document_id) : null,
      createdAt: String(c.created_at),
    })),
    approvals: ((row.approvals as Record<string, unknown>[]) ?? []).map((a) => ({
      id: String(a.id),
      approvalType: String(a.approval_type),
      status: String(a.status),
      approverUserId: a.approver_user_id != null ? String(a.approver_user_id) : null,
      comment: a.comment != null ? String(a.comment) : null,
      decidedAt: a.decided_at != null ? String(a.decided_at) : null,
    })),
    implementationPlan: (row.implementation_plan as Record<string, unknown>) ?? null,
    pendingChanges: mapPendingChanges(row.pending_changes),
  };
}

function mapPendingChanges(raw: unknown): PendingChanges | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const files = ((row.files as Record<string, unknown>[]) ?? [])
    .map((f) => ({
      path: String(f.path ?? ""),
      content: String(f.content ?? ""),
      message: f.message != null ? String(f.message) : null,
    }))
    .filter((f) => f.path);
  if (!files.length) return null;
  return {
    branchName: String(row.branch_name ?? "feature/ai-changes"),
    baseBranch: String(row.base_branch ?? "main"),
    prTitle: String(row.pr_title ?? "feat: AI implementation"),
    prBody: row.pr_body != null ? String(row.pr_body) : null,
    summary: row.summary != null ? String(row.summary) : null,
    files,
  };
}

export const intakeApi = {
  getPortal: async (projectKey?: string) => {
    const { data } = await api.get<Record<string, unknown>[]>("/api/workspace/jira/portal", {
      params: projectKey ? { project_key: projectKey } : undefined,
    });
    return data.map(mapPortalIssue);
  },

  createIntake: async (payload: { jiraIssueKey: string; projectId?: string }) => {
    const { data } = await api.post<Record<string, unknown>>("/api/workspace/intakes", {
      jira_issue_key: payload.jiraIssueKey,
      project_id: payload.projectId,
    });
    return mapIntake(data);
  },

  getByKey: async (issueKey: string) => {
    const { data } = await api.get<Record<string, unknown>>(`/api/workspace/intakes/by-key/${issueKey}`);
    return mapIntake(data);
  },

  get: async (intakeId: string) => {
    const { data } = await api.get<Record<string, unknown>>(`/api/workspace/intakes/${intakeId}`);
    return mapIntake(data);
  },

  analyze: async (intakeId: string) => {
    const { data } = await api.post<Record<string, unknown>>(`/api/workspace/intakes/${intakeId}/analyze`);
    return mapIntake(data);
  },

  answerQuestion: async (
    intakeId: string,
    questionId: string,
    payload: { selectedOption?: string; customAnswer?: string }
  ) => {
    const { data } = await api.post<Record<string, unknown>>(
      `/api/workspace/intakes/${intakeId}/questions/${questionId}/answer`,
      {
        selected_option: payload.selectedOption,
        custom_answer: payload.customAnswer,
      }
    );
    return mapIntake(data);
  },

  submitAnswers: async (intakeId: string) => {
    const { data } = await api.post<Record<string, unknown>>(`/api/workspace/intakes/${intakeId}/submit-answers`);
    return mapIntake(data);
  },

  updateDocument: async (intakeId: string, docType: string, contentJson: Record<string, unknown>) => {
    const { data } = await api.patch<Record<string, unknown>>(
      `/api/workspace/intakes/${intakeId}/documents/${docType}`,
      { content_json: contentJson }
    );
    return mapIntake(data);
  },

  postConversation: async (intakeId: string, message: string, documentId?: string) => {
    const { data } = await api.post<Record<string, unknown>>(`/api/workspace/intakes/${intakeId}/conversations`, {
      message,
      document_id: documentId,
    });
    return mapIntake(data);
  },

  lock: async (intakeId: string) => {
    const { data } = await api.post<Record<string, unknown>>(`/api/workspace/intakes/${intakeId}/lock`);
    return mapIntake(data);
  },

  approvePlan: async (intakeId: string, comment?: string) => {
    const { data } = await api.post<Record<string, unknown>>(`/api/workspace/intakes/${intakeId}/approve-plan`, {
      comment,
    });
    return mapIntake(data);
  },

  rejectPlan: async (intakeId: string, comment?: string) => {
    const { data } = await api.post<Record<string, unknown>>(`/api/workspace/intakes/${intakeId}/reject-plan`, {
      comment,
    });
    return mapIntake(data);
  },

  startImplementation: async (intakeId: string, agentKeys?: string[]) => {
    const { data } = await api.post<Record<string, unknown>>(
      `/api/workspace/intakes/${intakeId}/start-implementation`,
      { agent_keys: agentKeys }
    );
    return mapIntake(data);
  },

  approvePr: async (intakeId: string, payload: ApprovePrPayload = {}) => {
    const { data } = await api.post<Record<string, unknown>>(`/api/workspace/intakes/${intakeId}/approve-pr`, {
      comment: payload.comment,
      branch_name: payload.branchName,
      base_branch: payload.baseBranch,
      pr_title: payload.prTitle,
      reviewers: payload.reviewers,
      merge: payload.merge ?? false,
    });
    return mapIntake(data);
  },

  recoverPendingChanges: async (intakeId: string) => {
    const { data } = await api.post<Record<string, unknown>>(
      `/api/workspace/intakes/${intakeId}/recover-pending-changes`
    );
    return mapIntake(data);
  },

  resetForReimplementation: async (intakeId: string) => {
    const { data } = await api.post<Record<string, unknown>>(
      `/api/workspace/intakes/${intakeId}/reset-for-reimplementation`
    );
    return mapIntake(data);
  },
};
