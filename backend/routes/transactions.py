from dataclasses import asdict
from pathlib import PurePosixPath
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth import get_current_user
from backend.money import normalize_money
from backend.websocket_manager import ConnectionManager
from repositories.cash_float_repository import CashFloatRepository
from repositories.user_repository import UserRepository
from viewmodels.account_viewmodel import AccountViewModel
from viewmodels.transaction_viewmodel import TransactionViewModel, InsufficientFloatError, InsufficientDenominationError

router = APIRouter(prefix="/transactions", tags=["transactions"])

_txn_vm = TransactionViewModel()
_account_vm = AccountViewModel()
_float_repo = CashFloatRepository()
_user_repo = UserRepository()

# Set from main.py at startup
ws_manager: Optional[ConnectionManager] = None


class CashInRequest(BaseModel):
    account_id: int
    amount: float = Field(gt=0)
    amount_received: Optional[float] = Field(default=None, ge=0)
    customer_name: str
    customer_phone: str
    screenshot_path: Optional[str] = None
    customer_fee: float = Field(default=0.0, ge=0)
    additional_fee_amount: float = Field(default=0.0, ge=0)
    fee_account_id: Optional[int] = None
    note: Optional[str] = None
    received_breakdown: Optional[Any] = None
    change_breakdown: Optional[Any] = None


class CashOutRequest(BaseModel):
    account_id: int
    amount: float = Field(gt=0)
    customer_name: str
    customer_phone: str
    screenshot_path: Optional[str] = None
    customer_fee: float = Field(default=0.0, ge=0)
    additional_fee_amount: float = Field(default=0.0, ge=0)
    fee_account_id: Optional[int] = None
    note: Optional[str] = None
    denominations: Optional[dict[str, int]] = None


class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float = Field(gt=0)
    screenshot_path: Optional[str] = None
    customer_fee: float = Field(default=0.0, ge=0)
    additional_fee_amount: float = Field(default=0.0, ge=0)
    fee_account_id: Optional[int] = None
    note: Optional[str] = None
    denominations: Optional[dict[str, int]] = None


class ExchangeRequest(BaseModel):
    account_id: int
    amount: float = Field(gt=0)
    currency: Literal["MMK", "THB"]
    screenshot_path: Optional[str] = None
    customer_fee: float = Field(default=0.0, ge=0)
    additional_fee_amount: float = Field(default=0.0, ge=0)
    fee_account_id: Optional[int] = None
    note: Optional[str] = None
    denominations: Optional[dict[str, int]] = None


_txn_repo_direct = None  # lazy import to avoid circular


def _validate_screenshot_path(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    clean = str(path).strip().replace("\\", "/")
    if not clean:
        return None
    parts = PurePosixPath(clean).parts
    if (
        clean.startswith("/")
        or ":" in clean
        or ".." in parts
        or parts[:2] != ("uploads", "screenshots")
    ):
        raise HTTPException(
            422,
            "Invalid screenshot_path. Use a server-generated uploads/screenshots path.",
        )
    return clean


def _money(value: float) -> float:
    try:
        return normalize_money(value)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))


async def _broadcast_balances() -> None:
    if ws_manager is None:
        return
    accounts = _account_vm.get_all_active()
    payload = {
        "type": "balance_update",   # handled by DashboardPage.update_from_ws
        "event": "balance_update",  # handled by DailyClosingView.handle_ws_event
        "source": "transaction",
        "accounts": [asdict(a) for a in accounts],
    }
    await ws_manager.broadcast_to_roles(["owner", "cashier"], payload)


async def _broadcast_new_transaction(txn_dict: dict) -> None:
    if ws_manager is None:
        return
    await ws_manager.broadcast_to_roles(
        ["owner", "cashier"],
        {"type": "new_transaction", "transaction": txn_dict},
    )


async def _broadcast_cash_in_pending(txn_dict: dict) -> None:
    if ws_manager is None:
        return
    creator = _user_repo.get_by_id(int(txn_dict.get("created_by") or 0))
    await ws_manager.broadcast_to_role(
        "cashier",
        {
            "type": "cash_in_pending",
            "txn_id": txn_dict.get("id"),
            "amount": txn_dict.get("amount"),
            "employee_name": creator.full_name if creator else str(txn_dict.get("created_by") or ""),
            "timestamp": txn_dict.get("created_at"),
            "transaction": txn_dict,
        },
    )


