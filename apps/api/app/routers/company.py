from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.deps import CompanyAdminDep, CompanyAuthDep, CompanyWriterDep, DbDep
from models import Company, CompanyMember, CompanySettings, PipelineRun, Project, User
from models.company_portal import MemberIntegrationAccess
from models.platform import CompanyPlatformIntegration, CompanyPlatformService, PlatformIntegration, PlatformService
from schemas.company import (
    CompanyDashboardResponse,
    CompanyIntegrationCatalogItem,
    CompanyIntegrationConnectRequest,
    CompanyIntegrationTestResponse,
    CompanyMemberCreateRequest,
    CompanyMemberResponse,
    CompanyMemberUpdateRequest,
    CompanyServiceItem,
    CompanySettingsResponse,
    CompanySettingsUpdateRequest,
    MemberIntegrationAccessItem,
    MemberIntegrationsAccessUpdate,
    MyIntegrationItem,
    ChangePasswordRequest,
    PipelineRunSummary,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectSummary,
    ProjectUpdateRequest,
    UserDashboardResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
    IntegrationStatusSummary,
)
from services.auth import hash_password, verify_password
from services.company_access import set_company_email_domain
from services.company_domain import email_matches_domain, normalize_domain
from services.member_integrations import (
    get_member_connection,
    member_integration_to_dict,
    save_member_connection,
)
from services.platform_helpers import integration_is_assignable, service_is_assignable
from services.secrets import decrypt_secrets

router = APIRouter(prefix="/api/company", tags=["company"])


def _get_company_settings(db: Session, company_id) -> CompanySettings | None:
    return db.query(CompanySettings).filter(CompanySettings.company_id == company_id).first()


def _require_email_domain(db: Session, company_id) -> str:
    settings = _get_company_settings(db, company_id)
    if not settings or not settings.email_domain:
        raise HTTPException(400, "Configure your company email domain in Settings before adding employees")
    return settings.email_domain


def _granted_integration_ids(db: Session, company_id) -> set:
    rows = (
        db.query(CompanyPlatformIntegration)
        .filter(
            CompanyPlatformIntegration.company_id == company_id,
            CompanyPlatformIntegration.is_enabled.is_(True),
        )
        .all()
    )
    return {r.platform_integration_id for r in rows}


def _list_granted_integrations(db: Session, company_id) -> list[PlatformIntegration]:
    granted = _granted_integration_ids(db, company_id)
    integrations = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .order_by(PlatformIntegration.category, PlatformIntegration.name)
        .all()
    )
    return [i for i in integrations if i.id in granted and integration_is_assignable(i)]


def _assigned_integration_ids(db: Session, company_id, user_id) -> set:
    rows = (
        db.query(MemberIntegrationAccess)
        .filter(
            MemberIntegrationAccess.company_id == company_id,
            MemberIntegrationAccess.user_id == user_id,
            MemberIntegrationAccess.is_enabled.is_(True),
        )
        .all()
    )
    return {r.platform_integration_id for r in rows}


def _get_granted_integration(db: Session, company_id, key: str) -> PlatformIntegration:
    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == key)
        .first()
    )
    if not integration:
        raise HTTPException(404, "Integration not found")
    granted = _granted_integration_ids(db, company_id)
    if integration.id not in granted or not integration_is_assignable(integration):
        raise HTTPException(403, "Integration not granted to your company")
    return integration


def _get_assigned_integration(db: Session, company_id, user_id, key: str) -> PlatformIntegration:
    integration = _get_granted_integration(db, company_id, key)
    assigned = _assigned_integration_ids(db, company_id, user_id)
    if integration.id not in assigned:
        raise HTTPException(403, "This integration has not been assigned to you")
    return integration


@router.get("/settings", response_model=CompanySettingsResponse)
def get_company_settings(ctx: CompanyAuthDep, db: DbDep):
    settings = _get_company_settings(db, ctx.company_id)
    return CompanySettingsResponse(
        email_domain=settings.email_domain if settings else None,
        timezone=settings.timezone if settings else "UTC",
    )


