from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import create_token, get_current_user
from viewmodels.auth_viewmodel import AuthViewModel

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


class MessageResponse(BaseModel):
    message: str


_auth_vm = AuthViewModel()


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> dict:
    if not _auth_vm.login(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = _auth_vm.current_user
    token = create_token(user)
    _auth_vm.logout()
    return {"token": token, "user": asdict(user)}


@router.post("/logout", response_model=MessageResponse)
def logout(current_user: dict = Depends(get_current_user)) -> dict:
    return {"message": "Logged out"}
