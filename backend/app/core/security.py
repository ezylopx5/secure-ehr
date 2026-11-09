"""Password hashing (bcrypt) and JWT (HS256) with RBAC claims.

JWT claims: ``sub`` (user id), ``role``, ``attrs`` (ABE attributes),
``typ`` (access|refresh), ``exp``/``iat``/``jti``. The signing key is
HKDF-derived from the system master key - never configured separately.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import get_settings
from app.crypto.key_manager import get_key_manager

_ALG = "HS256"


# ---- passwords -------------------------------------------------------------
def hash_password(password: str) -> str:
    if not 8 <= len(password) <= 72:  # bcrypt operates on <= 72 bytes
        raise ValueError("password must be 8-72 characters")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


# ---- tokens ----------------------------------------------------------------
def _create_token(
    subject: str,
    role: str,
    attrs: list[str],
    token_type: Literal["access", "refresh"],
    lifetime: timedelta,
) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "attrs": attrs,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, get_key_manager().jwt_signing_key, algorithm=_ALG)


def create_token_pair(user_id: str, role: str, attrs: list[str]) -> dict[str, str]:
    s = get_settings()
    return {
        "access_token": _create_token(
            user_id, role, attrs, "access",
            timedelta(minutes=s.ACCESS_TOKEN_MINUTES),
        ),
        "refresh_token": _create_token(
            user_id, role, attrs, "refresh",
            timedelta(days=s.REFRESH_TOKEN_DAYS),
        ),
        "token_type": "bearer",
    }


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> dict[str, Any]:
    """Decode + validate; raises ``jwt.PyJWTError`` on any problem."""
    claims = jwt.decode(
        token, get_key_manager().jwt_signing_key, algorithms=[_ALG]
    )
    if claims.get("typ") != expected_type:
        raise jwt.InvalidTokenError(f"expected {expected_type} token")
    return claims
