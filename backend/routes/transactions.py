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


async def _broadcast_balances() -> None:
    if ws_manager is None:
        return
    accounts = _account_vm.get_all_active()
    payload = {
        "type": "balance_update",
        "accounts": [asdict(a) for a in accounts],
    }
    await ws_manager.broadcast(payload)


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
    await _broadcast_balances()
    return asdict(txn)


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
    await _broadcast_balances()
    return asdict(txn)


@router.post("/transfer")
async def create_transfer(
    body: TransferRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] == "cashier":
        raise HTTPException(403, "Cashiers cannot record transactions")
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
    await _broadcast_balances()
    return asdict(txn)


@router.post("/exchange")
async def create_exchange(
    body: ExchangeRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] == "cashier":
        raise HTTPException(403, "Cashiers cannot record transactions")
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
    await _broadcast_balances()
    return asdict(txn)


@router.get("/recent")
def get_recent(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    from viewmodels.dashboard_viewmodel import DashboardViewModel
    limit = min(limit, 200)
    txns = DashboardViewModel().get_recent_transactions(limit)
    return [asdict(t) for t in txns]
