-- Platform AI agents catalog + tenant / user / project access

CREATE TYPE agent_category AS ENUM ('planning', 'development', 'quality', 'delivery');

CREATE TABLE platform_agents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_key           VARCHAR(64) NOT NULL UNIQUE,
    name                VARCHAR(128) NOT NULL,
    description         TEXT,
    category            agent_category NOT NULL,
    default_step_order  SMALLINT NOT NULL DEFAULT 1,
    is_enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json       JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE plan_platform_agents (
    plan_id             UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    platform_agent_id   UUID NOT NULL REFERENCES platform_agents(id) ON DELETE CASCADE,
    PRIMARY KEY (plan_id, platform_agent_id)
);

CREATE TABLE workspace_platform_agents (
    workspace_id        UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    platform_agent_id   UUID NOT NULL REFERENCES platform_agents(id) ON DELETE CASCADE,
    is_enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    granted_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, platform_agent_id)
);

CREATE TABLE member_agent_access (
    workspace_id        UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform_agent_id   UUID NOT NULL REFERENCES platform_agents(id) ON DELETE CASCADE,
    is_enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    granted_by_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
    granted_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id, platform_agent_id)
);

CREATE TABLE project_agents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    platform_agent_id   UUID NOT NULL REFERENCES platform_agents(id) ON DELETE CASCADE,
    is_enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    step_order          SMALLINT NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, platform_agent_id)
);

CREATE INDEX idx_platform_agents_category ON platform_agents(category, default_step_order);
CREATE INDEX idx_platform_agents_enabled ON platform_agents(is_enabled);
CREATE INDEX idx_workspace_platform_agents_workspace ON workspace_platform_agents(workspace_id);
CREATE INDEX idx_member_agent_access_workspace_user ON member_agent_access(workspace_id, user_id);
CREATE INDEX idx_project_agents_project ON project_agents(project_id, step_order);

-- Seed: 10 pipeline agents
INSERT INTO platform_agents (agent_key, name, description, category, default_step_order, metadata_json) VALUES
  ('requirements', 'Requirements Agent', 'Reads PDF, Notion, or text inputs and produces a structured PRD.', 'planning', 1,
   '{"artifact":"prd_documents","group":"Planning"}'),
  ('architecture', 'Architecture Agent', 'Generates stack-specific folder structure, API contracts, and database schema.', 'planning', 2,
   '{"artifact":"architecture_docs","group":"Planning"}'),
  ('task_planner', 'Task Planner Agent', 'Breaks work into tasks in Jira, Linear, or Azure Boards.', 'planning', 3,
   '{"artifact":"external_tasks","group":"Planning"}'),
  ('code_writer', 'Code Writer Agent', 'Writes code in a sandbox, commits to a branch, and opens pull requests.', 'development', 4,
   '{"artifact":"pull_requests","group":"Development"}'),
  ('review', 'Review Agent', 'Reviews PR diffs, approves or sends feedback with retry loops.', 'development', 5,
   '{"artifact":"pull_requests","group":"Development"}'),
  ('test_writer', 'Test Writer Agent', 'Generates unit and integration tests for the selected stack.', 'quality', 6,
   '{"artifact":"validation_reports","group":"Quality"}'),
  ('test_runner', 'Test Runner Agent', 'Executes tests in an isolated sandbox and reports pass/fail.', 'quality', 7,
   '{"artifact":"validation_reports","group":"Quality"}'),
  ('deploy', 'Deploy Agent', 'Builds container images and deploys to staging environments.', 'delivery', 8,
   '{"artifact":"deployments","group":"Delivery"}'),
  ('smoke_test', 'Smoke Test Agent', 'Runs browser smoke tests against the deployed staging URL.', 'delivery', 9,
   '{"artifact":"validation_reports","group":"Delivery"}'),
  ('validation', 'Validation Agent', 'Compares delivered output against the original PRD requirements.', 'quality', 10,
   '{"artifact":"validation_reports","group":"Quality"}');

-- Plan ↔ agent mapping (mirror integrations pattern)
INSERT INTO plan_platform_agents (plan_id, platform_agent_id)
SELECT p.id, pa.id
FROM plans p
CROSS JOIN platform_agents pa
WHERE p.name = 'Enterprise';

INSERT INTO plan_platform_agents (plan_id, platform_agent_id)
SELECT p.id, pa.id
FROM plans p
JOIN platform_agents pa ON pa.agent_key IN (
  'requirements', 'architecture', 'task_planner', 'code_writer', 'review',
  'test_writer', 'test_runner', 'deploy', 'validation'
)
WHERE p.name = 'Professional';

INSERT INTO plan_platform_agents (plan_id, platform_agent_id)
SELECT p.id, pa.id
FROM plans p
JOIN platform_agents pa ON pa.agent_key IN ('requirements', 'code_writer', 'review')
WHERE p.name = 'Starter';
