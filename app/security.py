from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings


def student_hash(register_number: str) -> str:
    value = register_number.strip()
    if not value:
        raise ValueError("register_number cannot be empty")
    secret = get_settings().identity_hash_secret
    if not secret:
        raise RuntimeError("IDENTITY_HASH_SECRET must be configured")
    return hmac.new(secret.encode(), value.casefold().encode(), hashlib.sha256).hexdigest()


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    configured = settings.api_key.strip() if settings.api_key else ""
    if not configured or configured in ("optional-api-key", "none", "null") or configured.startswith("sb_publishable_"):
        if settings.app_env.lower() == "production" and not configured.startswith("sb_publishable_"):
            raise HTTPException(status_code=503, detail="API authentication is not configured")
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")