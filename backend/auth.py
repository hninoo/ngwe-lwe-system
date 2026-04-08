import hashlib
import hmac
import json
import os
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import Header, HTTPException

from models.user import User

load_dotenv()

SECRET_KEY = os.getenv("APP_SECRET")
if not SECRET_KEY:
    raise RuntimeError("APP_SECRET environment variable is not set")
TOKEN_EXPIRY_SECONDS = 86400  # 24 hours


def create_token(user: User) -> str:
    payload = json.dumps({
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
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

    payload = json.loads(payload_str)
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ")
    return decode_token(token)
