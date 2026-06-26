from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from constants.roles import TEAM_LEAD
from app.deps import TeamLeadDep, WorkspaceAdminDep, WorkspaceAuthDep, WorkspaceWriterDep, DbDep
from models import Workspace, WorkspaceMember, Project, User
from models.agents import WorkspacePlatformAgent, MemberAgentAccess, PlatformAgent, ProjectAgent
from schemas.agents import (
    CompanyAgentCatalogItem,
    MemberAgentAccessItem,
    MemberAgentsAccessUpdate,
    MyAgentItem,
    ProjectAgentItem,
    ProjectAgentsUpdate,
)
from services.agent_helpers import agent_is_assignable, agent_to_dict, list_platform_agents

router = APIRouter(prefix="/api/workspace", tags=["workspace-agents"])


def _granted_agent_ids(db: Session, workspace_id) -> set:
    rows = (
        db.query(WorkspacePlatformAgent)
        .filter(
            WorkspacePlatformAgent.workspace_id == workspace_id,
            WorkspacePlatformAgent.is_enabled.is_(True),
        )
        .all()
    )
    return {r.platform_agent_id for r in rows}


def _list_granted_agents(db: Session, workspace_id) -> list[PlatformAgent]:
    granted = _granted_agent_ids(db, workspace_id)
    agents = list_platform_agents(db)
    return [a for a in agents if a.id in granted and agent_is_assignable(a)]


def _assigned_agent_ids(db: Session, workspace_id, user_id) -> set:
    rows = (
        db.query(MemberAgentAccess)
        .filter(
            MemberAgentAccess.workspace_id == workspace_id,
            MemberAgentAccess.user_id == user_id,
            MemberAgentAccess.is_enabled.is_(True),
        )
        .all()
    )
    return {r.platform_agent_id for r in rows}


def _get_member_or_403(db: Session, ctx : WorkspaceAuthDep, member_id: str) -> WorkspaceMember:
    member = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.id == member_id, WorkspaceMember.workspace_id == ctx.workspace_id)
        .first()
    )
    if not member:
        raise HTTPException(404, "Member not found")
    if ctx.member_role != TEAM_LEAD and member.user_id != ctx.user.id:
        raise HTTPException(403, "Not allowed to view this member's agents")
    return member


@router.get("/agents", response_model=list[CompanyAgentCatalogItem])
def workspace_agents_catalog(ctx : WorkspaceAdminDep, db: DbDep):
    return [
        CompanyAgentCatalogItem(
            agent_key=a.agent_key,
            name=a.name,
            description=a.description,
            category=a.category,
            group=(a.metadata_json or {}).get("group"),
            default_step_order=a.default_step_order,
            is_granted=True,
        )
        for a in _list_granted_agents(db, ctx.workspace_id)
    ]


@router.get("/my-agents", response_model=list[MyAgentItem])
def my_agents(ctx : WorkspaceAuthDep, db: DbDep):
    assigned = _assigned_agent_ids(db, ctx.workspace_id, ctx.user.id)
    items: list[MyAgentItem] = []
    for agent in _list_granted_agents(db, ctx.workspace_id):
        if agent.id not in assigned:
            continue
        data = agent_to_dict(agent)
        items.append(
            MyAgentItem(
                agent_key=data["agent_key"],
                name=data["name"],
                description=data["description"],
                category=data["category"],
                group=data.get("group"),
                default_step_order=data["default_step_order"],
                is_assigned=True,
                is_enabled_on_platform=agent.is_enabled,
            )
        )
    return items


@router.get("/members/{member_id}/agents", response_model=list[MemberAgentAccessItem])
def get_member_agents(member_id: str, ctx : WorkspaceAuthDep, db: DbDep):
    member = _get_member_or_403(db, ctx, member_id)
    assigned = {
        row.platform_agent_id: row.is_enabled
        for row in db.query(MemberAgentAccess)
        .filter(
            MemberAgentAccess.workspace_id == ctx.workspace_id,
            MemberAgentAccess.user_id == member.user_id,
        )
        .all()
    }
    items: list[MemberAgentAccessItem] = []
    for agent in _list_granted_agents(db, ctx.workspace_id):
        data = agent_to_dict(agent)
        items.append(
            MemberAgentAccessItem(
                agent_key=data["agent_key"],
                name=data["name"],
                category=data["category"],
                group=data.get("group"),
                default_step_order=data["default_step_order"],
                is_assigned=assigned.get(agent.id, False),
            )
        )
    return items