@router.post("/cash_in")
async def create_cash_in(
    body: CashInRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] == "cashier":
        raise HTTPException(403, "Cashiers cannot record transactions")
    if current_user["role"] == "employee":
        active = _float_repo.get_active_float_for_employee(current_user["user_id"])
        if active is None:
            raise HTTPException(403, "No active float. Receive your float from the cashier first.")
    try:
        txn = _txn_vm.create_cash_in(
            account_id=body.account_id,
            amount=_money(body.amount),
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            screenshot_path=_validate_screenshot_path(body.screenshot_path),
            created_by=current_user["user_id"],
            customer_fee=_money(body.customer_fee),
            additional_fee_amount=_money(body.additional_fee_amount),
            fee_account_id=body.fee_account_id,
            note=body.note,
            employee_id=current_user["user_id"] if current_user["role"] == "employee" else None,
            amount_received=_money(body.amount_received) if body.amount_received is not None else None,
            received_breakdown=body.received_breakdown,
            change_breakdown=body.change_breakdown,
        )
    except (InsufficientFloatError, InsufficientDenominationError) as exc:
        raise HTTPException(409, detail=f"Insufficient Mini Vault balance for Cash In change: {exc}")
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))
    txn_dict = asdict(txn)
    await _broadcast_balances()
    if txn_dict.get("status") == "PENDING_CASHIER_CONFIRM":
        await _broadcast_cash_in_pending(txn_dict)
    await _broadcast_new_transaction(txn_dict)
    return txn_dict


@router.post("/cash_out")
async def create_cash_out(
    body: CashOutRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] == "cashier":
        raise HTTPException(403, "Cashiers cannot record transactions")
    if current_user["role"] == "employee":
        active = _float_repo.get_active_float_for_employee(current_user["user_id"])
        if active is None:
            raise HTTPException(403, "No active float. Receive your float from the cashier first.")
        if body.denominations is None:
            raise HTTPException(422, "Employees must provide denomination breakdown for Cash Out.")
    employee_id = current_user["user_id"] if current_user["role"] == "employee" else None
    try:
        txn = _txn_vm.create_cash_out(
            account_id=body.account_id,
            amount=_money(body.amount),
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            screenshot_path=_validate_screenshot_path(body.screenshot_path),
            created_by=current_user["user_id"],
            customer_fee=_money(body.customer_fee),
            additional_fee_amount=_money(body.additional_fee_amount),
            fee_account_id=body.fee_account_id,
            note=body.note,
            employee_id=employee_id,
            denominations=body.denominations,
        )
    except (InsufficientFloatError, InsufficientDenominationError) as exc:
        raise HTTPException(409, detail=f"Insufficient Mini Vault balance for Cash Out: {exc}")
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))
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
        if body.denominations is None:
            raise HTTPException(422, "Employees must provide denomination breakdown for transfers.")
    employee_id = current_user["user_id"] if current_user["role"] == "employee" else None
    try:
        txn = _txn_vm.create_transfer(
            from_account_id=body.from_account_id,
            to_account_id=body.to_account_id,
            amount=_money(body.amount),
            screenshot_path=_validate_screenshot_path(body.screenshot_path),
            created_by=current_user["user_id"],
            customer_fee=_money(body.customer_fee),
            additional_fee_amount=_money(body.additional_fee_amount),
            fee_account_id=body.fee_account_id,
            note=body.note,
            employee_id=employee_id,
            denominations=body.denominations,
        )
    except (InsufficientFloatError, InsufficientDenominationError) as exc:
        raise HTTPException(422, detail=f"Vault Insufficient: {exc}")
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))
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
        if body.denominations is None:
            raise HTTPException(422, "Employees must provide denomination breakdown for exchanges.")
    employee_id = current_user["user_id"] if current_user["role"] == "employee" else None
    try:
        txn = _txn_vm.create_exchange(
            account_id=body.account_id,
            amount=_money(body.amount),
            currency=body.currency,
            screenshot_path=_validate_screenshot_path(body.screenshot_path),
            created_by=current_user["user_id"],
            customer_fee=_money(body.customer_fee),
            additional_fee_amount=_money(body.additional_fee_amount),
            fee_account_id=body.fee_account_id,
            note=body.note,
            employee_id=employee_id,
            denominations=body.denominations,
        )
    except (InsufficientFloatError, InsufficientDenominationError) as exc:
        raise HTTPException(422, detail=f"Vault Insufficient: {exc}")
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))
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
    """Owner-only guard: hard deletes are disabled for financial records."""
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    raise HTTPException(
        status_code=409,
        detail=(
            "Transaction hard delete is disabled because it can corrupt balances. "
            "Use a reversal/void workflow instead."
        ),
    )


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
    """Return transactions for a given date. Owner/cashier see all; employees see their own."""
    from repositories.transaction_repository import TransactionRepository
    repo = TransactionRepository()
    if current_user["role"] == "employee":
        txns = repo.get_by_date_for_user(date, current_user["user_id"])
    else:
        txns = repo.get_by_date(date)
    return [asdict(t) for t in txns]
