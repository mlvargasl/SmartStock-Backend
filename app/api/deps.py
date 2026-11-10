from typing import Annotated
import hmac
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import credential_signature
from app.core.database import get_db
from app.models import Role, User
from app.repositories import Repository
from app.services import Service

Db = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def service(db: Db) -> Service:
    return Service(db)


def current_user(
    db: Db, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> User:
    unauthorized = HTTPException(
        401, "Invalid or expired credentials", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "pwd"]},
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise unauthorized
    user = Repository(db).get(User, user_id)
    if user is None or not user.active:
        raise unauthorized
    if not isinstance(payload.get("pwd"), str) or not hmac.compare_digest(
        payload["pwd"], credential_signature(user.password_hash)
    ):
        raise unauthorized
    return user


def allow(*roles: Role):
    def check(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user

    return check


Svc = Annotated[Service, Depends(service)]
