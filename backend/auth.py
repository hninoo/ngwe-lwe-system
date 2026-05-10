import hashlib
import hmac
import json
import os
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException

from models.user import User
from repositories.user_repository import UserRepository

load_dotenv()

SECRET_KEY = os.getenv("APP_SECRET")
if not SECRET_KEY:
    raise RuntimeError("APP_SECRET environment variable is not set")
if SECRET_KEY.strip().lower() in {"your_secret_key_here", "change-me", "secret"} or len(SECRET_KEY) < 32:
    raise RuntimeError("APP_SECRET must be a strong random secret of at least 32 characters")
TOKEN_EXPIRY_SECONDS = 86400  # 24 hours


def create_token(user: User) -> str:
    payload = json.dumps({
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "auth_version": getattr(user, "auth_version", 0) or 0,
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS,
    })
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def decode_token(token: str) -> dict:
    parts = token.split("|", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid token")

    payload_str, signature = parts
    expected = hmac.new(SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ")
    payload = decode_token(token)
    user = UserRepository().get_by_username(str(payload.get("username") or ""))
    if user is None or user.id != int(payload.get("user_id") or 0) or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or not found")
    token_version = int(payload.get("auth_version") or 0)
    if token_version != int(getattr(user, "auth_version", 0) or 0):
        raise HTTPException(status_code=401, detail="Token revoked")
    return {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "auth_version": user.auth_version,
    }


def require_roles(*roles: str):
    """Dependency factory that restricts access to specific roles."""
    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Access denied")
        return current_user
    return Depends(_check)