@router.patch("/settings", response_model=CompanySettingsResponse)
def update_company_settings(body: CompanySettingsUpdateRequest, ctx: CompanyAdminDep, db: DbDep):
    company = db.query(Company).options(joinedload(Company.settings)).filter(Company.id == ctx.company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")
    try:
        set_company_email_domain(db, company, body.email_domain)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    settings = _get_company_settings(db, ctx.company_id)
    return CompanySettingsResponse(
        email_domain=settings.email_domain if settings else None,
        timezone=settings.timezone if settings else "UTC",
    )


@router.get("/dashboard", response_model=CompanyDashboardResponse)
def company_dashboard(ctx: CompanyAuthDep, db: DbDep):
    co = db.query(Company).options(joinedload(Company.settings)).filter(Company.id == ctx.company_id).first()
    if not co:
        return CompanyDashboardResponse(
            company_name="",
            company_slug="",
            role=ctx.member_role or "member",
            email_domain=None,
            projects_count=0,
            integrations_enabled=0,
            services_enabled=0,
            team_count=0,
        )

    projects_count = db.query(func.count(Project.id)).filter(Project.company_id == co.id).scalar() or 0
    integrations_enabled = len(_list_granted_integrations(db, co.id))
    services_enabled = (
        db.query(func.count(CompanyPlatformService.platform_service_id))
        .filter(
            CompanyPlatformService.company_id == co.id,
            CompanyPlatformService.is_enabled.is_(True),
        )
        .scalar()
        or 0
    )
    team_count = db.query(func.count(CompanyMember.id)).filter(CompanyMember.company_id == co.id).scalar() or 0

    return CompanyDashboardResponse(
        company_name=co.name,
        company_slug=co.slug,
        role=ctx.member_role or "member",
        email_domain=co.settings.email_domain if co.settings else None,
        projects_count=projects_count,
        integrations_enabled=integrations_enabled,
        services_enabled=services_enabled,
        team_count=team_count,
    )


@router.get("/user-dashboard", response_model=UserDashboardResponse)
def user_dashboard(ctx: CompanyAuthDep, db: DbDep):
    co = (
        db.query(Company)
        .options(joinedload(Company.settings))
        .filter(Company.id == ctx.company_id)
        .first()
    )
    assigned_ids = _assigned_integration_ids(db, ctx.company_id, ctx.user.id)
    connected_count = 0
    integration_status: list[IntegrationStatusSummary] = []
    for integration in _list_granted_integrations(db, ctx.company_id):
        if integration.id not in assigned_ids:
            continue
        conn = get_member_connection(db, ctx.company_id, ctx.user.id, integration.id)
        is_connected = bool(conn and conn.status == "connected")
        if is_connected:
            connected_count += 1
        integration_status.append(
            IntegrationStatusSummary(
                integration_key=integration.integration_key,
                name=integration.name,
                is_connected=is_connected,
                connection_status=conn.status if conn else "not_configured",
            )
        )

    my_projects_count = (
        db.query(func.count(Project.id))
        .filter(Project.company_id == ctx.company_id, Project.created_by == ctx.user.id)
        .scalar()
        or 0
    )
    company_projects_count = (
        db.query(func.count(Project.id)).filter(Project.company_id == ctx.company_id).scalar() or 0
    )
    services_enabled = (
        db.query(func.count(CompanyPlatformService.platform_service_id))
        .filter(
            CompanyPlatformService.company_id == ctx.company_id,
            CompanyPlatformService.is_enabled.is_(True),
        )
        .scalar()
        or 0
    )

    recent = (
        db.query(Project)
        .filter(Project.company_id == ctx.company_id)
        .order_by(Project.created_at.desc())
        .limit(5)
        .all()
    )
    creator_ids = {p.created_by for p in recent}
    creators = {
        u.id: u.full_name
        for u in db.query(User).filter(User.id.in_(creator_ids)).all()
    } if creator_ids else {}

    return UserDashboardResponse(
        company_name=co.name if co else "",
        company_slug=co.slug if co else "",
        role=ctx.member_role or "member",
        email_domain=co.settings.email_domain if co and co.settings else None,
        my_projects_count=my_projects_count,
        company_projects_count=company_projects_count,
        integrations_assigned=len(assigned_ids),
        integrations_connected=connected_count,
        services_enabled=services_enabled,
        recent_projects=[
            ProjectSummary(
                id=p.id,
                name=p.name,
                status=p.status,
                frontend_stack=p.frontend_stack,
                backend_stack=p.backend_stack,
                created_at=p.created_at,
                created_by_name=creators.get(p.created_by),
            )
            for p in recent
        ],
        integration_status=integration_status,
    )


@router.get("/profile", response_model=UserProfileResponse)
def get_profile(ctx: CompanyAuthDep, db: DbDep):
    member = (
        db.query(CompanyMember)
        .filter(CompanyMember.company_id == ctx.company_id, CompanyMember.user_id == ctx.user.id)
        .first()
    )
    if not member:
        raise HTTPException(404, "Membership not found")
    assigned = len(_assigned_integration_ids(db, ctx.company_id, ctx.user.id))
    connected = 0
    for iid in _assigned_integration_ids(db, ctx.company_id, ctx.user.id):
        conn = get_member_connection(db, ctx.company_id, ctx.user.id, iid)
        if conn and conn.status == "connected":
            connected += 1
    return UserProfileResponse(
        id=ctx.user.id,
        email=ctx.user.email,
        full_name=ctx.user.full_name,
        role=member.role,
        is_active=ctx.user.is_active,
        joined_at=member.joined_at,
        integrations_assigned=assigned,
        integrations_connected=connected,
    )


@router.patch("/profile", response_model=UserProfileResponse)
def update_profile(body: UserProfileUpdateRequest, ctx: CompanyAuthDep, db: DbDep):
    ctx.user.full_name = body.full_name.strip()
    db.commit()
    db.refresh(ctx.user)
    return get_profile(ctx, db)


@router.post("/profile/password")
def change_password(body: ChangePasswordRequest, ctx: CompanyAuthDep, db: DbDep):
    if not verify_password(body.current_password, ctx.user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    ctx.user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"success": True, "message": "Password updated successfully"}


@router.get("/integrations", response_model=list[CompanyIntegrationCatalogItem])
def company_integrations_catalog(ctx: CompanyAdminDep, db: DbDep):
    return [
        CompanyIntegrationCatalogItem(
            integration_key=i.integration_key,
            name=i.name,
            description=i.description,
            category=i.category,
            auth_type=i.auth_type,
            is_granted=True,
        )
        for i in _list_granted_integrations(db, ctx.company_id)
    ]


@router.get("/my-integrations", response_model=list[MyIntegrationItem])
def my_integrations(ctx: CompanyAuthDep, db: DbDep):
    assigned = _assigned_integration_ids(db, ctx.company_id, ctx.user.id)
    items = []
    for integration in _list_granted_integrations(db, ctx.company_id):
        if integration.id not in assigned:
            continue
        conn = get_member_connection(db, ctx.company_id, ctx.user.id, integration.id)
        data = member_integration_to_dict(
            integration, conn, is_granted=True, is_assigned=True
        )
        items.append(MyIntegrationItem(**data))
    return items


@router.get("/my-integrations/{key}", response_model=MyIntegrationItem)
def get_my_integration(key: str, ctx: CompanyAuthDep, db: DbDep):
    integration = _get_assigned_integration(db, ctx.company_id, ctx.user.id, key)
    conn = get_member_connection(db, ctx.company_id, ctx.user.id, integration.id)
    return MyIntegrationItem(
        **member_integration_to_dict(integration, conn, is_granted=True, is_assigned=True)
    )


@router.put("/my-integrations/{key}/connection", response_model=MyIntegrationItem)
def connect_my_integration(
    key: str, body: CompanyIntegrationConnectRequest, ctx: CompanyWriterDep, db: DbDep
):
    integration = _get_assigned_integration(db, ctx.company_id, ctx.user.id, key)
    conn = save_member_connection(
        db,
        ctx.company_id,
        ctx.user.id,
        integration,
        body.connection_name,
        body.config,
    )
    return MyIntegrationItem(
        **member_integration_to_dict(integration, conn, is_granted=True, is_assigned=True)
    )


@router.post("/my-integrations/{key}/test", response_model=CompanyIntegrationTestResponse)
def test_my_integration(key: str, ctx: CompanyWriterDep, db: DbDep):
    integration = _get_assigned_integration(db, ctx.company_id, ctx.user.id, key)
    conn = get_member_connection(db, ctx.company_id, ctx.user.id, integration.id)
    if not conn or not conn.encrypted_config_ref:
        return CompanyIntegrationTestResponse(success=False, message="No connection configured")
    secrets = decrypt_secrets(conn.encrypted_config_ref)
    success = bool(secrets or conn.config_metadata_json)
    conn.last_tested_at = datetime.now(UTC)
    conn.last_test_status = success
    conn.status = "connected" if success else "error"
    conn.last_error_message = None if success else "Missing required credentials"
    db.commit()
    return CompanyIntegrationTestResponse(
        success=success,
        message="Connection verified successfully" if success else "Connection test failed",
    )


@router.delete("/my-integrations/{key}/connection", response_model=MyIntegrationItem)
def disconnect_my_integration(key: str, ctx: CompanyWriterDep, db: DbDep):
    integration = _get_assigned_integration(db, ctx.company_id, ctx.user.id, key)
    conn = get_member_connection(db, ctx.company_id, ctx.user.id, integration.id)
    if conn:
        db.delete(conn)
        db.commit()
    return MyIntegrationItem(
        **member_integration_to_dict(integration, None, is_granted=True, is_assigned=True)
    )


@router.get("/services", response_model=list[CompanyServiceItem])
def company_services(ctx: CompanyAuthDep, db: DbDep):
    access_map = {
        row.platform_service_id: row.is_enabled
        for row in db.query(CompanyPlatformService)
        .filter(CompanyPlatformService.company_id == ctx.company_id)
        .all()
    }
    services = db.query(PlatformService).order_by(PlatformService.display_name).all()
    return [
        CompanyServiceItem(service_key=s.service_key, display_name=s.display_name, is_granted=True)
        for s in services
        if access_map.get(s.id, False) and service_is_assignable(s)
    ]


@router.get("/members", response_model=list[CompanyMemberResponse])
def list_members(ctx: CompanyAdminDep, db: DbDep):
    members = (
        db.query(CompanyMember)
        .join(User)
        .filter(CompanyMember.company_id == ctx.company_id)
        .order_by(CompanyMember.joined_at.asc())
        .all()
    )
    return [_member_response(db, m) for m in members]


@router.post("/members", response_model=CompanyMemberResponse, status_code=201)
def create_member(body: CompanyMemberCreateRequest, ctx: CompanyAdminDep, db: DbDep):
    if body.role not in ("admin", "member", "viewer"):
        raise HTTPException(400, "Invalid role")
    email_domain = _require_email_domain(db, ctx.company_id)
    email = body.email.lower().strip()
    if not email_matches_domain(email, email_domain):
        raise HTTPException(
            400,
            f"Employee email must use your company domain @{normalize_domain(email_domain)}",
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name=body.full_name.strip(),
            password_hash=hash_password(body.password),
            is_super_admin=False,
            is_active=True,
        )
        db.add(user)
        db.flush()
    elif user.is_super_admin:
        raise HTTPException(400, "Cannot add platform super admin as company member")
    elif not email_matches_domain(user.email, email_domain):
        raise HTTPException(400, f"Existing user email must match @{normalize_domain(email_domain)}")

    existing = (
        db.query(CompanyMember)
        .filter(CompanyMember.company_id == ctx.company_id, CompanyMember.user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(400, "User is already a member of this company")

    member = CompanyMember(company_id=ctx.company_id, user_id=user.id, role=body.role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return _member_response(db, member)


@router.get("/members/{member_id}", response_model=CompanyMemberResponse)
def get_member(member_id: str, ctx: CompanyAuthDep, db: DbDep):
    member = _get_member(db, ctx.company_id, member_id)
    if ctx.member_role != "admin" and member.user_id != ctx.user.id:
        raise HTTPException(403, "Not allowed to view this member")
    return _member_response(db, member)


@router.patch("/members/{member_id}", response_model=CompanyMemberResponse)
def update_member(member_id: str, body: CompanyMemberUpdateRequest, ctx: CompanyAdminDep, db: DbDep):
    member = _get_member(db, ctx.company_id, member_id)
    user = db.query(User).filter(User.id == member.user_id).first()
    if body.role is not None:
        if body.role not in ("admin", "member", "viewer"):
            raise HTTPException(400, "Invalid role")
        member.role = body.role
    if body.is_active is not None and user:
        user.is_active = body.is_active
    db.commit()
    db.refresh(member)
    return _member_response(db, member)


@router.get("/members/{member_id}/integrations", response_model=list[MemberIntegrationAccessItem])
def get_member_integrations(member_id: str, ctx: CompanyAuthDep, db: DbDep):
    member = _get_member(db, ctx.company_id, member_id)
    if ctx.member_role != "admin" and member.user_id != ctx.user.id:
        raise HTTPException(403, "Not allowed to view this member's integrations")

    assigned = {
        row.platform_integration_id: row.is_enabled
        for row in db.query(MemberIntegrationAccess)
        .filter(
            MemberIntegrationAccess.company_id == ctx.company_id,
            MemberIntegrationAccess.user_id == member.user_id,
        )
        .all()
    }
    items = []
    for integration in _list_granted_integrations(db, ctx.company_id):
        conn = get_member_connection(db, ctx.company_id, member.user_id, integration.id)
        is_connected = bool(conn and conn.status == "connected")
        items.append(
            MemberIntegrationAccessItem(
                integration_key=integration.integration_key,
                name=integration.name,
                category=integration.category,
                is_connected=is_connected,
                is_assigned=assigned.get(integration.id, False),
            )
        )
    return items


@router.put("/members/{member_id}/integrations", response_model=list[MemberIntegrationAccessItem])
def update_member_integrations(
    member_id: str, body: MemberIntegrationsAccessUpdate, ctx: CompanyAdminDep, db: DbDep
):
    member = _get_member(db, ctx.company_id, member_id)
    key_to_integration = {i.integration_key: i for i in _list_granted_integrations(db, ctx.company_id)}

    for item in body.integrations:
        integration = key_to_integration.get(item.integration_key)
        if not integration:
            raise HTTPException(400, f"Integration not granted: {item.integration_key}")
        row = (
            db.query(MemberIntegrationAccess)
            .filter(
                MemberIntegrationAccess.company_id == ctx.company_id,
                MemberIntegrationAccess.user_id == member.user_id,
                MemberIntegrationAccess.platform_integration_id == integration.id,
            )
            .first()
        )
        if item.is_assigned:
            if row:
                row.is_enabled = True
            else:
                db.add(
                    MemberIntegrationAccess(
                        company_id=ctx.company_id,
                        user_id=member.user_id,
                        platform_integration_id=integration.id,
                        is_enabled=True,
                        granted_by_user_id=ctx.user.id,
                    )
                )
        elif row:
            db.delete(row)

    db.commit()
    return get_member_integrations(member_id, ctx, db)


def _max_projects(db: Session, company: Company) -> int:
    company = (
        db.query(Company)
        .options(joinedload(Company.plan), joinedload(Company.limits))
        .filter(Company.id == company.id)
        .first()
    )
    if company and company.limits and company.limits.max_projects is not None:
        return company.limits.max_projects
    if company and company.plan:
        return company.plan.max_projects
    return 5


def _project_response(db: Session, project: Project) -> ProjectResponse:
    creator = db.query(User).filter(User.id == project.created_by).first()
    runs_count = (
        db.query(func.count(PipelineRun.id)).filter(PipelineRun.project_id == project.id).scalar() or 0
    )
    active_runs = (
        db.query(func.count(PipelineRun.id))
        .filter(PipelineRun.project_id == project.id, PipelineRun.status.in_(["pending", "running"]))
        .scalar()
        or 0
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        frontend_stack=project.frontend_stack,
        backend_stack=project.backend_stack,
        db_type=project.db_type,
        vcs_provider=project.vcs_provider,
        pm_tool=project.pm_tool,
        notification_channels=project.notification_channels or [],
        monthly_token_budget_usd=float(project.monthly_token_budget_usd)
        if project.monthly_token_budget_usd is not None
        else None,
        created_by=project.created_by,
        created_by_name=creator.full_name if creator else None,
        created_at=project.created_at,
        updated_at=project.updated_at,
        pipeline_runs_count=runs_count,
        active_pipeline_runs=active_runs,
    )


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(ctx: CompanyAuthDep, db: DbDep):
    projects = (
        db.query(Project)
        .filter(Project.company_id == ctx.company_id)
        .order_by(Project.updated_at.desc())
        .all()
    )
    creator_ids = {p.created_by for p in projects}
    creators = {
        u.id: u.full_name for u in db.query(User).filter(User.id.in_(creator_ids)).all()
    } if creator_ids else {}
    return [
        ProjectSummary(
            id=p.id,
            name=p.name,
            status=p.status,
            frontend_stack=p.frontend_stack,
            backend_stack=p.backend_stack,
            created_at=p.created_at,
            created_by_name=creators.get(p.created_by),
        )
        for p in projects
    ]


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(body: ProjectCreateRequest, ctx: CompanyWriterDep, db: DbDep):
    company = (
        db.query(Company)
        .options(joinedload(Company.plan), joinedload(Company.limits))
        .filter(Company.id == ctx.company_id)
        .first()
    )
    if not company:
        raise HTTPException(404, "Company not found")
    current_count = (
        db.query(func.count(Project.id)).filter(Project.company_id == ctx.company_id).scalar() or 0
    )
    if current_count >= _max_projects(db, company):
        raise HTTPException(400, "Project limit reached for your company plan")

    name = body.name.strip()
    if db.query(Project).filter(Project.company_id == ctx.company_id, Project.name == name).first():
        raise HTTPException(400, "A project with this name already exists")

    project = Project(
        company_id=ctx.company_id,
        created_by=ctx.user.id,
        name=name,
        description=body.description,
        status="draft",
        frontend_stack=body.frontend_stack,
        backend_stack=body.backend_stack,
        db_type=body.db_type,
        vcs_provider=body.vcs_provider,
        pm_tool=body.pm_tool,
        notification_channels=body.notification_channels,
        monthly_token_budget_usd=body.monthly_token_budget_usd,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_response(db, project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, ctx: CompanyAuthDep, db: DbDep):
    project = _get_project(db, ctx.company_id, project_id)
    return _project_response(db, project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, body: ProjectUpdateRequest, ctx: CompanyWriterDep, db: DbDep):
    project = _get_project(db, ctx.company_id, project_id)
    if body.name is not None:
        name = body.name.strip()
        existing = (
            db.query(Project)
            .filter(Project.company_id == ctx.company_id, Project.name == name, Project.id != project.id)
            .first()
        )
        if existing:
            raise HTTPException(400, "A project with this name already exists")
        project.name = name
    if body.description is not None:
        project.description = body.description
    if body.status is not None:
        if body.status not in ("draft", "active", "paused", "completed", "failed", "archived"):
            raise HTTPException(400, "Invalid project status")
        project.status = body.status
    for field in (
        "frontend_stack",
        "backend_stack",
        "db_type",
        "vcs_provider",
        "pm_tool",
        "notification_channels",
        "monthly_token_budget_usd",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return _project_response(db, project)


@router.get("/projects/{project_id}/runs", response_model=list[PipelineRunSummary])
def list_project_runs(project_id: str, ctx: CompanyAuthDep, db: DbDep):
    project = _get_project(db, ctx.company_id, project_id)
    runs = (
        db.query(PipelineRun)
        .filter(PipelineRun.project_id == project.id)
        .order_by(PipelineRun.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        PipelineRunSummary(
            id=r.id,
            status=r.status,
            current_step=r.current_step,
            started_at=r.started_at,
            finished_at=r.finished_at,
            error_message=r.error_message,
            created_at=r.created_at,
        )
        for r in runs
    ]


def _get_project(db: Session, company_id, project_id: str) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.company_id == company_id)
        .first()
    )
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _get_member(db: Session, company_id, member_id: str) -> CompanyMember:
    member = (
        db.query(CompanyMember)
        .filter(CompanyMember.id == member_id, CompanyMember.company_id == company_id)
        .first()
    )
    if not member:
        raise HTTPException(404, "Member not found")
    return member


def _member_response(db: Session, member: CompanyMember) -> CompanyMemberResponse:
    user = db.query(User).filter(User.id == member.user_id).first()
    assigned_count = (
        db.query(func.count(MemberIntegrationAccess.platform_integration_id))
        .filter(
            MemberIntegrationAccess.company_id == member.company_id,
            MemberIntegrationAccess.user_id == member.user_id,
            MemberIntegrationAccess.is_enabled.is_(True),
        )
        .scalar()
        or 0
    )
    return CompanyMemberResponse(
        id=member.id,
        user_id=member.user_id,
        email=user.email if user else "",
        full_name=user.full_name if user else "",
        role=member.role,
        is_active=user.is_active if user else False,
        integrations_assigned=assigned_count,
        joined_at=member.joined_at,
    )
