-- Microsoft Teams chat cache + OAuth state

CREATE TABLE oauth_states (
    state           VARCHAR(64) PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    integration_key VARCHAR(64) NOT NULL DEFAULT 'teams',
    redirect_path   VARCHAR(512),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL
);

CREATE TABLE teams_chats (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    graph_chat_id       VARCHAR(512) NOT NULL,
    chat_type           VARCHAR(32) NOT NULL DEFAULT 'chat',
    topic               VARCHAR(512),
    team_id             VARCHAR(255),
    team_name           VARCHAR(255),
    channel_id          VARCHAR(255),
    channel_name        VARCHAR(255),
    last_message_preview TEXT,
    last_message_at     TIMESTAMPTZ,
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, user_id, graph_chat_id)
);

CREATE TABLE teams_messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    graph_chat_id       VARCHAR(512) NOT NULL,
    graph_message_id    VARCHAR(512) NOT NULL,
    sender_name         VARCHAR(255),
    sender_email        VARCHAR(255),
    body_text           TEXT,
    body_html           TEXT,
    message_created_at  TIMESTAMPTZ NOT NULL,
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, user_id, graph_message_id)
);

CREATE TABLE teams_sync_state (
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource_type   VARCHAR(32) NOT NULL DEFAULT 'chats',
    delta_link      TEXT,
    last_synced_at  TIMESTAMPTZ,
    PRIMARY KEY (company_id, user_id, resource_type)
);

CREATE INDEX idx_teams_chats_user ON teams_chats(company_id, user_id, last_message_at DESC);
CREATE INDEX idx_teams_messages_chat ON teams_messages(company_id, user_id, graph_chat_id, message_created_at DESC);
CREATE INDEX idx_oauth_states_expires ON oauth_states(expires_at);
