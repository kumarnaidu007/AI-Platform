-- OAuth tokens (especially Jira JWTs) exceed VARCHAR(512) after encryption
ALTER TABLE member_integration_connections
    ALTER COLUMN encrypted_config_ref TYPE TEXT;

ALTER TABLE workspace_integration_connections
    ALTER COLUMN encrypted_config_ref TYPE TEXT;

ALTER TABLE platform_connections
    ALTER COLUMN encrypted_config_ref TYPE TEXT;

ALTER TABLE platform_services
    ALTER COLUMN encrypted_config_ref TYPE TEXT;
