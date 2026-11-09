"""Shared FastAPI dependencies: DB session, current user, RBAC guards."""
from __future__ import annotations

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = decode_token(credentials.credentials, expected_type="access")
    except pyjwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc.__class__.__name__}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = db.get(User, claims["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="user inactive or unknown")
    return user


def require_roles(*roles: str):
    """Route guard: ``Depends(require_roles("doctor", "admin"))``."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"role '{user.role}' not permitted (requires one of {list(roles)})",
            )
        return user

    return checker
