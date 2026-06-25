from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from sqlalchemy.orm import joinedload

from app.deps import AuthContext, CompanyAuthDep, DbDep, get_auth_context
from fastapi import Depends
from models import AuditEvent, Company, CompanyMember, CompanySettings, User
from schemas.auth import (
    AuthMeResponse,
    CompanyContextResponse,
    CompanyLoginRequest,
    LoginRequest,
    LogoutResponse,
    TokenResponse,
    UserResponse,
)
from services.auth import create_access_token, revoke_token, verify_password
from services.company_domain import email_matches_domain, normalize_domain

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


def _company_context(company: Company, role: str) -> CompanyContextResponse:
    domain = company.settings.email_domain if company.settings else None
    return CompanyContextResponse(
        id=company.id,
        name=company.name,
        slug=company.slug,
        status=company.status,
        plan_name=company.plan.name if company.plan else "",
        role=role,
        email_domain=domain,
    )


def _audit(db, user: User, action: str, request: Request, company_id=None) -> None:
    db.add(
        AuditEvent(
            user_id=user.id,
            company_id=company_id,
            action=action,
            resource_type="user",
            resource_id=user.id,
            ip_address=request.client.host if request.client else None,
        )
    )


@router.post("/admin/login", response_model=TokenResponse)
def admin_login(body: LoginRequest, request: Request, db: DbDep):
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    if not user.is_super_admin:
        raise HTTPException(403, "Super admin access required")

    user.last_login_at = datetime.now(UTC)
    token, _, _ = create_access_token(str(user.id), extra={"portal": "admin"})
    _audit(db, user, "login", request)
    db.commit()
    db.refresh(user)

    return TokenResponse(portal="admin", access_token=token, user=_user_response(user))


@router.post("/company/login", response_model=TokenResponse)
def company_login(body: CompanyLoginRequest, request: Request, db: DbDep):
    company = (
        db.query(Company)
        .options(joinedload(Company.plan), joinedload(Company.settings))
        .filter(Company.slug == body.company_slug)
        .first()
    )
    if not company:
        raise HTTPException(404, "Company not found")
    if company.status == "suspended":
        raise HTTPException(403, "Company account is suspended")

    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    if user.is_super_admin:
        raise HTTPException(403, "Use the super admin portal to sign in")

    membership = (
        db.query(CompanyMember)
        .filter(CompanyMember.company_id == company.id, CompanyMember.user_id == user.id)
        .first()
    )
    if not membership:
        raise HTTPException(403, "You are not a member of this company")

    email_domain = company.settings.email_domain if company.settings else None
    if email_domain:
        if not email_matches_domain(user.email, email_domain):
            raise HTTPException(
                403,
                f"Only @{normalize_domain(email_domain)} email addresses can sign in to this company",
            )
    elif membership.role != "admin":
        raise HTTPException(
            403,
            "Company email domain is not configured yet. Ask your company admin to complete setup.",
        )

    user.last_login_at = datetime.now(UTC)
    token, _, _ = create_access_token(
        str(user.id),
        extra={
            "portal": "company",
            "company_id": str(company.id),
            "company_slug": company.slug,
            "role": membership.role,
        },
    )
    _audit(db, user, "login", request, company_id=company.id)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        portal="company",
        access_token=token,
        user=_user_response(user),
        company=_company_context(company, membership.role),
    )


# Legacy alias
@router.post("/login", response_model=TokenResponse, include_in_schema=False)
def login_legacy(body: LoginRequest, request: Request, db: DbDep):
    return admin_login(body, request, db)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    db: DbDep,
    ctx: AuthContext = Depends(get_auth_context),
):
    if ctx.jti and ctx.token_exp:
        expires_at = datetime.fromtimestamp(ctx.token_exp, tz=UTC)
        revoke_token(db, ctx.jti, expires_at)

    company_id = ctx.company_id if ctx.portal == "company" else None
    _audit(db, ctx.user, "logout", request, company_id=company_id)
    db.commit()
    return LogoutResponse()


@router.get("/me", response_model=AuthMeResponse)
def me(db: DbDep, ctx: AuthContext = Depends(get_auth_context)):
    company_ctx = None
    if ctx.portal == "company" and ctx.company_id:
        company = (
            db.query(Company)
            .options(joinedload(Company.plan), joinedload(Company.settings))
            .filter(Company.id == ctx.company_id)
            .first()
        )
        if company:
            membership = (
                db.query(CompanyMember)
                .filter(CompanyMember.company_id == company.id, CompanyMember.user_id == ctx.user.id)
                .first()
            )
            if membership:
                company_ctx = _company_context(company, membership.role)

    return AuthMeResponse(
        portal=ctx.portal,
        user=_user_response(ctx.user),
        company=company_ctx,
    )
