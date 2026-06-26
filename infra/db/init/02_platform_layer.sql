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

CREATE TABLE platform_settings (
    key         VARCHAR(128) PRIMARY KEY,
    value_json  JSONB NOT NULL DEFAULT '{}',
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE plan_platform_integrations (
    plan_id                 UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    platform_integration_id UUID NOT NULL REFERENCES platform_integrations(id) ON DELETE CASCADE,
    PRIMARY KEY (plan_id, platform_integration_id)
);

CREATE INDEX idx_platform_connections_integration ON platform_connections(platform_integration_id);
CREATE INDEX idx_platform_connections_status ON platform_connections(status);
CREATE INDEX idx_platform_integrations_category ON platform_integrations(category);
CREATE INDEX idx_platform_integrations_enabled ON platform_integrations(is_enabled);

-- Integrations: GitHub + Jira only
INSERT INTO platform_integrations (integration_key, name, description, category, auth_type, config_schema_json, documentation_url) VALUES
  ('github', 'GitHub', 'Source control — repos, branches, PRs', 'vcs', 'oauth2',
   '{"fields":[{"key":"client_id","label":"OAuth App Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true}]}',
   'https://docs.github.com/en/apps'),
  ('jira', 'Jira', 'Issue tracking and sprint management', 'pm', 'oauth2',
   '{"fields":[{"key":"client_id","label":"OAuth Client ID","type":"text","required":true},{"key":"client_secret","label":"Client Secret","type":"secret","required":true}]}',
   'https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/');

INSERT INTO platform_services (service_key, display_name, description, is_enabled, config_metadata_json) VALUES
  ('azure_foundry', 'Microsoft Foundry', 'Azure AI Foundry project endpoint — powers all agents via your deployed models', FALSE,
   '{"deployment_name":"claude-sonnet-4-6","embedding_deployment":"text-embedding-3-small"}'),
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

INSERT INTO platform_settings (key, value_json, description) VALUES
  ('default_llm_provider', '"anthropic"', 'Default LLM provider for new pipelines'),
  ('maintenance_mode', 'false', 'Disable new pipeline runs platform-wide'),
  ('max_agent_retries', '3', 'Default max retries per agent step'),
  ('oauth_redirect_base_url', '"http://localhost:8000/api/oauth"', 'Base URL for OAuth redirects'),
  ('platform_name', '"AI Dev Platform"', 'Display name in UI');

INSERT INTO plan_platform_integrations (plan_id, platform_integration_id)
SELECT p.id, pi.id
FROM plans p
CROSS JOIN platform_integrations pi;
