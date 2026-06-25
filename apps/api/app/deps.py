from typing import Annotated
from collections.abc import Generator
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db.session import SessionLocal
from models import Company, CompanyMember, User
from services.auth import decode_access_token, is_token_revoked

security = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    portal: str
    company_id: UUID | None = None
    company_slug: str | None = None
    member_role: str | None = None
    jti: str | None = None
    token_exp: int | None = None


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbDep = Annotated[Session, Depends(get_db)]


def get_auth_context(
    db: DbDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> AuthContext:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
        portal = payload.get("portal", "admin")
        jti = payload.get("jti")
        token_exp = payload.get("exp")
    except (ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from None

    if is_token_revoked(db, jti):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has been revoked")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    company_id = payload.get("company_id")
    return AuthContext(
        user=user,
        portal=portal,
        company_id=UUID(company_id) if company_id else None,
        company_slug=payload.get("company_slug"),
        member_role=payload.get("role"),
        jti=jti,
        token_exp=token_exp,
    )


def get_current_user(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> User:
    return ctx.user


def require_super_admin(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> User:
    if ctx.portal != "admin" or not ctx.user.is_super_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin access required")
    return ctx.user


def require_company_member(
    db: DbDep,
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthContext:
    if ctx.portal != "company" or not ctx.company_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Company portal access required")

    membership = (
        db.query(CompanyMember)
        .filter(CompanyMember.user_id == ctx.user.id, CompanyMember.company_id == ctx.company_id)
        .first()
    )
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this company")

    company = db.query(Company).filter(Company.id == ctx.company_id).first()
    if not company or company.status == "suspended":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Company is suspended or not found")

    ctx.member_role = membership.role
    return ctx


CurrentUserDep = Annotated[User, Depends(get_current_user)]
SuperAdminDep = Annotated[User, Depends(require_super_admin)]
CompanyAuthDep = Annotated[AuthContext, Depends(require_company_member)]


def require_company_admin(ctx: CompanyAuthDep) -> AuthContext:
    if ctx.member_role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Company admin access required")
    return ctx


CompanyAdminDep = Annotated[AuthContext, Depends(require_company_admin)]


def require_company_writer(ctx: CompanyAuthDep) -> AuthContext:
    if ctx.member_role == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Viewer accounts have read-only access")
    return ctx


CompanyWriterDep = Annotated[AuthContext, Depends(require_company_writer)]
