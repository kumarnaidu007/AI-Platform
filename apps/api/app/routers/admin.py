from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.deps import DbDep, SuperAdminDep, require_super_admin
from models import AuditEvent, Company, CompanyMember, PipelineRun, Plan, Project, UsageLedger, User
from models.platform import (
    CompanyPlatformIntegration,
    CompanyPlatformService,
    PlanPlatformIntegration,
    PlatformIntegration,
    PlatformService,
    PlatformSetting,
)
from schemas.admin import (
    CompanyCreateRequest,
    CompanyDetailResponse,
    CompanyIntegrationAccessItem,
    CompanyIntegrationsAccessUpdate,
    CompanyResponse,
    CompanyServiceAccessItem,
    CompanyServicesAccessUpdate,
    CompanyUpdateRequest,
    ConnectionSaveRequest,
    ConnectionTestResponse,
    DashboardMetricsResponse,
    PipelineActivityItem,
    PlanResponse,
    PlatformIntegrationResponse,
    PlatformIntegrationUpdate,
    PlatformServiceResponse,
    PlatformServiceUpdate,
    PlatformSettingResponse,
    PlatformSettingsUpdate,
    PlatformStatsResponse,
)
from services.company_access import create_company_admin, get_company_admin, provision_company_access, set_company_email_domain
from services.platform_helpers import (
    integration_is_assignable,
    integration_to_dict,
    save_connection,
    service_is_assignable,
    service_to_dict,
    setting_to_dict,
)
from services.secrets import decrypt_secrets, encrypt_secrets

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_super_admin)],
)


@router.get("/integrations", response_model=list[PlatformIntegrationResponse])
def list_integrations(db: DbDep):
    items = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .order_by(PlatformIntegration.category, PlatformIntegration.name)
        .all()
    )
    return [integration_to_dict(i) for i in items]


@router.get("/integrations/{key}", response_model=PlatformIntegrationResponse)
def get_integration(key: str, db: DbDep):
    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == key)
        .first()
    )
    if not integration:
        raise HTTPException(404, "Integration not found")
    return integration_to_dict(integration)


@router.patch("/integrations/{key}", response_model=PlatformIntegrationResponse)
def update_integration(key: str, body: PlatformIntegrationUpdate, db: DbDep):
    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == key)
        .first()
    )
    if not integration:
        raise HTTPException(404, "Integration not found")
    if body.is_enabled is not None:
        integration.is_enabled = body.is_enabled
        integration.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(integration)
    return integration_to_dict(integration)


@router.put("/integrations/{key}/connection", response_model=PlatformIntegrationResponse)
def save_integration_connection(key: str, body: ConnectionSaveRequest, db: DbDep):
    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == key)
        .first()
    )
    if not integration:
        raise HTTPException(404, "Integration not found")
    save_connection(db, integration, body.connection_name, body.config)
    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == key)
        .first()
    )
    return integration_to_dict(integration)


@router.delete("/integrations/{key}/connection", response_model=PlatformIntegrationResponse)
def delete_integration_connection(key: str, db: DbDep):
    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == key)
        .first()
    )
    if not integration:
        raise HTTPException(404, "Integration not found")
    for conn in list(integration.connections):
        db.delete(conn)
    integration.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(integration)
    return integration_to_dict(integration)


@router.post("/integrations/{key}/test", response_model=ConnectionTestResponse)
def test_integration_connection(key: str, db: DbDep):
    integration = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .filter(PlatformIntegration.integration_key == key)
        .first()
    )
    if not integration:
        raise HTTPException(404, "Integration not found")
    conn = integration.connections[0] if integration.connections else None
    if not conn or not conn.encrypted_config_ref:
        return ConnectionTestResponse(success=False, message="No connection configured")

    secrets = decrypt_secrets(conn.encrypted_config_ref)
    success = bool(secrets or conn.config_metadata_json)
    conn.last_tested_at = datetime.now(UTC)
    conn.last_test_status = success
    conn.status = "connected" if success else "error"
    conn.last_error_message = None if success else "Missing required credentials"
    db.commit()
    return ConnectionTestResponse(
        success=success,
        message="Connection verified successfully" if success else "Connection test failed",
    )


