-- Team lead / member Jira workflow

ALTER TABLE jira_ticket_intakes
  ADD COLUMN IF NOT EXISTS planner_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS assignee_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS parent_jira_key VARCHAR(32),
  ADD COLUMN IF NOT EXISTS intake_mode VARCHAR(24) NOT NULL DEFAULT 'member',
  ADD COLUMN IF NOT EXISTS jira_project_key VARCHAR(32),
  ADD COLUMN IF NOT EXISTS jira_tasks_json JSONB;

CREATE INDEX IF NOT EXISTS idx_jira_intakes_parent ON jira_ticket_intakes(workspace_id, parent_jira_key);
CREATE INDEX IF NOT EXISTS idx_jira_intakes_assignee ON jira_ticket_intakes(assignee_user_id, status);
