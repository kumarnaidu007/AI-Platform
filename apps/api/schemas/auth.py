from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CompanyLoginRequest(BaseModel):
    email: EmailStr
    password: str
    company_slug: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_super_admin: bool
    is_active: bool
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class CompanyContextResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    plan_name: str
    role: str
    email_domain: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    portal: str
    user: UserResponse
    company: CompanyContextResponse | None = None


class AuthMeResponse(BaseModel):
    portal: str
    user: UserResponse
    company: CompanyContextResponse | None = None


class LogoutResponse(BaseModel):
    success: bool = True
    message: str = "Logged out successfully"