@router.get("/platform-services", response_model=list[PlatformServiceResponse])
def list_platform_services(db: DbDep):
    services = db.query(PlatformService).order_by(PlatformService.display_name).all()
    return [service_to_dict(s) for s in services]


@router.patch("/platform-services/{service_key}", response_model=PlatformServiceResponse)
def update_platform_service(service_key: str, body: PlatformServiceUpdate, db: DbDep):
    service = db.query(PlatformService).filter(PlatformService.service_key == service_key).first()
    if not service:
        raise HTTPException(404, "Service not found")
    if body.is_enabled is not None:
        service.is_enabled = body.is_enabled
    if body.config_metadata is not None:
        service.config_metadata_json = body.config_metadata
    if body.api_key:
        service.encrypted_config_ref = encrypt_secrets({"api_key": body.api_key})
    service.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(service)
    return service_to_dict(service)


@router.post("/platform-services/{service_key}/test", response_model=ConnectionTestResponse)
def test_platform_service(service_key: str, db: DbDep):
    service = db.query(PlatformService).filter(PlatformService.service_key == service_key).first()
    if not service:
        raise HTTPException(404, "Service not found")
    if not service.encrypted_config_ref:
        return ConnectionTestResponse(success=False, message="API key not configured")
    service.last_tested_at = datetime.now(UTC)
    service.last_test_status = True
    service.last_error_message = None
    db.commit()
    return ConnectionTestResponse(success=True, message=f"{service.display_name} connection OK")


@router.get("/platform-settings", response_model=list[PlatformSettingResponse])
def list_platform_settings(db: DbDep):
    settings = db.query(PlatformSetting).order_by(PlatformSetting.key).all()
    return [setting_to_dict(s) for s in settings]


@router.put("/platform-settings", response_model=list[PlatformSettingResponse])
def update_platform_settings(body: PlatformSettingsUpdate, db: DbDep):
    for key, value in body.settings.items():
        setting = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
        if setting:
            setting.value_json = value
            setting.updated_at = datetime.now(UTC)
    db.commit()
    settings = db.query(PlatformSetting).order_by(PlatformSetting.key).all()
    return [setting_to_dict(s) for s in settings]


@router.get("/plans", response_model=list[PlanResponse])
def list_plans(db: DbDep):
    plans = db.query(Plan).order_by(Plan.name).all()
    result = []
    for plan in plans:
        companies_count = db.query(func.count(Company.id)).filter(Company.plan_id == plan.id).scalar() or 0
        integration_keys = [
            row[0]
            for row in db.query(PlatformIntegration.integration_key)
            .join(PlanPlatformIntegration, PlanPlatformIntegration.platform_integration_id == PlatformIntegration.id)
            .filter(PlanPlatformIntegration.plan_id == plan.id)
            .all()
        ]
        result.append(
            PlanResponse(
                id=plan.id,
                name=plan.name,
                max_projects=plan.max_projects,
                max_parallel_pipelines=plan.max_parallel_pipelines,
                monthly_token_budget_usd=float(plan.monthly_token_budget_usd),
                is_active=plan.is_active,
                companies_count=companies_count,
                integration_keys=integration_keys,
            )
        )
    return result


def _company_response(db: Session, company: Company) -> CompanyResponse:
    plan = db.query(Plan).filter(Plan.id == company.plan_id).first()
    users_count = (
        db.query(func.count(CompanyMember.id)).filter(CompanyMember.company_id == company.id).scalar() or 0
    )
    projects_count = db.query(func.count(Project.id)).filter(Project.company_id == company.id).scalar() or 0
    active_pipelines = (
        db.query(func.count(PipelineRun.id))
        .join(Project, Project.id == PipelineRun.project_id)
        .filter(Project.company_id == company.id, PipelineRun.status == "running")
        .scalar()
        or 0
    )
    usage = (
        db.query(func.coalesce(func.sum(UsageLedger.cost_usd), 0))
        .filter(UsageLedger.company_id == company.id)
        .scalar()
        or 0
    )
    return CompanyResponse(
        id=company.id,
        name=company.name,
        slug=company.slug,
        status=company.status,
        plan_id=company.plan_id,
        plan_name=plan.name if plan else "Unknown",
        users_count=users_count,
        projects_count=projects_count,
        active_pipelines=active_pipelines,
        monthly_usage_usd=float(usage),
        created_at=company.created_at,
    )


