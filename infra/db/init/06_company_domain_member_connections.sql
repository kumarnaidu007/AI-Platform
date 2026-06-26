-- Workspace email domain + per-user integration credentials

ALTER TABLE workspace_settings
    ADD COLUMN IF NOT EXISTS email_domain VARCHAR(255);

CREATE TABLE member_integration_connections (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id            UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform_integration_id UUID NOT NULL REFERENCES platform_integrations(id) ON DELETE CASCADE,
    connection_name         VARCHAR(255) NOT NULL DEFAULT 'Default',
    status                  VARCHAR(32) NOT NULL DEFAULT 'not_configured',
    encrypted_config_ref    VARCHAR(512),
    config_metadata_json    JSONB DEFAULT '{}',
    last_tested_at          TIMESTAMPTZ,
    last_test_status        BOOLEAN,
    last_error_message      TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (workspace_id, user_id, platform_integration_id)
);

CREATE INDEX idx_member_integration_connections_workspace_user
    ON member_integration_connections(workspace_id, user_id);
