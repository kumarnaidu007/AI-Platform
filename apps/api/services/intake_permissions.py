"""Intake access control for team lead vs member workflows."""

from __future__ import annotations

from uuid import UUID

from constants.roles import TEAM_LEAD
from models.requirements import JiraTicketIntake


def is_team_lead(member_role: str | None) -> bool:
    return member_role == TEAM_LEAD


def effective_assignee_id(intake: JiraTicketIntake) -> UUID:
    return intake.assignee_user_id or intake.user_id


def can_view_intake(intake: JiraTicketIntake, user_id: UUID, member_role: str | None) -> bool:
    if is_team_lead(member_role):
        return True
    if intake.user_id == user_id:
        return True
    if intake.assignee_user_id == user_id:
        return True
    if intake.planner_user_id == user_id:
        return True
    return False


def can_edit_intake(intake: JiraTicketIntake, user_id: UUID, member_role: str | None) -> bool:
    if intake.intake_mode == "lead_planning":
        if is_team_lead(member_role) or intake.planner_user_id == user_id or intake.user_id == user_id:
            return True
        return False
    return can_view_intake(intake, user_id, member_role)


def can_implement_intake(intake: JiraTicketIntake, user_id: UUID, member_role: str | None) -> bool:
    if intake.intake_mode == "lead_planning":
        return False
    assignee = effective_assignee_id(intake)
    if user_id == assignee:
        return True
    if is_team_lead(member_role) and intake.user_id == user_id:
        return True
    return False


def can_plan_jira_tasks(intake: JiraTicketIntake, user_id: UUID, member_role: str | None) -> bool:
    if intake.intake_mode != "lead_planning":
        return False
    return is_team_lead(member_role) or intake.planner_user_id == user_id
