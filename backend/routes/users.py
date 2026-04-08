from dataclasses import asdict
from typing import Literal, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from repositories.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["users"])

_user_repo = UserRepository()


class CreateUserRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: Literal["employee", "cashier"] = "employee"


class ToggleActiveRequest(BaseModel):
    is_active: bool


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class SetPinRequest(BaseModel):
    pin: str


@router.get("/")
def get_users(current_user: dict = Depends(get_current_user)) -> list[dict]:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    users = _user_repo.get_all()
    return [asdict(u) for u in users]


@router.post("/")
def create_user(
    body: CreateUserRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt(12)).decode()
    user_id = _user_repo.create({
        "username": body.username,
        "password_hash": pw_hash,
        "full_name": body.full_name,
        "role": body.role,
    })
    return {"message": "User created", "user_id": user_id}


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
    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt(12)).decode()
    _user_repo.update(current_user["user_id"], {"password_hash": new_hash})
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
    if len(body.pin) != 6 or not body.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must be exactly 6 digits")
    pin_hash = bcrypt.hashpw(body.pin.encode(), bcrypt.gensalt(12)).decode()
    _user_repo.update(user_id, {"pin_hash": pin_hash})
    return {"message": "PIN set"}
