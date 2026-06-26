-- Upgrade cleanup: remove Teams, rename legacy company schema, keep GitHub + Jira only

DROP TABLE IF EXISTS teams_messages CASCADE;
DROP TABLE IF EXISTS teams_chats CASCADE;
DROP TABLE IF EXISTS teams_sync_state CASCADE;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'companies') THEN
    ALTER TYPE company_status RENAME TO workspace_status;
    ALTER TABLE companies RENAME TO workspaces;

    ALTER TABLE IF EXISTS company_limits RENAME TO workspace_limits;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'workspace_limits' AND column_name = 'company_id') THEN
      ALTER TABLE workspace_limits RENAME COLUMN company_id TO workspace_id;
    END IF;

    ALTER TABLE IF EXISTS company_members RENAME TO workspace_members;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'workspace_members' AND column_name = 'company_id') THEN
      ALTER TABLE workspace_members RENAME COLUMN company_id TO workspace_id;
    END IF;

    ALTER TABLE IF EXISTS company_settings RENAME TO workspace_settings;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'workspace_settings' AND column_name = 'company_id') THEN
      ALTER TABLE workspace_settings RENAME COLUMN company_id TO workspace_id;
    END IF;

    ALTER TABLE IF EXISTS company_platform_integrations RENAME TO workspace_platform_integrations;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'workspace_platform_integrations' AND column_name = 'company_id') THEN
      ALTER TABLE workspace_platform_integrations RENAME COLUMN company_id TO workspace_id;
    END IF;

    ALTER TABLE IF EXISTS company_platform_services RENAME TO workspace_platform_services;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'workspace_platform_services' AND column_name = 'company_id') THEN
      ALTER TABLE workspace_platform_services RENAME COLUMN company_id TO workspace_id;
    END IF;

    ALTER TABLE IF EXISTS company_platform_agents RENAME TO workspace_platform_agents;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'workspace_platform_agents' AND column_name = 'company_id') THEN
      ALTER TABLE workspace_platform_agents RENAME COLUMN company_id TO workspace_id;
    END IF;

    ALTER TABLE IF EXISTS company_integration_connections RENAME TO workspace_integration_connections;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'workspace_integration_connections' AND column_name = 'company_id') THEN
      ALTER TABLE workspace_integration_connections RENAME COLUMN company_id TO workspace_id;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'integration_configs' AND column_name = 'company_id') THEN
      ALTER TABLE integration_configs RENAME COLUMN company_id TO workspace_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'company_id') THEN
      ALTER TABLE projects RENAME COLUMN company_id TO workspace_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_events' AND column_name = 'company_id') THEN
      ALTER TABLE audit_events RENAME COLUMN company_id TO workspace_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'usage_ledger' AND column_name = 'company_id') THEN
      ALTER TABLE usage_ledger RENAME COLUMN company_id TO workspace_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'member_integration_access' AND column_name = 'company_id') THEN
      ALTER TABLE member_integration_access RENAME COLUMN company_id TO workspace_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'member_integration_connections' AND column_name = 'company_id') THEN
      ALTER TABLE member_integration_connections RENAME COLUMN company_id TO workspace_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'member_agent_access' AND column_name = 'company_id') THEN
      ALTER TABLE member_agent_access RENAME COLUMN company_id TO workspace_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'oauth_states' AND column_name = 'company_id') THEN
      ALTER TABLE oauth_states RENAME COLUMN company_id TO workspace_id;
    END IF;
  END IF;
END $$;

DELETE FROM member_integration_connections
WHERE platform_integration_id IN (
  SELECT id FROM platform_integrations WHERE integration_key NOT IN ('github', 'jira')
);
DELETE FROM member_integration_access
WHERE platform_integration_id IN (
  SELECT id FROM platform_integrations WHERE integration_key NOT IN ('github', 'jira')
);
DELETE FROM workspace_platform_integrations
WHERE platform_integration_id IN (
  SELECT id FROM platform_integrations WHERE integration_key NOT IN ('github', 'jira')
);
DELETE FROM plan_platform_integrations
WHERE platform_integration_id IN (
  SELECT id FROM platform_integrations WHERE integration_key NOT IN ('github', 'jira')
);
DELETE FROM platform_connections
WHERE platform_integration_id IN (
  SELECT id FROM platform_integrations WHERE integration_key NOT IN ('github', 'jira')
);
DELETE FROM platform_integrations WHERE integration_key NOT IN ('github', 'jira');

DELETE FROM platform_connections;

TRUNCATE agent_memory, codebase_chunks RESTART IDENTITY CASCADE;
TRUNCATE agent_logs, pipeline_steps, pipeline_runs RESTART IDENTITY CASCADE;
TRUNCATE validation_reports, deployments, pull_requests, external_tasks RESTART IDENTITY CASCADE;
TRUNCATE prd_documents, architecture_docs RESTART IDENTITY CASCADE;
TRUNCATE project_agents, projects RESTART IDENTITY CASCADE;
TRUNCATE oauth_states RESTART IDENTITY CASCADE;
DELETE FROM audit_events;
DELETE FROM usage_ledger;

UPDATE platform_settings SET value_json = '"http://localhost:8000/api/oauth"'::jsonb
WHERE key = 'oauth_redirect_base_url';