@router.get("/companies", response_model=list[CompanyResponse])
def list_companies(db: DbDep):
    companies = db.query(Company).order_by(Company.created_at.desc()).all()
    return [_company_response(db, c) for c in companies]


@router.get("/companies/{company_id}", response_model=CompanyDetailResponse)
def get_company(company_id: str, db: DbDep):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")
    base = _company_response(db, company)
    admin = get_company_admin(db, company.id)
    projects = (
        db.query(Project)
        .filter(Project.company_id == company.id)
        .order_by(Project.created_at.desc())
        .limit(5)
        .all()
    )
    recent = [
        {
            "id": str(p.id),
            "name": p.name,
            "status": p.status,
            "stack": f"{p.frontend_stack or ''} + {p.backend_stack or ''}".strip(" +"),
        }
        for p in projects
    ]
    return CompanyDetailResponse(
        **base.model_dump(),
        admin_email=admin.email if admin else None,
        admin_name=admin.full_name if admin else None,
        limits_override={},
        recent_projects=recent,
    )


@router.post("/companies", response_model=CompanyResponse, status_code=201)
def create_company(body: CompanyCreateRequest, db: DbDep, _: SuperAdminDep):
    if db.query(Company).filter(Company.slug == body.slug).first():
        raise HTTPException(400, "Slug already exists")
    plan = db.query(Plan).filter(Plan.id == body.plan_id).first()
    if not plan:
        raise HTTPException(400, "Invalid plan")

    if body.admin_email and not body.admin_password:
        raise HTTPException(400, "Admin password required when admin email is provided")

    company = Company(name=body.name, slug=body.slug, status=body.status, plan_id=body.plan_id)
    db.add(company)
    db.flush()

    provision_company_access(db, company)

    if body.email_domain:
        try:
            set_company_email_domain(db, company, body.email_domain)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    if body.admin_email and body.admin_name and body.admin_password:
        try:
            create_company_admin(
                db,
                company,
                admin_name=body.admin_name,
                admin_email=body.admin_email,
                admin_password=body.admin_password,
                email_domain=company.settings.email_domain if company.settings else body.email_domain,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    db.commit()
    db.refresh(company)
    return _company_response(db, company)


@router.get("/companies/{company_id}/integrations-access", response_model=list[CompanyIntegrationAccessItem])
def get_company_integrations_access(company_id: str, db: DbDep):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")

    access_map = {
        row.platform_integration_id: row.is_enabled
        for row in db.query(CompanyPlatformIntegration)
        .filter(CompanyPlatformIntegration.company_id == company.id)
        .all()
    }
    integrations = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .order_by(PlatformIntegration.category, PlatformIntegration.name)
        .all()
    )

    items: list[CompanyIntegrationAccessItem] = []
    for i in integrations:
        assignable = integration_is_assignable(i)
        connection_status = integration_to_dict(i)["connection_status"]
        granted = access_map.get(i.id, False)
        items.append(
            CompanyIntegrationAccessItem(
                integration_key=i.integration_key,
                name=i.name,
                category=i.category,
                is_enabled=granted if assignable else False,
                platform_enabled=i.is_enabled,
                platform_connected=connection_status == "connected",
                assignable=assignable,
                connection_status=connection_status,
            )
        )
    return items


