from sqlalchemy.orm import Session

from models import User
from services.auth import hash_password, verify_password

ADMIN_EMAIL = "superadmin@platform.io"
ADMIN_PASSWORD = "Admin@123"


def ensure_super_admin(db: Session) -> None:
    """Ensure default super admin exists with a known dev password."""
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
