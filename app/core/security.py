from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import jwt
from pwdlib import PasswordHash
from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def credential_signature(hashed: str) -> str:
    return hmac.new(
        get_settings().jwt_secret_key.encode(), hashed.encode(), hashlib.sha256
    ).hexdigest()


def generate_password() -> str:
    return secrets.token_urlsafe(18)


def create_token(user_id: int, hashed: str) -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user_id),
            "pwd": credential_signature(hashed),
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=settings.access_token_expire_minutes),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
