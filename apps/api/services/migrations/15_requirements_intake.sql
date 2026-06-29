-- Copied for API container bootstrap (see infra/db/init/15_requirements_intake.sql)
CREATE TABLE IF NOT EXISTS jira_ticket_intakes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id          UUID REFERENCES projects(id) ON DELETE SET NULL,
    jira_issue_key      VARCHAR(32) NOT NULL,
    jira_issue_id       VARCHAR(64),
    jira_summary        TEXT,
    jira_status         VARCHAR(64),
    jira_url            TEXT,
    status              VARCHAR(48) NOT NULL DEFAULT 'synced',
    repo_url            TEXT,
    base_branch         VARCHAR(128),
    feature_branch      VARCHAR(256),
    implementation_plan_json JSONB,
    pipeline_run_id     UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    locked_at           TIMESTAMPTZ,
    locked_by_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, jira_issue_key)
);
CREATE INDEX IF NOT EXISTS idx_jira_intakes_workspace ON jira_ticket_intakes(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_jira_intakes_user ON jira_ticket_intakes(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS clarification_questions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intake_id           UUID NOT NULL REFERENCES jira_ticket_intakes(id) ON DELETE CASCADE,
    category            VARCHAR(32) NOT NULL,
    question_text       TEXT NOT NULL,
    options_json        JSONB NOT NULL DEFAULT '[]',
    allow_custom_answer BOOLEAN NOT NULL DEFAULT TRUE,
    is_required         BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order          SMALLINT NOT NULL DEFAULT 0,
    rationale           TEXT,
    status              VARCHAR(24) NOT NULL DEFAULT 'open',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_clarification_questions_intake ON clarification_questions(intake_id, category, sort_order);
CREATE TABLE IF NOT EXISTS clarification_answers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id         UUID NOT NULL REFERENCES clarification_questions(id) ON DELETE CASCADE UNIQUE,
    selected_option     TEXT,
    custom_answer       TEXT,
    answered_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS requirement_documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intake_id           UUID NOT NULL REFERENCES jira_ticket_intakes(id) ON DELETE CASCADE,
    doc_type            VARCHAR(32) NOT NULL,
    title               VARCHAR(512) NOT NULL,
    content_json        JSONB NOT NULL DEFAULT '{}',
    version             SMALLINT NOT NULL DEFAULT 1,
    status              VARCHAR(24) NOT NULL DEFAULT 'draft',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (intake_id, doc_type)
);
CREATE TABLE IF NOT EXISTS requirement_conversations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intake_id           UUID NOT NULL REFERENCES jira_ticket_intakes(id) ON DELETE CASCADE,
    document_id         UUID REFERENCES requirement_documents(id) ON DELETE SET NULL,
    author_type         VARCHAR(16) NOT NULL,
    author_user_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    message             TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_requirement_conversations_intake ON requirement_conversations(intake_id, created_at);
CREATE TABLE IF NOT EXISTS intake_approvals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intake_id           UUID NOT NULL REFERENCES jira_ticket_intakes(id) ON DELETE CASCADE,
    approval_type       VARCHAR(32) NOT NULL,
    approver_user_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    status              VARCHAR(24) NOT NULL DEFAULT 'pending',
    comment             TEXT,
    decided_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_intake_approvals_intake ON intake_approvals(intake_id, approval_type);
CREATE TABLE IF NOT EXISTS workspace_notifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type   VARCHAR(48) NOT NULL,
    title               VARCHAR(512) NOT NULL,
    body                TEXT,
    link_path           VARCHAR(512),
    intake_id           UUID REFERENCES jira_ticket_intakes(id) ON DELETE CASCADE,
    is_read             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_workspace_notifications_user ON workspace_notifications(user_id, is_read, created_at DESC);