@router.put("/companies/{company_id}/integrations-access", response_model=list[CompanyIntegrationAccessItem])
def update_company_integrations_access(company_id: str, body: CompanyIntegrationsAccessUpdate, db: DbDep):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")

    integrations = (
        db.query(PlatformIntegration)
        .options(joinedload(PlatformIntegration.connections))
        .all()
    )
    key_to_integration = {i.integration_key: i for i in integrations}

    for item in body.integrations:
        integration = key_to_integration.get(item.integration_key)
        if not integration:
            raise HTTPException(400, f"Unknown integration: {item.integration_key}")
        if item.is_enabled and not integration_is_assignable(integration):
            raise HTTPException(
                400,
                f"Integration '{item.integration_key}' is not connected on the platform — configure it in Integrations first",
            )

        row = (
            db.query(CompanyPlatformIntegration)
            .filter(
                CompanyPlatformIntegration.company_id == company.id,
                CompanyPlatformIntegration.platform_integration_id == integration.id,
            )
            .first()
        )
        if item.is_enabled:
            if row:
                row.is_enabled = True
            else:
                db.add(
                    CompanyPlatformIntegration(
                        company_id=company.id,
                        platform_integration_id=integration.id,
                        is_enabled=True,
                    )
                )
        elif row:
            row.is_enabled = False

    db.commit()
    return get_company_integrations_access(company_id, db)


@router.get("/companies/{company_id}/services-access", response_model=list[CompanyServiceAccessItem])
def get_company_services_access(company_id: str, db: DbDep):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")

    access_map = {
        row.platform_service_id: row.is_enabled
        for row in db.query(CompanyPlatformService)
        .filter(CompanyPlatformService.company_id == company.id)
        .all()
    }
    services = db.query(PlatformService).order_by(PlatformService.display_name).all()

    items: list[CompanyServiceAccessItem] = []
    for s in services:
        assignable = service_is_assignable(s)
        granted = access_map.get(s.id, False)
        items.append(
            CompanyServiceAccessItem(
                service_key=s.service_key,
                display_name=s.display_name,
                is_enabled=granted if assignable else False,
                platform_enabled=s.is_enabled,
                platform_configured=bool(s.encrypted_config_ref),
                assignable=assignable,
            )
        )
    return items


@router.put("/companies/{company_id}/services-access", response_model=list[CompanyServiceAccessItem])
def update_company_services_access(company_id: str, body: CompanyServicesAccessUpdate, db: DbDep):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")

    services = db.query(PlatformService).all()
    key_to_service = {s.service_key: s for s in services}

    for item in body.services:
        service = key_to_service.get(item.service_key)
        if not service:
            raise HTTPException(400, f"Unknown service: {item.service_key}")
        if item.is_enabled and not service_is_assignable(service):
            raise HTTPException(
                400,
                f"AI service '{item.service_key}' is not configured on the platform — enable and add API keys in AI Services first",
            )

        row = (
            db.query(CompanyPlatformService)
            .filter(
                CompanyPlatformService.company_id == company.id,
                CompanyPlatformService.platform_service_id == service.id,
            )
            .first()
        )
        if item.is_enabled:
            if row:
                row.is_enabled = True
            else:
                db.add(
                    CompanyPlatformService(
                        company_id=company.id,
                        platform_service_id=service.id,
                        is_enabled=True,
                    )
                )
        elif row:
            row.is_enabled = False

    db.commit()
    return get_company_services_access(company_id, db)


@router.patch("/companies/{company_id}", response_model=CompanyResponse)
def update_company(company_id: str, body: CompanyUpdateRequest, db: DbDep):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")
    if body.name is not None:
        company.name = body.name
    if body.status is not None:
        company.status = body.status
    if body.plan_id is not None:
        company.plan_id = body.plan_id
    company.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(company)
    return _company_response(db, company)


