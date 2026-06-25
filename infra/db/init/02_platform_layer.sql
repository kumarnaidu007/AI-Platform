-- Platform layer: integration catalog, connections, AI services, settings
-- Run after 01_schema.sql

CREATE TYPE integration_category AS ENUM (
  'vcs', 'pm', 'notify', 'deploy', 'requirements', 'identity'
);

CREATE TYPE integration_auth_type AS ENUM (
  'oauth2', 'api_key', 'webhook', 'smtp', 'service_principal'
);

CREATE TYPE connection_status AS ENUM (
  'not_configured', 'connected', 'error', 'disabled'
);

-- Catalog of integrations the platform offers (no secrets)
CREATE TABLE platform_integrations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_key     VARCHAR(64) NOT NULL UNIQUE,
    name                VARCHAR(128) NOT NULL,
    description         TEXT,
    category            integration_category NOT NULL,
    auth_type           integration_auth_type NOT NULL,
    is_enabled          BOOLEAN NOT NULL DEFAULT TRUE,
    config_schema_json  JSONB NOT NULL DEFAULT '{}',
    documentation_url   VARCHAR(512),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Platform-owned OAuth apps / connection configs (secret refs only)
CREATE TABLE platform_connections (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_integration_id UUID NOT NULL REFERENCES platform_integrations(id) ON DELETE CASCADE,
    connection_name         VARCHAR(255) NOT NULL DEFAULT 'Default',
    status                  connection_status NOT NULL DEFAULT 'not_configured',
    encrypted_config_ref    VARCHAR(512),
    config_metadata_json    JSONB DEFAULT '{}',
    last_tested_at          TIMESTAMPTZ,
    last_test_status        BOOLEAN,
    last_error_message      TEXT,
    created_by              UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform_integration_id, connection_name)
);

