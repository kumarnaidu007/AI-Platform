-- Workspace integration/service access + plan service defaults

CREATE TABLE plan_platform_services (
    plan_id               UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    platform_service_id   UUID NOT NULL REFERENCES platform_services(id) ON DELETE CASCADE,
    PRIMARY KEY (plan_id, platform_service_id)
);

CREATE TABLE workspace_platform_integrations (
    workspace_id            UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    platform_integration_id UUID NOT NULL REFERENCES platform_integrations(id) ON DELETE CASCADE,
    is_enabled              BOOLEAN NOT NULL DEFAULT TRUE,
    granted_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, platform_integration_id)
);

CREATE TABLE workspace_platform_services (
    workspace_id          UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    platform_service_id   UUID NOT NULL REFERENCES platform_services(id) ON DELETE CASCADE,
    is_enabled            BOOLEAN NOT NULL DEFAULT TRUE,
    granted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, platform_service_id)
);

CREATE INDEX idx_workspace_platform_integrations_workspace ON workspace_platform_integrations(workspace_id);
CREATE INDEX idx_workspace_platform_services_workspace ON workspace_platform_services(workspace_id);

INSERT INTO plan_platform_services (plan_id, platform_service_id)
SELECT p.id, ps.id
FROM plans p
CROSS JOIN platform_services ps;
