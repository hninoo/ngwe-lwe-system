import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user

logger = logging.getLogger(__name__)
from backend.database import get_cursor
from repositories.account_repository import AccountRepository
from repositories.cash_denomination_repository import CashDenominationRepository
from repositories.cash_float_repository import CashFloatRepository
from repositories.daily_reconciliation_repository import DailyReconciliationRepository
from repositories.transaction_repository import TransactionRepository
from services.vault_service import VaultService
from viewmodels.dashboard_viewmodel import DashboardViewModel, MMT

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

_txn_repo = TransactionRepository()
_account_repo = AccountRepository()
_float_repo = CashFloatRepository()
_denom_repo = CashDenominationRepository()
_recon_repo = DailyReconciliationRepository()
_dashboard_vm = DashboardViewModel()
_vault_service = VaultService(float_repo=_float_repo, denom_repo=_denom_repo)


class CloseDayRequest(BaseModel):
    notes: Optional[str] = None


@router.get("/current")
def get_current_snapshot(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(403, "Owner only")
    return _build_snapshot()


@router.post("/close-day")
def close_day(
    body: CloseDayRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(403, "Owner only")

    snapshot = _build_snapshot()

    recon_id = _recon_repo.save({
        "recon_date": snapshot["date"],
        "closed_by": current_user["user_id"],
        "total_deposit": snapshot["summary"]["total_deposit"],
        "total_withdraw": snapshot["summary"]["total_withdraw"],
        "total_transfer": snapshot["summary"]["total_transfer"],
        "total_exchange": snapshot["summary"]["total_exchange"],
        "total_commission": snapshot["summary"]["total_commission"],
        "total_customer_fees": snapshot["summary"]["total_customer_fees"],
        "main_vault_total": snapshot["vault_total"],
        "employee_floats_total": snapshot["employee_floats_total"],
        "total_cash": snapshot["total_cash"],
        "total_digital": snapshot["total_digital"],
        "grand_total": snapshot["grand_total"],
        "employee_snapshots": json.dumps(snapshot["employee_floats"]),
        "account_snapshots": json.dumps(snapshot["accounts"]),
        "vault_snapshot": json.dumps(snapshot["vault_denominations"]),
        "notes": body.notes,
    })

    # Close all active employee floats — end of day
    _float_repo.close_all_active_end_of_day()

    # Automated backup after successful day close
    try:
        from services.backup_service import BackupService
        backup_path = BackupService().create_backup()
        logger.info("Close-day backup: %s", backup_path)
    except Exception as exc:
        logger.warning("Close-day backup failed (non-fatal): %s", exc)

    return {"message": "Day closed successfully", "reconciliation_id": recon_id, **snapshot}


@router.get("/history")
def get_history(
    limit: int = 30,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    if current_user["role"] != "owner":
        raise HTTPException(403, "Owner only")
    return _recon_repo.get_recent(limit)


def _build_snapshot() -> dict:
    today = datetime.now(MMT).date()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())
    txns = _txn_repo.get_by_date_range(start, end)
    summary = _dashboard_vm._build_summary(txns)

    accounts = _account_repo.get_all_active()
    account_data = []
    for acc in accounts:
        sent_net = sum(
            (t.balance_change or 0.0) for t in txns if t.account_id == acc.id
        )
        received_transfers = sum(
            (t.amount or 0.0) for t in txns
            if t.to_account_id == acc.id and t.transaction_type == "transfer"
        )
        today_net = sent_net + received_transfers
        opening = (acc.balance or 0.0) - today_net
        account_data.append({
            "id": acc.id,
            "account_name": acc.account_name,
            "phone_number": acc.phone_number,
            "is_fee_account": bool(acc.is_fee_account),
            "opening_balance": round(opening, 2),
            "today_net": round(today_net, 2),
            "closing_balance": round(acc.balance or 0.0, 2),
        })

    vault = _denom_repo.get_vault_balance()
    vault_total = sum(d * q for d, q in vault.items())

    float_summaries = _float_repo.get_active_employee_float_summaries()
    employee_floats_total = sum(f["current_balance"] for f in float_summaries)

    # Full denomination inventory for the Closing Dashboard
    denomination_inventory = _vault_service.get_denomination_inventory()

    pending_deposits = [
        {
            "id": t.id,
            "account_id": t.account_id,
            "amount": t.amount,
            "customer_name": t.customer_name,
            "created_by": t.created_by,
            "created_at": str(t.created_at) if t.created_at else None,
        }
        for t in txns
        if t.transaction_type == "deposit" and t.cash_approved_by is None
    ]

    total_digital = sum(a["closing_balance"] for a in account_data)
    total_cash = vault_total + employee_floats_total

    return {
        "date": str(today),
        "summary": asdict(summary),
        "accounts": account_data,
        "vault_total": vault_total,
        "vault_denominations": {str(d): q for d, q in vault.items()},
        "employee_floats": float_summaries,
        "employee_floats_total": employee_floats_total,
        "denomination_inventory": denomination_inventory,
        "pending_deposits": pending_deposits,
        "total_cash": total_cash,
        "total_digital": total_digital,
        "grand_total": total_cash + total_digital,
    }
