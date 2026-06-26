-- Advanced agent features: RAG, memory, approval gate, per-user usage tracking

CREATE TABLE IF NOT EXISTS codebase_chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path    VARCHAR(1024) NOT NULL,
    chunk_index  INTEGER NOT NULL DEFAULT 0,
    content      TEXT NOT NULL,
    embedding    JSONB,
    token_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, file_path, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_codebase_chunks_project ON codebase_chunks(project_id);

CREATE TABLE IF NOT EXISTS agent_memory (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    memory_key   VARCHAR(128) NOT NULL,
    content_json JSONB NOT NULL DEFAULT '{}',
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, memory_key)
);

ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS started_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS approval_plan_json JSONB;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS graph_state_json JSONB;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS review_retry_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE usage_ledger ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_usage_ledger_user ON usage_ledger(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_ledger_project ON usage_ledger(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
