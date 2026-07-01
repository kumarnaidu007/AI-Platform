from sqlalchemy.orm import Session, joinedload

from constants.roles import TEAM_LEAD, TEAM_MEMBER
from models import Plan, User, Workspace, WorkspaceMember, WorkspaceSettings
from models.platform import PlatformService
from services.auth import hash_password, verify_password
from services.workspace_access import provision_workspace
from services.workspace_helpers import DEFAULT_WORKSPACE_SLUG

ADMIN_EMAIL = "superadmin@platform.io"
ADMIN_PASSWORD = "Admin@123"
TEAM_LEAD_EMAIL = "lead@platform.io"
TEAM_LEAD_PASSWORD = "Welcome123!"
TEAM_MEMBER_EMAIL = "member@platform.io"
TEAM_MEMBER_PASSWORD = "Welcome123!"


def ensure_super_admin(db: Session) -> None:
    existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    password_hash = hash_password(ADMIN_PASSWORD)

    if existing:
        if not existing.is_super_admin or not existing.is_active:
            existing.is_super_admin = True
            existing.is_active = True
        if not verify_password(ADMIN_PASSWORD, existing.password_hash):
            existing.password_hash = password_hash
        db.commit()
        return

    db.add(
        User(
            email=ADMIN_EMAIL,
            full_name="Super Admin",
            password_hash=password_hash,
            is_super_admin=True,
            is_active=True,
        )
    )
    db.commit()


def ensure_default_workspace(db: Session) -> Workspace:
    workspace = db.query(Workspace).filter(Workspace.slug == DEFAULT_WORKSPACE_SLUG).first()
    if workspace:
        return workspace

    plan = db.query(Plan).filter(Plan.name == "Platform").first()
    if not plan:
        plan = db.query(Plan).first()
    if not plan:
        raise RuntimeError("No subscription plan found — run database init scripts")

    workspace = Workspace(name="AI Dev Platform", slug=DEFAULT_WORKSPACE_SLUG, status="active", plan_id=plan.id)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceSettings(workspace_id=workspace.id, email_domain=None, timezone="UTC"))
    db.commit()
    db.refresh(workspace)
    provision_workspace(db , workspace)
    return workspace


def _ensure_team_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    role: str,
    workspace: Workspace,
) -> User:
    user = db.query(User).filter(User.email == email).first()
    password_hash = hash_password(password)
    if not user:
        user = User(
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            is_super_admin=False,
            is_active=True,
        )
        db.add(user)
        db.flush()
    elif not verify_password(password, user.password_hash):
        user.password_hash = password_hash

    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace.id, WorkspaceMember.user_id == user.id)
        .first()
    )
    if not membership:
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role))
    else:
        membership.role = role

    db.commit()
    return user


def ensure_workspace_team(db: Session) -> None:
    workspace = ensure_default_workspace(db)
    _ensure_team_user(
        db,
        email=TEAM_LEAD_EMAIL,
        password=TEAM_LEAD_PASSWORD,
        full_name="Team Lead",
        role=TEAM_LEAD,
        workspace=workspace,
    )
    _ensure_team_user(
        db,
        email=TEAM_MEMBER_EMAIL,
        password=TEAM_MEMBER_PASSWORD,
        full_name="Team Member",
        role=TEAM_MEMBER,
        workspace=workspace,
    )


def ensure_azure_foundry_service(db: Session) -> None:
    service = db.query(PlatformService).filter(PlatformService.service_key == "azure_foundry").first()
    if service:
        return
    db.add(
        PlatformService(
            service_key="azure_foundry",
            display_name="Microsoft Foundry",
            description="Azure AI Foundry project endpoint — powers all agents via your deployed models",
            is_enabled=False,
            config_metadata_json={
                "deployment_name": "claude-sonnet-4-6",
                "embedding_deployment": "text-embedding-3-small",
            },
        )
    )
    db.commit()


def _apply_schema_patches(db: Session) -> None:
    """Idempotent DDL for databases created before newer init scripts."""
    from sqlalchemy import text

    db.execute(text("ALTER TYPE pipeline_status ADD VALUE IF NOT EXISTS 'awaiting_approval'"))
    db.execute(
        text(
            "ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS "
            "started_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL"
        )
    )
    db.execute(text("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS approval_plan_json JSONB"))
    db.execute(text("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS graph_state_json JSONB"))
    db.execute(
        text(
            "ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS "
            "review_retry_count INTEGER NOT NULL DEFAULT 0"
        )
    )
    _apply_requirements_schema(db)
    _apply_encrypted_config_text(db)
    _apply_pending_publish_schema(db)
    _apply_jira_team_workflow_schema(db)
    db.commit()


def _apply_jira_team_workflow_schema(db: Session) -> None:
    from pathlib import Path

    from sqlalchemy import text

    path = Path(__file__).resolve().parent / "migrations" / "18_jira_team_workflow.sql"
    if path.exists():
        db.execute(text(path.read_text(encoding="utf-8")))


def _apply_pending_publish_schema(db: Session) -> None:
    from pathlib import Path

    from sqlalchemy import text

    path = Path(__file__).resolve().parent / "migrations" / "17_pending_publish.sql"
    if path.exists():
        db.execute(text(path.read_text(encoding="utf-8")))


def _apply_encrypted_config_text(db: Session) -> None:
    from pathlib import Path

    from sqlalchemy import text

    path = Path(__file__).resolve().parent / "migrations" / "16_encrypted_config_text.sql"
    if path.exists():
        db.execute(text(path.read_text(encoding="utf-8")))


def _apply_requirements_schema(db: Session) -> None:
    from sqlalchemy import text

    db.execute(text(open(_requirements_sql_path(), encoding="utf-8").read()))


def _requirements_sql_path() -> str:
    from pathlib import Path

    local = Path(__file__).resolve().parent / "migrations" / "15_requirements_intake.sql"
    if local.exists():
        return str(local)
    repo = Path(__file__).resolve().parents[3] / "infra" / "db" / "init" / "15_requirements_intake.sql"
    if repo.exists():
        return str(repo)
    raise FileNotFoundError("15_requirements_intake.sql not found")


def bootstrap_platform(db: Session) -> None:
    _apply_schema_patches(db)
    ensure_super_admin(db)
    ensure_azure_foundry_service(db)
    workspace = ensure_default_workspace(db)
    provision_workspace(db, workspace)
    ensure_workspace_team(db)