@router.put("/members/{member_id}/agents", response_model=list[MemberAgentAccessItem])
def update_member_agents(member_id: str, body: MemberAgentsAccessUpdate, ctx : WorkspaceAdminDep, db: DbDep):
    member = _get_member_or_403(db, ctx, member_id)
    key_to_agent = {a.agent_key: a for a in _list_granted_agents(db, ctx.workspace_id)}

    for item in body.agents:
        agent = key_to_agent.get(item.agent_key)
        if not agent:
            raise HTTPException(400, f"Agent not granted to Workspace: {item.agent_key}")
        row = (
            db.query(MemberAgentAccess)
            .filter(
                MemberAgentAccess.workspace_id == ctx.workspace_id,
                MemberAgentAccess.user_id == member.user_id,
                MemberAgentAccess.platform_agent_id == agent.id,
            )
            .first()
        )
        if item.is_assigned:
            if row:
                row.is_enabled = True
            else:
                db.add(
                    MemberAgentAccess(
                        workspace_id=ctx.workspace_id,
                        user_id=member.user_id,
                        platform_agent_id=agent.id,
                        is_enabled=True,
                        granted_by_user_id=ctx.user.id,
                    )
                )
        elif row:
            row.is_enabled = False

    db.commit()
    return get_member_agents(member_id, ctx, db)


@router.get("/projects/{project_id}/agents", response_model=list[ProjectAgentItem])
def get_project_agents(project_id: str, ctx : WorkspaceAuthDep, db: DbDep):
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.workspace_id == ctx.workspace_id)
        .first()
    )
    if not project:
        raise HTTPException(404, "Project not found")

    assigned = _assigned_agent_ids(db, ctx.workspace_id, ctx.user.id)
    config_map = {
        row.platform_agent_id: row
        for row in db.query(ProjectAgent).filter(ProjectAgent.project_id == project.id).all()
    }

    items: list[ProjectAgentItem] = []
    for agent in _list_granted_agents(db, ctx.workspace_id):
        if agent.id not in assigned:
            continue
        data = agent_to_dict(agent)
        cfg = config_map.get(agent.id)
        items.append(
            ProjectAgentItem(
                agent_key=data["agent_key"],
                name=data["name"],
                category=data["category"],
                group=data.get("group"),
                step_order=cfg.step_order if cfg else data["default_step_order"],
                is_enabled=cfg.is_enabled if cfg else False,
                is_assigned=True,
                default_step_order=data["default_step_order"],
            )
        )
    items.sort(key=lambda x: x.step_order)
    return items


@router.put("/projects/{project_id}/agents", response_model=list[ProjectAgentItem])
def update_project_agents(project_id: str, body: ProjectAgentsUpdate, ctx : WorkspaceWriterDep, db: DbDep):
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.workspace_id == ctx.workspace_id)
        .first()
    )
    if not project:
        raise HTTPException(404, "Project not found")

    assigned = _assigned_agent_ids(db, ctx.workspace_id, ctx.user.id)
    key_to_agent = {a.agent_key: a for a in _list_granted_agents(db, ctx.workspace_id)}

    for item in body.agents:
        agent = key_to_agent.get(item.agent_key)
        if not agent:
            raise HTTPException(400, f"Agent not available: {item.agent_key}")
        if agent.id not in assigned:
            raise HTTPException(403, f"Agent '{item.agent_key}' is not assigned to you")

        row = (
            db.query(ProjectAgent)
            .filter(
                ProjectAgent.project_id == project.id,
                ProjectAgent.platform_agent_id == agent.id,
            )
            .first()
        )
        step_order = item.step_order if item.step_order is not None else agent.default_step_order
        if item.is_enabled:
            if row:
                row.is_enabled = True
                row.step_order = step_order
                row.updated_at = datetime.now(UTC)
            else:
                db.add(
                    ProjectAgent(
                        project_id=project.id,
                        platform_agent_id=agent.id,
                        is_enabled=True,
                        step_order=step_order,
                    )
                )
        elif row:
            row.is_enabled = False
            row.updated_at = datetime.now(UTC)

    db.commit()
    return get_project_agents(project_id, ctx, db)
