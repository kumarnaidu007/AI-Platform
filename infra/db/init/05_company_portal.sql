-- Company portal: tenant integration connections + per-user access

CREATE TABLE company_integration_connections (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id              UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    platform_integration_id UUID NOT NULL REFERENCES platform_integrations(id) ON DELETE CASCADE,
    connection_name         VARCHAR(255) NOT NULL DEFAULT 'Default',
    status                  VARCHAR(32) NOT NULL DEFAULT 'not_configured',
    encrypted_config_ref    VARCHAR(512),
    config_metadata_json    JSONB DEFAULT '{}',
    last_tested_at          TIMESTAMPTZ,
    last_test_status        BOOLEAN,
    last_error_message      TEXT,
    created_by_user_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, platform_integration_id)
);

CREATE TABLE member_integration_access (
    company_id              UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform_integration_id UUID NOT NULL REFERENCES platform_integrations(id) ON DELETE CASCADE,
    is_enabled              BOOLEAN NOT NULL DEFAULT TRUE,
    granted_by_user_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    granted_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (company_id, user_id, platform_integration_id)
);

CREATE INDEX idx_company_integration_connections_company ON company_integration_connections(company_id);
CREATE INDEX idx_member_integration_access_user ON member_integration_access(company_id, user_id);
