from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from constants.roles import TEAM_LEAD
from models import Workspace, WorkspaceMember, WorkspaceSettings, User
from models.agents import WorkspacePlatformAgent, PlatformAgent
from models.platform import (
    WorkspacePlatformIntegration,
    WorkspacePlatformService,
    PlatformIntegration,
    PlatformService,
)
from services.agent_helpers import agent_is_assignable
from services.auth import hash_password
from services.workspace_domain import email_matches_domain, is_valid_domain, normalize_domain
from services.platform_helpers import integration_is_assignable


def provision_workspace_access(db: Session, workspace: Workspace, *, enabled_by_default: bool = False) -> None:
    """Register platform integrations and services for the workspace (disabled until super admin grants)."""
    integrations = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.is_enabled.is_(True))
        .all()
    )
    for integration in integrations:
        if not integration_is_assignable(integration):
            continue
        existing = (
            db.query(WorkspacePlatformIntegration)
            .filter(
                WorkspacePlatformIntegration.workspace_id == workspace.id,
                WorkspacePlatformIntegration.platform_integration_id == integration.id,
            )
            .first()
        )
        if not existing:
            db.add(
                WorkspacePlatformIntegration(
                    workspace_id=workspace.id,
                    platform_integration_id=integration.id,
                    is_enabled=enabled_by_default,
                )
            )

    services = db.query(PlatformService).all()
    for service in services:
        existing = (
            db.query(WorkspacePlatformService)
            .filter(
                WorkspacePlatformService.workspace_id == workspace.id,
                WorkspacePlatformService.platform_service_id == service.id,
            )
            .first()
        )
        if not existing:
            db.add(
                WorkspacePlatformService(
                    workspace_id=workspace.id,
                    platform_service_id=service.id,
                    is_enabled=enabled_by_default,
                )
            )

    if not workspace.settings:
        settings = WorkspaceSettings(workspace_id=workspace.id)
        db.add(settings)
        workspace.settings = settings


def provision_workspace_agents(db: Session, workspace: Workspace, *, enabled_by_default: bool = False) -> None:
    """Register platform agents for the workspace (disabled until super admin grants)."""
    agents = db.query(PlatformAgent).filter(PlatformAgent.is_enabled.is_(True)).all()
    for agent in agents:
        if not agent_is_assignable(agent):
            continue
        existing = (
            db.query(WorkspacePlatformAgent)
            .filter(
                WorkspacePlatformAgent.workspace_id == workspace.id,
                WorkspacePlatformAgent.platform_agent_id == agent.id,
            )
            .first()
        )
        if not existing:
            db.add(
                WorkspacePlatformAgent(
                    workspace_id=workspace.id,
                    platform_agent_id=agent.id,
                    is_enabled=enabled_by_default,
                )
            )


def provision_workspace(db: Session, workspace: Workspace) -> None:
    provision_workspace_access(db, workspace)
    provision_workspace_agents(db, workspace)
    db.commit()


def set_workspace_email_domain(db: Session, workspace: Workspace, domain: str) -> str:
    norm = normalize_domain(domain)
    if not is_valid_domain(norm):
        raise ValueError("Invalid email domain")
    if not workspace.settings:
        workspace.settings = WorkspaceSettings(workspace_id=workspace.id)
        db.add(workspace.settings)
    workspace.settings.email_domain = norm
    return norm


def create_team_lead_user(
    db: Session,
    workspace: Workspace,
    *,
    admin_name: str,
    admin_email: str,
    admin_password: str,
    email_domain: str | None = None,
) -> User:
    admin_email = admin_email.lower().strip()
    if email_domain and not email_matches_domain(admin_email, email_domain):
        raise ValueError(f"Admin email must use @{normalize_domain(email_domain)}")
    existing = db.query(User).filter(User.email == admin_email).first()
    if existing:
        member = (
            db.query(WorkspaceMember)
            .filter(WorkspaceMember.workspace_id == workspace.id, WorkspaceMember.user_id == existing.id)
            .first()
        )
        if not member:
            db.add(
                WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=existing.id,
                    role=TEAM_LEAD,
                )
            )
        return existing

    user = User(
        email=admin_email,
        full_name=admin_name,
        password_hash=hash_password(admin_password),
        is_super_admin=False,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        WorkspaceMember(
                    workspace_id=workspace.id,
            user_id=user.id,
            role=TEAM_LEAD,
        )
    )
    return user


def get_team_lead_user(db: Session, workspace_id: UUID) -> User | None:
    member = (
        db.query(WorkspaceMember)
        .join(User)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.role == TEAM_LEAD)
        .order_by(WorkspaceMember.joined_at.asc())
        .first()
    )
    return member.user if member else None
