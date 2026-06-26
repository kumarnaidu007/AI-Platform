from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.deps import DbDep
from app.routers.admin import require_super_admin
from models import Workspace
from models.agents import WorkspacePlatformAgent, PlatformAgent
from schemas.agents import (
    CompanyAgentAccessItem,
    CompanyAgentsAccessUpdate,
    PlatformAgentResponse,
    PlatformAgentUpdate,
)
from services.agent_helpers import agent_is_assignable, agent_to_dict, list_platform_agents

router = APIRouter(
    prefix="/api/admin",
    tags=["admin-agents"],
    dependencies=[Depends(require_super_admin)],
)


@router.get("/agents", response_model=list[PlatformAgentResponse])
def list_agents(db: DbDep):
    return [PlatformAgentResponse(**agent_to_dict(a)) for a in list_platform_agents(db)]


@router.patch("/agents/{key}", response_model=PlatformAgentResponse)
def update_agent(key: str, body: PlatformAgentUpdate, db: DbDep):
    agent = db.query(PlatformAgent).filter(PlatformAgent.agent_key == key).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if body.is_enabled is not None:
        agent.is_enabled = body.is_enabled
        agent.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(agent)
    return PlatformAgentResponse(**agent_to_dict(agent))


@router.get("/companies/{workspace_id}/agents-access", response_model=list[CompanyAgentAccessItem])
def get_workspace_agents_access(workspace_id: str, db: DbDep):
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(404, "Workspace not found")

    access_map = {
        row.platform_agent_id: row.is_enabled
        for row in db.query(WorkspacePlatformAgent)
        .filter(WorkspacePlatformAgent.workspace_id == workspace.id)
        .all()
    }
    items: list[CompanyAgentAccessItem] = []
    for agent in list_platform_agents(db):
        assignable = agent_is_assignable(agent)
        granted = access_map.get(agent.id, False)
        data = agent_to_dict(agent)
        items.append(
            CompanyAgentAccessItem(
                agent_key=data["agent_key"],
                name=data["name"],
                category=data["category"],
                group=data.get("group"),
                default_step_order=data["default_step_order"],
                is_enabled=granted if assignable else False,
                platform_enabled=agent.is_enabled,
                assignable=assignable,
            )
        )
    return items


@router.put("/companies/{workspace_id}/agents-access", response_model=list[CompanyAgentAccessItem])
def update_workspace_agents_access(workspace_id: str, body: CompanyAgentsAccessUpdate, db: DbDep):
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(404, "Workspace not found")

    key_to_agent = {a.agent_key: a for a in list_platform_agents(db)}

    for item in body.agents:
        agent = key_to_agent.get(item.agent_key)
        if not agent:
            raise HTTPException(400, f"Unknown agent: {item.agent_key}")
        if item.is_enabled and not agent_is_assignable(agent):
            raise HTTPException(
                400,
                f"Agent '{item.agent_key}' is disabled on the platform — enable it in Agents first",
            )
        row = (
            db.query(WorkspacePlatformAgent)
            .filter(
                WorkspacePlatformAgent.workspace_id == workspace.id,
                WorkspacePlatformAgent.platform_agent_id == agent.id,
            )
            .first()
        )
        if item.is_enabled:
            if row:
                row.is_enabled = True
            else:
                db.add(
                    WorkspacePlatformAgent(
                        workspace_id=workspace.id,
                        platform_agent_id=agent.id,
                        is_enabled=True,
                    )
                )
        elif row:
            row.is_enabled = False

    db.commit()
    return get_workspace_agents_access(workspace_id, db)
