"""Signed double-opt-in tokens.

Backed by ``itsdangerous.URLSafeTimedSerializer`` so we don't have to hand-roll
HMAC + timestamp encoding. Each token carries a ``jti`` (token id) so we can
invalidate tokens by storing the jti in the DB row and refusing to confirm
twice.
"""

from __future__ import annotations

import hashlib
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import get_settings

_SALT = "lead_pipeline.confirm.v1"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt=_SALT)


def new_jti() -> str:
    return secrets.token_urlsafe(24)


def make_confirmation_token(email: str, jti: str) -> str:
    return _serializer().dumps({"email": email.lower(), "jti": jti})


def parse_confirmation_token(token: str) -> tuple[str, str]:
    """Returns ``(email, jti)`` or raises ``ValueError``."""
    settings = get_settings()
    try:
        data = _serializer().loads(token, max_age=settings.confirm_token_max_age_seconds)
    except SignatureExpired as exc:
        raise ValueError("token expired") from exc
    except BadSignature as exc:
        raise ValueError("invalid token") from exc
    if not isinstance(data, dict) or "email" not in data or "jti" not in data:
        raise ValueError("malformed token payload")
    return str(data["email"]), str(data["jti"])


def hash_ip(ip: str) -> str:
    """SHA-256 of the IP joined with the secret key. Stored, not the raw IP."""
    settings = get_settings()
    return hashlib.sha256(f"{ip}|{settings.secret_key}".encode()).hexdigest()
