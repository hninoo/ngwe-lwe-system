from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.auth import create_token, get_current_user
from backend.rate_limit import RateLimiter
from backend.user_dto import safe_user_dict
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
_login_limiter = RateLimiter(max_attempts=5, window_seconds=300)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request) -> dict:
    client_host = request.client.host if request.client else "unknown"
    key = f"login:{client_host}:{body.username.strip().lower()}"
    _login_limiter.check(key)
    if not _auth_vm.login(body.username, body.password):
        _login_limiter.record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = _auth_vm.current_user
    token = create_token(user)
    _auth_vm.logout()
    _login_limiter.clear(key)
    return {"token": token, "user": safe_user_dict(user)}


@router.post("/logout", response_model=MessageResponse)
def logout(current_user: dict = Depends(get_current_user)) -> dict:
    return {"message": "Logged out"}
