from dataclasses import asdict

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


class ToggleActiveRequest(BaseModel):
    is_active: bool


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


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
        "role": "employee",
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
