-- Link projects to a Git repository for agent pipeline execution

ALTER TABLE projects ADD COLUMN IF NOT EXISTS repo_url VARCHAR(512);
