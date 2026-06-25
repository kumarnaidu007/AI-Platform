import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet

from config import settings


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def encrypt_secrets(data: dict[str, Any]) -> str:
    payload = json.dumps(data).encode()
    token = _fernet().encrypt(payload).decode()
    return f"local:{token}"


def decrypt_secrets(ref: str | None) -> dict[str, Any]:
    if not ref or not ref.startswith("local:"):
        return {}
    token = ref[6:].encode()
    payload = _fernet().decrypt(token)
    return json.loads(payload.decode())


def mask_secret(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return value[:4] + "****"
