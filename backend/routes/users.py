from typing import Literal, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from backend.rate_limit import RateLimiter
from backend.security_policy import validate_password_strength, validate_pin
from backend.user_dto import safe_user_dict
from repositories.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["users"])

_user_repo = UserRepository()
_pin_limiter = RateLimiter(max_attempts=5, window_seconds=300)


class CreateUserRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: Literal["employee", "cashier"] = "employee"


class ToggleActiveRequest(BaseModel):
    is_active: bool


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    new_password: str


class SetPinRequest(BaseModel):
    pin: str


class ChangePinRequest(BaseModel):
    current_pin: str
    new_pin: str


@router.get("/")
def get_users(current_user: dict = Depends(get_current_user)) -> list[dict]:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    users = _user_repo.get_all()
    return [safe_user_dict(u) for u in users]


@router.get("/employees")
def list_employees(current_user: dict = Depends(get_current_user)) -> list[dict]:
    """Return active employees. Accessible to cashiers (needed for float issuance)."""
    if current_user["role"] not in ("owner", "cashier"):
        raise HTTPException(status_code=403, detail="Access denied")
    return [
        {"id": u.id, "full_name": u.full_name, "username": u.username}
        for u in _user_repo.get_employees()
    ]


@router.post("/")
def create_user(
    body: CreateUserRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    try:
        validate_password_strength(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt(12)).decode()
    user_id = _user_repo.create({
        "username": body.username,
        "password_hash": pw_hash,
        "full_name": body.full_name,
        "role": body.role,
    })
    return {"message": "User created", "user_id": user_id}


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "role" in data and data["role"] not in ("employee", "cashier"):
        raise HTTPException(status_code=400, detail="Invalid role")
    _user_repo.update_with_auth_revoke(user_id, data)
    return {"message": "User updated", "user_id": user_id}


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    body: ResetPasswordRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    try:
        validate_password_strength(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt(12)).decode()
    _user_repo.update_with_auth_revoke(user_id, {"password_hash": new_hash})
    return {"message": "Password reset", "user_id": user_id}


@router.patch("/{user_id}/active")
def toggle_active(
    user_id: int,
    body: ToggleActiveRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    _user_repo.update_is_active(user_id, body.is_active)
    return {"message": "Updated", "user_id": user_id}


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    stored = _user_repo.get_password_hash(current_user["username"])
    if stored is None or not bcrypt.checkpw(body.old_password.encode(), stored.encode()):
        raise HTTPException(status_code=400, detail="Old password incorrect")
    try:
        validate_password_strength(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt(12)).decode()
    _user_repo.update_with_auth_revoke(current_user["user_id"], {"password_hash": new_hash})
    return {"message": "Password changed"}


@router.post("/{user_id}/pin")
def set_pin(
    user_id: int,
    body: SetPinRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Owner can set anyone's PIN; user can set their own PIN."""
    if current_user["role"] != "owner" and current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        validate_pin(body.pin)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    pin_hash = bcrypt.hashpw(body.pin.encode(), bcrypt.gensalt(12)).decode()
    _user_repo.update_with_auth_revoke(user_id, {"pin_hash": pin_hash})
    return {"message": "PIN set"}


@router.post("/change-pin")
def change_pin(
    body: ChangePinRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Authenticated user changes their own PIN by verifying the current one first."""
    try:
        validate_pin(body.new_pin)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    key = f"pin:{current_user['user_id']}"
    _pin_limiter.check(key)
    stored_hash = _user_repo.get_pin_hash(current_user["user_id"])
    if not stored_hash:
        raise HTTPException(status_code=400, detail="No PIN set yet. Use Set PIN first.")
    if not bcrypt.checkpw(body.current_pin.encode(), stored_hash.encode()):
        _pin_limiter.record_failure(key)
        raise HTTPException(status_code=401, detail="Incorrect current PIN.")
    new_hash = bcrypt.hashpw(body.new_pin.encode(), bcrypt.gensalt(12)).decode()
    _user_repo.update_with_auth_revoke(current_user["user_id"], {"pin_hash": new_hash})
    _pin_limiter.clear(key)
    return {"message": "PIN changed"}
