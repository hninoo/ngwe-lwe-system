from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from backend.websocket_manager import ConnectionManager
from repositories.cash_float_repository import CashFloatRepository
from viewmodels.account_viewmodel import AccountViewModel
from viewmodels.transaction_viewmodel import TransactionViewModel

router = APIRouter(prefix="/transactions", tags=["transactions"])

_txn_vm = TransactionViewModel()
_account_vm = AccountViewModel()
_float_repo = CashFloatRepository()

# Set from main.py at startup
ws_manager: Optional[ConnectionManager] = None


class DepositRequest(BaseModel):
    account_id: int
    amount: float
    customer_name: str
    customer_phone: str
    screenshot_path: Optional[str] = None
    customer_fee: float = 0.0
    additional_fee_amount: float = 0.0
    fee_account_id: Optional[int] = None
    note: Optional[str] = None


class WithdrawRequest(BaseModel):
    account_id: int
    amount: float
    customer_name: str
    customer_phone: str
    screenshot_path: Optional[str] = None
    customer_fee: float = 0.0
    additional_fee_amount: float = 0.0
    fee_account_id: Optional[int] = None
    note: Optional[str] = None


class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float
    screenshot_path: Optional[str] = None
    customer_fee: float = 0.0
    additional_fee_amount: float = 0.0
    fee_account_id: Optional[int] = None
    note: Optional[str] = None


class ExchangeRequest(BaseModel):
    account_id: int
    amount: float
    currency: str
    screenshot_path: Optional[str] = None
    customer_fee: float = 0.0
    additional_fee_amount: float = 0.0
    fee_account_id: Optional[int] = None
    note: Optional[str] = None


_txn_repo_direct = None  # lazy import to avoid circular


async def _broadcast_balances() -> None:
    if ws_manager is None:
        return
    accounts = _account_vm.get_all_active()
    payload = {
        "type": "balance_update",
        "accounts": [asdict(a) for a in accounts],
    }
    await ws_manager.broadcast(payload)


async def _broadcast_new_transaction(txn_dict: dict) -> None:
    if ws_manager is None:
        return
    await ws_manager.broadcast({"type": "new_transaction", "transaction": txn_dict})


@router.post("/deposit")
async def create_deposit(
    body: DepositRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] == "cashier":
        raise HTTPException(403, "Cashiers cannot record transactions")
    txn = _txn_vm.create_deposit(
        account_id=body.account_id,
        amount=body.amount,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        screenshot_path=body.screenshot_path,
        created_by=current_user["user_id"],
        customer_fee=body.customer_fee,
        additional_fee_amount=body.additional_fee_amount,
        fee_account_id=body.fee_account_id,
        note=body.note,
    )
    txn_dict = asdict(txn)
    await _broadcast_balances()
    await _broadcast_new_transaction(txn_dict)
    return txn_dict


@router.post("/withdraw")
async def create_withdraw(
    body: WithdrawRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] == "cashier":
        raise HTTPException(403, "Cashiers cannot record transactions")
    if current_user["role"] == "employee":
        active = _float_repo.get_active_float_for_employee(current_user["user_id"])
        if active is None:
            raise HTTPException(403, "No active float. Receive your float from the cashier first.")
    txn = _txn_vm.create_withdraw(
        account_id=body.account_id,
        amount=body.amount,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        screenshot_path=body.screenshot_path,
        created_by=current_user["user_id"],
        customer_fee=body.customer_fee,
        additional_fee_amount=body.additional_fee_amount,
        fee_account_id=body.fee_account_id,
        note=body.note,
    )
    txn_dict = asdict(txn)
    await _broadcast_balances()
    await _broadcast_new_transaction(txn_dict)
    return txn_dict


@router.post("/transfer")
async def create_transfer(
    body: TransferRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] == "cashier":
        raise HTTPException(403, "Cashiers cannot record transactions")
    if current_user["role"] == "employee":
        active = _float_repo.get_active_float_for_employee(current_user["user_id"])
        if active is None:
            raise HTTPException(403, "No active float. Receive your float from the cashier first.")
    txn = _txn_vm.create_transfer(
        from_account_id=body.from_account_id,
        to_account_id=body.to_account_id,
        amount=body.amount,
        screenshot_path=body.screenshot_path,
        created_by=current_user["user_id"],
        customer_fee=body.customer_fee,
        additional_fee_amount=body.additional_fee_amount,
        fee_account_id=body.fee_account_id,
        note=body.note,
    )
    txn_dict = asdict(txn)
    await _broadcast_balances()
    await _broadcast_new_transaction(txn_dict)
    return txn_dict


@router.post("/exchange")
async def create_exchange(
    body: ExchangeRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] == "cashier":
        raise HTTPException(403, "Cashiers cannot record transactions")
    if current_user["role"] == "employee":
        active = _float_repo.get_active_float_for_employee(current_user["user_id"])
        if active is None:
            raise HTTPException(403, "No active float. Receive your float from the cashier first.")
    txn = _txn_vm.create_exchange(
        account_id=body.account_id,
        amount=body.amount,
        currency=body.currency,
        screenshot_path=body.screenshot_path,
        created_by=current_user["user_id"],
        customer_fee=body.customer_fee,
        additional_fee_amount=body.additional_fee_amount,
        fee_account_id=body.fee_account_id,
        note=body.note,
    )
    txn_dict = asdict(txn)
    await _broadcast_balances()
    await _broadcast_new_transaction(txn_dict)
    return txn_dict


@router.get("/")
def get_all(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    txn_type: Optional[str] = None,
    account_id: Optional[int] = None,
    limit: int = 200,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    """Owner-only: list all transactions with optional filters."""
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    from repositories.transaction_repository import TransactionRepository
    repo = TransactionRepository()
    txns = repo.get_all_filtered(
        date_from=date_from, date_to=date_to,
        txn_type=txn_type, account_id=account_id,
        limit=min(limit, 1000),
    )
    return [asdict(t) for t in txns]


@router.delete("/{txn_id}")
def delete_transaction(
    txn_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Owner-only: permanently delete a transaction record."""
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    from repositories.transaction_repository import TransactionRepository
    repo = TransactionRepository()
    deleted = repo.delete(txn_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted", "txn_id": txn_id}


@router.get("/recent")
def get_recent(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    limit = min(limit, 1000)
    if current_user["role"] == "employee":
        from repositories.transaction_repository import TransactionRepository
        txns = TransactionRepository().get_recent_by_user(current_user["user_id"], limit)
    else:
        from viewmodels.dashboard_viewmodel import DashboardViewModel
        txns = DashboardViewModel().get_recent_transactions(limit)
    return [asdict(t) for t in txns]


@router.get("/by-date")
def get_by_date(
    date: str,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    """Return all transactions for a given date (YYYY-MM-DD)."""
    from repositories.transaction_repository import TransactionRepository
    txns = TransactionRepository().get_by_date(date)
    return [asdict(t) for t in txns]
