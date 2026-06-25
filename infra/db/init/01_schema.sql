-- AI Development Automation Platform — initial schema
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enums
CREATE TYPE company_status AS ENUM ('active', 'suspended', 'trial');
CREATE TYPE member_role AS ENUM ('admin', 'member', 'viewer');
CREATE TYPE project_status AS ENUM ('draft', 'active', 'paused', 'completed', 'failed', 'archived');
CREATE TYPE pipeline_status AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');
CREATE TYPE step_status AS ENUM ('pending', 'running', 'completed', 'failed', 'skipped', 'needs_manual_review');
CREATE TYPE integration_type AS ENUM (
  'github', 'gitlab', 'azure_devops', 'jira', 'notion', 'linear',
  'slack', 'teams', 'email'
);
CREATE TYPE audit_action AS ENUM (
  'create', 'update', 'delete', 'login', 'invite', 'suspend',
  'pipeline_start', 'pipeline_complete'
);

-- Platform: users & plans
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    is_super_admin  BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE plans (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                     VARCHAR(100) NOT NULL UNIQUE,
    max_projects             INTEGER NOT NULL DEFAULT 5,
    max_parallel_pipelines   INTEGER NOT NULL DEFAULT 1,
    monthly_token_budget_usd NUMERIC(12, 4) NOT NULL DEFAULT 100.0000,
    is_active                BOOLEAN NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tenancy: companies
CREATE TABLE companies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) NOT NULL UNIQUE,
    status      company_status NOT NULL DEFAULT 'trial',
    plan_id     UUID NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE company_limits (
    company_id               UUID PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    max_projects             INTEGER,
    max_parallel_pipelines   INTEGER,
    monthly_token_budget_usd NUMERIC(12, 4),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE company_members (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        member_role NOT NULL DEFAULT 'member',
    invited_at  TIMESTAMPTZ,
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, user_id)
);

CREATE TABLE company_settings (
    company_id                      UUID PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    default_notification_channels   TEXT[] DEFAULT '{}',
    timezone                        VARCHAR(64) DEFAULT 'UTC',
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE integration_configs (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id           UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    integration_type     integration_type NOT NULL,
    display_name         VARCHAR(255),
    encrypted_config_ref VARCHAR(512) NOT NULL,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    last_tested_at       TIMESTAMPTZ,
    last_test_status     BOOLEAN,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, integration_type, display_name)
);

-- AI Dev: projects & pipelines
CREATE TABLE projects (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id               UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_by               UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name                     VARCHAR(255) NOT NULL,
    description              TEXT,
    status                   project_status NOT NULL DEFAULT 'draft',
    frontend_stack           VARCHAR(64),
    backend_stack            VARCHAR(64),
    db_type                  VARCHAR(64),
    vcs_provider             VARCHAR(64),
    pm_tool                  VARCHAR(64),
    notification_channels    TEXT[] DEFAULT '{}',
    monthly_token_budget_usd NUMERIC(12, 4),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, name)
);

CREATE TABLE pipeline_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status              pipeline_status NOT NULL DEFAULT 'pending',
    current_step        VARCHAR(64),
    langgraph_thread_id VARCHAR(255),
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE pipeline_steps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_name       VARCHAR(64) NOT NULL,
    step_order      SMALLINT NOT NULL,
    status          step_status NOT NULL DEFAULT 'pending',
    retry_count     SMALLINT NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (pipeline_run_id, step_name)
);

CREATE TABLE agent_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_step_id UUID NOT NULL REFERENCES pipeline_steps(id) ON DELETE CASCADE,
    agent_name       VARCHAR(64) NOT NULL,
    input_json       JSONB,
    output_json      JSONB,
    input_tokens     INTEGER NOT NULL DEFAULT 0,
    output_tokens    INTEGER NOT NULL DEFAULT 0,
    cost_usd         NUMERIC(12, 6) NOT NULL DEFAULT 0,
    model_name       VARCHAR(128),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Artifacts
CREATE TABLE prd_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    content_json    JSONB NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE architecture_docs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    content_json    JSONB NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE external_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    external_id     VARCHAR(255) NOT NULL,
    external_url    VARCHAR(512),
    title           VARCHAR(512) NOT NULL,
    status          VARCHAR(64),
    pm_tool         VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, external_id, pm_tool)
);

CREATE TABLE pull_requests (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    external_task_id UUID REFERENCES external_tasks(id) ON DELETE SET NULL,
    url              VARCHAR(512) NOT NULL,
    title            VARCHAR(512),
    status           VARCHAR(64),
    branch_name      VARCHAR(255),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE deployments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    environment     VARCHAR(64) NOT NULL DEFAULT 'staging',
    url             VARCHAR(512),
    status          VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE validation_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    passed          BOOLEAN NOT NULL,
    report_json     JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit & usage
CREATE TABLE audit_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id    UUID REFERENCES companies(id) ON DELETE SET NULL,
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    action        audit_action NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id   UUID,
    metadata_json JSONB,
    ip_address    INET,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE usage_ledger (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    project_id      UUID REFERENCES projects(id) ON DELETE SET NULL,
    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    event_type      VARCHAR(64) NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_company_members_user ON company_members(user_id);
CREATE INDEX idx_company_members_company ON company_members(company_id);
CREATE INDEX idx_projects_company_status ON projects(company_id, status);
CREATE INDEX idx_pipeline_runs_project ON pipeline_runs(project_id, status);
CREATE INDEX idx_pipeline_steps_run ON pipeline_steps(pipeline_run_id);
CREATE INDEX idx_agent_logs_step ON agent_logs(pipeline_step_id);
CREATE INDEX idx_audit_events_company ON audit_events(company_id, created_at DESC);
CREATE INDEX idx_usage_ledger_company ON usage_ledger(company_id, created_at DESC);
CREATE INDEX idx_integration_configs_company ON integration_configs(company_id);

-- Seed data
INSERT INTO plans (name, max_projects, max_parallel_pipelines, monthly_token_budget_usd)
VALUES
  ('Starter', 3, 1, 50.0000),
  ('Professional', 10, 3, 250.0000),
  ('Enterprise', 50, 10, 1000.0000);