-- AI / runtime services (Anthropic, E2B, etc.)
CREATE TABLE platform_services (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_key          VARCHAR(64) NOT NULL UNIQUE,
    display_name         VARCHAR(128) NOT NULL,
    description          TEXT,
    is_enabled           BOOLEAN NOT NULL DEFAULT FALSE,
    encrypted_config_ref VARCHAR(512),
    config_metadata_json JSONB DEFAULT '{}',
    last_tested_at       TIMESTAMPTZ,
    last_test_status     BOOLEAN,
    last_error_message   TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Global platform key-value settings
CREATE TABLE platform_settings (
    key         VARCHAR(128) PRIMARY KEY,
    value_json  JSONB NOT NULL DEFAULT '{}',
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Which integrations each plan allows (for later company onboarding)
CREATE TABLE plan_platform_integrations (
    plan_id                 UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    platform_integration_id UUID NOT NULL REFERENCES platform_integrations(id) ON DELETE CASCADE,
    PRIMARY KEY (plan_id, platform_integration_id)
);

CREATE INDEX idx_platform_connections_integration ON platform_connections(platform_integration_id);
CREATE INDEX idx_platform_connections_status ON platform_connections(status);
CREATE INDEX idx_platform_integrations_category ON platform_integrations(category);
CREATE INDEX idx_platform_integrations_enabled ON platform_integrations(is_enabled);

-- Seed: integration catalog
INSERT INTO platform_integrations (integration_key, name, description, category, auth_type, config_schema_json, documentation_url) VALUES
  ('github', 'GitHub', 'Source control — repos, branches, PRs, issues', 'vcs', 'oauth2',
   '{"fields":[{"key":"client_id","label":"OAuth App Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true},{"key":"webhook_secret","label":"Webhook Secret","type":"secret","required":false}]}',
   'https://docs.github.com/en/apps'),
  ('gitlab', 'GitLab', 'Source control and CI/CD pipelines', 'vcs', 'oauth2',
   '{"fields":[{"key":"client_id","label":"Application ID","type":"text","required":true},{"key":"client_secret","label":"Secret","type":"secret","required":true},{"key":"gitlab_url","label":"GitLab URL","type":"text","required":false,"default":"https://gitlab.com"}]}',
   'https://docs.gitlab.com/ee/integration/oauth_provider.html'),
  ('azure_devops', 'Azure DevOps', 'Repos, boards, and pipelines on Azure', 'vcs', 'oauth2',
   '{"fields":[{"key":"tenant_id","label":"Azure AD Tenant ID","type":"text","required":true},{"key":"client_id","label":"App Registration Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true},{"key":"organization_url","label":"DevOps Organization URL","type":"text","required":true}]}',
   'https://learn.microsoft.com/en-us/azure/devops/integrate/'),
  ('bitbucket', 'Bitbucket', 'Atlassian Git hosting and PRs', 'vcs', 'oauth2',
   '{"fields":[{"key":"client_id","label":"OAuth Consumer Key","type":"text","required":true},{"key":"client_secret","label":"Consumer Secret","type":"secret","required":true}]}',
   'https://developer.atlassian.com/cloud/bitbucket/'),
  ('jira', 'Jira', 'Issue tracking and sprint management', 'pm', 'oauth2',
   '{"fields":[{"key":"client_id","label":"OAuth Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true},{"key":"jira_url","label":"Jira Cloud URL","type":"text","required":true}]}',
   'https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/'),
  ('azure_boards', 'Azure Boards', 'Work items and sprints on Azure DevOps', 'pm', 'oauth2',
   '{"fields":[{"key":"tenant_id","label":"Azure AD Tenant ID","type":"text","required":true},{"key":"client_id","label":"Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true}]}',
   'https://learn.microsoft.com/en-us/azure/devops/boards/'),
  ('linear', 'Linear', 'Modern issue tracking for dev teams', 'pm', 'api_key',
   '{"fields":[{"key":"api_key","label":"API Key","type":"secret","required":true}]}',
   'https://developers.linear.app/'),
  ('notion', 'Notion', 'Requirements docs and wikis', 'requirements', 'oauth2',
   '{"fields":[{"key":"client_id","label":"OAuth Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true}]}',
   'https://developers.notion.com/docs/authorization'),
  ('confluence', 'Confluence', 'Enterprise documentation and requirements', 'requirements', 'oauth2',
   '{"fields":[{"key":"client_id","label":"OAuth Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true},{"key":"confluence_url","label":"Confluence URL","type":"text","required":true}]}',
   'https://developer.atlassian.com/cloud/confluence/oauth-2-3lo-apps/'),
  ('teams', 'Microsoft Teams', 'Channel notifications and alerts', 'notify', 'oauth2',
   '{"fields":[{"key":"tenant_id","label":"Azure AD Tenant ID","type":"text","required":true},{"key":"client_id","label":"App Registration Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true}]}',
   'https://learn.microsoft.com/en-us/graph/teams-concept-overview'),
  ('slack', 'Slack', 'Workspace notifications and bot messages', 'notify', 'oauth2',
   '{"fields":[{"key":"client_id","label":"App Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true},{"key":"signing_secret","label":"Signing Secret","type":"secret","required":true}]}',
   'https://api.slack.com/authentication/oauth-v2'),
  ('email', 'Email (SMTP)', 'Platform and tenant email delivery', 'notify', 'smtp',
   '{"fields":[{"key":"smtp_host","label":"SMTP Host","type":"text","required":true},{"key":"smtp_port","label":"Port","type":"number","required":true,"default":587},{"key":"smtp_user","label":"Username","type":"text","required":true},{"key":"smtp_password","label":"Password","type":"secret","required":true},{"key":"from_address","label":"From Address","type":"email","required":true}]}',
   NULL),
  ('azure', 'Microsoft Azure', 'Cloud deploy targets — App Service, AKS, Functions', 'deploy', 'service_principal',
   '{"fields":[{"key":"tenant_id","label":"Tenant ID","type":"text","required":true},{"key":"client_id","label":"Service Principal Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true},{"key":"subscription_id","label":"Default Subscription ID","type":"text","required":false}]}',
   'https://learn.microsoft.com/en-us/azure/active-directory/develop/'),
  ('aws', 'Amazon Web Services', 'Deploy to ECS, Lambda, EKS', 'deploy', 'api_key',
   '{"fields":[{"key":"access_key_id","label":"Access Key ID","type":"text","required":true},{"key":"secret_access_key","label":"Secret Access Key","type":"secret","required":true},{"key":"region","label":"Default Region","type":"text","required":true,"default":"us-east-1"}]}',
   'https://docs.aws.amazon.com/IAM/'),
  ('gcp', 'Google Cloud Platform', 'Deploy to Cloud Run, GKE', 'deploy', 'service_principal',
   '{"fields":[{"key":"project_id","label":"GCP Project ID","type":"text","required":true},{"key":"service_account_json","label":"Service Account JSON","type":"secret","required":true}]}',
   'https://cloud.google.com/iam/docs/service-account-overview'),
  ('docker_registry', 'Docker Registry', 'Push built images to registry', 'deploy', 'api_key',
   '{"fields":[{"key":"registry_url","label":"Registry URL","type":"text","required":true},{"key":"username","label":"Username","type":"text","required":true},{"key":"password","label":"Password / Token","type":"secret","required":true}]}',
   NULL);

-- Seed: AI platform services
INSERT INTO platform_services (service_key, display_name, description, is_enabled, config_metadata_json) VALUES
  ('anthropic', 'Anthropic Claude', 'Primary LLM for agents — Claude Sonnet', FALSE,
   '{"default_model":"claude-sonnet-4-20250514","max_tokens":8192}'),
  ('openai', 'OpenAI GPT', 'Fallback LLM — GPT-4o', FALSE,
   '{"default_model":"gpt-4o","max_tokens":8192}'),
  ('e2b', 'E2B Sandboxes', 'Secure code execution for agents', FALSE,
   '{"template":"base","timeout_seconds":300}'),
  ('langsmith', 'LangSmith', 'Agent tracing, cost tracking, replay', FALSE,
   '{"project_name":"ai-dev-platform"}'),
  ('pgvector', 'pgvector (RAG)', 'Codebase embedding and retrieval', FALSE,
   '{"embedding_model":"text-embedding-3-small","chunk_size":512}');

-- Seed: platform settings
INSERT INTO platform_settings (key, value_json, description) VALUES
  ('default_llm_provider', '"anthropic"', 'Default LLM provider for new pipelines'),
  ('maintenance_mode', 'false', 'Disable new pipeline runs platform-wide'),
  ('allow_byodb', 'true', 'Allow companies to use their own database'),
  ('max_agent_retries', '3', 'Default max retries per agent step'),
  ('oauth_redirect_base_url', '"http://localhost:8000/oauth/callback"', 'Base URL for OAuth redirects'),
  ('platform_name', '"AI Dev Platform"', 'Display name in UI and emails');

-- Seed: plan ↔ integration mapping
INSERT INTO plan_platform_integrations (plan_id, platform_integration_id)
SELECT p.id, pi.id
FROM plans p
CROSS JOIN platform_integrations pi
WHERE p.name = 'Enterprise';

INSERT INTO plan_platform_integrations (plan_id, platform_integration_id)
SELECT p.id, pi.id
FROM plans p
JOIN platform_integrations pi ON pi.integration_key IN (
  'github', 'gitlab', 'jira', 'linear', 'notion', 'teams', 'slack', 'email', 'azure_devops', 'azure'
)
WHERE p.name = 'Professional';

INSERT INTO plan_platform_integrations (plan_id, platform_integration_id)
SELECT p.id, pi.id
FROM plans p
JOIN platform_integrations pi ON pi.integration_key IN ('github', 'jira', 'email', 'notion')
WHERE p.name = 'Starter';

-- Sample platform connections (metadata only — secrets in vault)
INSERT INTO platform_connections (platform_integration_id, connection_name, status, config_metadata_json, last_tested_at, last_test_status)
SELECT id, 'Production OAuth App', 'connected',
  '{"client_id":"ghp_***configured","scopes":["repo","read:org"],"redirect_uri":"http://localhost:8000/oauth/github/callback"}',
  NOW(), TRUE
FROM platform_integrations WHERE integration_key = 'github';

INSERT INTO platform_connections (platform_integration_id, connection_name, status, config_metadata_json, last_tested_at, last_test_status)
SELECT id, 'Microsoft Graph App', 'connected',
  '{"tenant_id":"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx","client_id":"yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy","scopes":["ChannelMessage.Send","Team.ReadBasic.All"]}',
  NOW(), TRUE
FROM platform_integrations WHERE integration_key = 'teams';

INSERT INTO platform_connections (platform_integration_id, connection_name, status, last_error_message)
SELECT id, 'Azure AD App', 'error',
  'Invalid client secret — re-authenticate in Azure Portal'
FROM platform_integrations WHERE integration_key = 'azure';

-- Sample AI service connections
UPDATE platform_services SET
  is_enabled = TRUE,
  encrypted_config_ref = 'vault://prod/anthropic-api-key',
  last_tested_at = NOW(),
  last_test_status = TRUE
WHERE service_key = 'anthropic';

UPDATE platform_services SET
  is_enabled = TRUE,
  encrypted_config_ref = 'vault://prod/e2b-api-key',
  last_tested_at = NOW(),
  last_test_status = TRUE
WHERE service_key = 'e2b';