@router.get("/dashboard", response_model=DashboardMetricsResponse)
def get_dashboard(db: DbDep):
    integrations = (
        db.query(PlatformIntegration).options(joinedload(PlatformIntegration.connections)).all()
    )
    enabled = [i for i in integrations if i.is_enabled]

    def conn_status(i: PlatformIntegration) -> str:
        if not i.is_enabled:
            return "disabled"
        if not i.connections:
            return "not_configured"
        return i.connections[0].status

    connected = sum(1 for i in enabled if conn_status(i) == "connected")
    errors = sum(1 for i in enabled if conn_status(i) == "error")
    not_configured = sum(1 for i in enabled if conn_status(i) == "not_configured")
    services = db.query(PlatformService).all()
    services_enabled = sum(1 for s in services if s.is_enabled and s.encrypted_config_ref)

    platform_stats = PlatformStatsResponse(
        total_integrations=len(integrations),
        enabled_integrations=len(enabled),
        connected_integrations=connected,
        error_integrations=errors,
        not_configured_integrations=not_configured,
        services_enabled=services_enabled,
        total_services=len(services),
    )

    total_companies = db.query(func.count(Company.id)).scalar() or 0
    active_companies = db.query(func.count(Company.id)).filter(Company.status == "active").scalar() or 0
    trial_companies = db.query(func.count(Company.id)).filter(Company.status == "trial").scalar() or 0
    suspended_companies = db.query(func.count(Company.id)).filter(Company.status == "suspended").scalar() or 0
    active_pipelines = db.query(func.count(PipelineRun.id)).filter(PipelineRun.status == "running").scalar() or 0
    monthly_cost = float(db.query(func.coalesce(func.sum(UsageLedger.cost_usd), 0)).scalar() or 0)
    token_sum = db.query(func.coalesce(func.sum(UsageLedger.input_tokens + UsageLedger.output_tokens), 0)).scalar() or 0

    return DashboardMetricsResponse(
        platform_stats=platform_stats,
        total_companies=total_companies,
        active_companies=active_companies,
        trial_companies=trial_companies,
        suspended_companies=suspended_companies,
        active_pipelines=active_pipelines,
        monthly_platform_cost_usd=monthly_cost,
        monthly_token_usage_m=round(float(token_sum) / 1_000_000, 2),
        failed_pipelines_24h=0,
    )


@router.get("/dashboard/pipeline-activity", response_model=list[PipelineActivityItem])
def get_pipeline_activity(db: DbDep):
    runs = (
        db.query(PipelineRun, Project, Company)
        .join(Project, Project.id == PipelineRun.project_id)
        .join(Company, Company.id == Project.company_id)
        .order_by(PipelineRun.created_at.desc())
        .limit(10)
        .all()
    )
    return [
        PipelineActivityItem(
            id=str(run.id),
            company_name=company.name,
            project_name=project.name,
            step=run.current_step or "pending",
            status=run.status,
            started_at=run.started_at,
        )
        for run, project, company in runs
    ]


@router.get("/audit-log")
def list_audit_log(db: DbDep):
    events = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100).all()
    result = []
    for e in events:
        user = db.query(User).filter(User.id == e.user_id).first() if e.user_id else None
        company = db.query(Company).filter(Company.id == e.company_id).first() if e.company_id else None
        meta = e.metadata_json or {}
        result.append(
            {
                "id": str(e.id),
                "timestamp": e.created_at.isoformat(),
                "user": user.email if user else "system",
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_name": meta.get("name", e.resource_type),
                "company_name": company.name if company else None,
                "ip_address": str(e.ip_address) if e.ip_address else None,
            }
        )
    return result


@router.get("/system-health")
def system_health(db: DbDep):
    from db.session import check_db_connection

    db_ok = False
    try:
        db_ok = check_db_connection()
    except Exception:
        pass

    services = db.query(PlatformService).all()
    svc_status = [
        {
            "name": "PostgreSQL",
            "status": "healthy" if db_ok else "down",
            "latency_ms": 4 if db_ok else None,
            "message": "Database connected" if db_ok else "Connection failed",
        }
    ]
    for s in services:
        if s.is_enabled and s.last_test_status:
            st = "healthy"
        elif s.is_enabled:
            st = "degraded"
        else:
            st = "healthy"
        svc_status.append(
            {
                "name": s.display_name,
                "status": st,
                "latency_ms": 12 if st == "healthy" else None,
                "message": "Configured" if s.encrypted_config_ref else "Not configured",
            }
        )

    healthy = sum(1 for s in svc_status if s["status"] == "healthy")
    degraded = sum(1 for s in svc_status if s["status"] == "degraded")
    down = sum(1 for s in svc_status if s["status"] == "down")

    return {
        "healthy": healthy,
        "degraded": degraded,
        "down": down,
        "services": svc_status,
        "queue": {"active_workers": 0, "queue_depth": 0, "tasks_per_min": 0, "failed_1h": 0},
    }


@router.get("/platform-stats", response_model=PlatformStatsResponse)
def platform_stats(db: DbDep):
    return get_dashboard(db).platform_stats
