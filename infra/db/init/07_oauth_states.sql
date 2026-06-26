-- OAuth state storage for integration callbacks (GitHub, Jira)

CREATE TABLE oauth_states (
    state           VARCHAR(64) PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    integration_key VARCHAR(64) NOT NULL,
    redirect_path   VARCHAR(512),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_oauth_states_expires ON oauth_states(expires_at);
