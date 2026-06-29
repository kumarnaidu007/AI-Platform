-- Store proposed code changes until the member approves push/PR.
ALTER TABLE jira_ticket_intakes
  ADD COLUMN IF NOT EXISTS pending_publish_json JSONB,
  ADD COLUMN IF NOT EXISTS pr_url TEXT;
