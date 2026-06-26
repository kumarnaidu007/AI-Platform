export const TEAM_LEAD = "team_lead" as const;
export const TEAM_MEMBER = "team_member" as const;

export type WorkspaceRole = typeof TEAM_LEAD | typeof TEAM_MEMBER;

export const ROLE_LABELS: Record<WorkspaceRole, string> = {
  team_lead: "Team Lead",
  team_member: "Team Member",
};

export function isTeamLead(role: string | undefined | null): boolean {
  return role === TEAM_LEAD;
}

export function formatRole(role: string): string {
  if (role in ROLE_LABELS) return ROLE_LABELS[role as WorkspaceRole];
  return role.replace(/_/g, " ");
}
