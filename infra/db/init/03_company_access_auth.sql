-- Company integration/service access + plan service defaults
-- Run after 02_platform_layer.sql

CREATE TABLE plan_platform_services (
    plan_id               UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    platform_service_id   UUID NOT NULL REFERENCES platform_services(id) ON DELETE CASCADE,
    PRIMARY KEY (plan_id, platform_service_id)
);

CREATE TABLE company_platform_integrations (
    company_id              UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    platform_integration_id UUID NOT NULL REFERENCES platform_integrations(id) ON DELETE CASCADE,
    is_enabled              BOOLEAN NOT NULL DEFAULT TRUE,
    granted_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (company_id, platform_integration_id)
);

CREATE TABLE company_platform_services (
    company_id            UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    platform_service_id   UUID NOT NULL REFERENCES platform_services(id) ON DELETE CASCADE,
    is_enabled            BOOLEAN NOT NULL DEFAULT TRUE,
    granted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (company_id, platform_service_id)
);

CREATE INDEX idx_company_platform_integrations_company ON company_platform_integrations(company_id);
CREATE INDEX idx_company_platform_services_company ON company_platform_services(company_id);

-- Plan → AI service defaults
INSERT INTO plan_platform_services (plan_id, platform_service_id)
SELECT p.id, ps.id
FROM plans p
CROSS JOIN platform_services ps
WHERE p.name = 'Enterprise';

INSERT INTO plan_platform_services (plan_id, platform_service_id)
SELECT p.id, ps.id
FROM plans p
JOIN platform_services ps ON ps.service_key IN ('anthropic', 'e2b', 'langsmith')
WHERE p.name = 'Professional';

INSERT INTO plan_platform_services (plan_id, platform_service_id)
SELECT p.id, ps.id
FROM plans p
JOIN platform_services ps ON ps.service_key IN ('anthropic', 'e2b')
WHERE p.name = 'Starter';
