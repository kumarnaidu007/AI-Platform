from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from models import Company, CompanyMember, CompanySettings, User
from models.platform import (
    CompanyPlatformIntegration,
    CompanyPlatformService,
    PlanPlatformIntegration,
    PlanPlatformService,
    PlatformIntegration,
    PlatformService,
)
from services.auth import hash_password
from services.company_domain import email_matches_domain, is_valid_domain, normalize_domain
from services.platform_helpers import integration_is_assignable, service_is_assignable


def provision_company_access(db: Session, company: Company) -> None:
    """Copy plan defaults — only for integrations/services configured on the platform."""
    plan_integration_ids = [
        row.platform_integration_id
        for row in db.query(PlanPlatformIntegration)
        .filter(PlanPlatformIntegration.plan_id == company.plan_id)
        .all()
    ]
    if plan_integration_ids:
        integrations = (
            db.query(PlatformIntegration)
            .options(joinedload(PlatformIntegration.connections))
            .filter(PlatformIntegration.id.in_(plan_integration_ids))
            .all()
        )
        for integration in integrations:
            if not integration_is_assignable(integration):
                continue
            db.merge(
                CompanyPlatformIntegration(
                    company_id=company.id,
                    platform_integration_id=integration.id,
                    is_enabled=True,
                )
            )

    plan_service_ids = [
        row.platform_service_id
        for row in db.query(PlanPlatformService)
        .filter(PlanPlatformService.plan_id == company.plan_id)
        .all()
    ]
    if plan_service_ids:
        services = db.query(PlatformService).filter(PlatformService.id.in_(plan_service_ids)).all()
        for service in services:
            if not service_is_assignable(service):
                continue
            db.merge(
                CompanyPlatformService(
                    company_id=company.id,
                    platform_service_id=service.id,
                    is_enabled=True,
                )
            )

    if not company.settings:
        settings = CompanySettings(company_id=company.id)
        db.add(settings)
        company.settings = settings


def set_company_email_domain(db: Session, company: Company, domain: str) -> str:
    norm = normalize_domain(domain)
    if not is_valid_domain(norm):
        raise ValueError("Invalid email domain")
    if not company.settings:
        company.settings = CompanySettings(company_id=company.id)
        db.add(company.settings)
    company.settings.email_domain = norm
    return norm


def create_company_admin(
    db: Session,
    company: Company,
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
            db.query(CompanyMember)
            .filter(CompanyMember.company_id == company.id, CompanyMember.user_id == existing.id)
            .first()
        )
        if not member:
            db.add(
                CompanyMember(
                    company_id=company.id,
                    user_id=existing.id,
                    role="admin",
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
        CompanyMember(
            company_id=company.id,
            user_id=user.id,
            role="admin",
        )
    )
    return user


def get_company_admin(db: Session, company_id: UUID) -> User | None:
    member = (
        db.query(CompanyMember)
        .join(User)
        .filter(CompanyMember.company_id == company_id, CompanyMember.role == "admin")
        .order_by(CompanyMember.joined_at.asc())
        .first()
    )
    return member.user if member else None
