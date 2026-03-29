from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import get_current_user
from viewmodels.dashboard_viewmodel import DashboardViewModel
from repositories.transaction_repository import TransactionRepository

router = APIRouter(prefix="/reports", tags=["reports"])

_dashboard_vm = DashboardViewModel()
_txn_repo = TransactionRepository()


@router.get("/daily")
def get_daily_report(
    date: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")

    day = datetime.strptime(date, "%Y-%m-%d").date()
    start = datetime.combine(day, datetime.min.time())
    end = datetime.combine(day, datetime.max.time())
    txns = _txn_repo.get_by_date_range(start, end)

    summary = _dashboard_vm._build_summary(txns)
    return asdict(summary)
