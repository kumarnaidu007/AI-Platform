-- Single-workspace bootstrap (role migration only when upgrading legacy DB)

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_enum e
    JOIN pg_type t ON e.enumtypid = t.oid
    WHERE t.typname = 'member_role' AND e.enumlabel = 'admin'
  ) THEN
    ALTER TYPE member_role RENAME TO member_role_old;
    CREATE TYPE member_role AS ENUM ('team_lead', 'team_member');

    ALTER TABLE workspace_members
      ALTER COLUMN role DROP DEFAULT,
      ALTER COLUMN role TYPE member_role
      USING (
        CASE role::text
          WHEN 'admin' THEN 'team_lead'::member_role
          WHEN 'member' THEN 'team_member'::member_role
          WHEN 'viewer' THEN 'team_member'::member_role
          ELSE 'team_member'::member_role
        END
      );

    ALTER TABLE workspace_members ALTER COLUMN role SET DEFAULT 'team_member';
    DROP TYPE member_role_old;
  END IF;
END $$;

INSERT INTO workspaces (name, slug, status, plan_id)
SELECT 'AI Dev Platform', 'workspace', 'active', p.id
FROM plans p
WHERE p.name = 'Platform'
  AND NOT EXISTS (SELECT 1 FROM workspaces WHERE slug = 'workspace');

INSERT INTO workspace_settings (workspace_id, email_domain, timezone)
SELECT w.id, NULL, 'UTC'
FROM workspaces w
WHERE w.slug = 'workspace'
  AND NOT EXISTS (SELECT 1 FROM workspace_settings ws WHERE ws.workspace_id = w.id);
