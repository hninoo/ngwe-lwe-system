from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import get_current_user
from viewmodels.dashboard_viewmodel import DashboardViewModel

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_dashboard_vm = DashboardViewModel()


@router.get("/summary")
def get_summary(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    summary = _dashboard_vm.get_today_summary()
    return asdict(summary)


@router.get("/accounts")
def get_accounts(current_user: dict = Depends(get_current_user)) -> list[dict]:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    accounts = _dashboard_vm.get_all_accounts()
    return [asdict(a) for a in accounts]
