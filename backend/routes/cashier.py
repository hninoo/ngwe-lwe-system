from dataclasses import asdict
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import json

from backend.auth import get_current_user
from backend.database import atomic, get_cursor
from repositories.cash_denomination_repository import CashDenominationRepository, DENOMINATIONS
from repositories.cash_float_repository import CashFloatRepository
from repositories.transaction_repository import TransactionRepository
from repositories.user_repository import UserRepository
from services.vault_service import (
    DenominationMismatchError,
    FloatStateError,
    InsufficientDenominationError,
    VaultService,
)

router = APIRouter(prefix="/cashier", tags=["cashier"])

CASH_TOLERANCE_MMK: int = 100

_denom_repo = CashDenominationRepository()
_float_repo = CashFloatRepository()
_user_repo = UserRepository()
_vault_service = VaultService(float_repo=_float_repo, denom_repo=_denom_repo)


# ── Pydantic request models ──

class VaultEntryRequest(BaseModel):
    entry_type: str
    denominations: dict[str, int]
    note: Optional[str] = None


class IssueFloatRequest(BaseModel):
    employee_id: int
    denominations: dict[str, int]
    note: Optional[str] = None


class ReceiveFloatRequest(BaseModel):
    pin: str
    denominations: dict[str, int]


class InitiateReturnRequest(BaseModel):
    denominations: dict[str, int]
    note: Optional[str] = None


class ConfirmReturnRequest(BaseModel):
    pin: str


class ReceivedCashRequest(BaseModel):
    denominations: dict[str, int]
    note: Optional[str] = None


# ── Helpers ──

def _parse_denominations(raw: dict[str, int]) -> dict[int, int]:
    result: dict[int, int] = {}
    for k, v in raw.items():
        try:
            denom = int(k)
        except (ValueError, TypeError):
            raise HTTPException(400, f"Invalid denomination key: {k}")
        if denom not in DENOMINATIONS:
            raise HTTPException(400, f"Invalid denomination: {denom}. Must be one of {DENOMINATIONS}")
        if not isinstance(v, int) or v < 0:
            raise HTTPException(400, f"Quantity for {denom} must be a non-negative integer")
        result[denom] = v
    return result


def _vault_summary(balance: dict[int, int]) -> dict:
    total = sum(d * q for d, q in balance.items())
    return {
        "denominations": {str(d): balance.get(d, 0) for d in DENOMINATIONS},
        "total": total,
    }


def _service_error(e: Exception) -> HTTPException:
    if isinstance(e, InsufficientDenominationError):
        return HTTPException(409, str(e))
    if isinstance(e, DenominationMismatchError):
        return HTTPException(422, str(e))
    if isinstance(e, FloatStateError):
        return HTTPException(409, str(e))
    return HTTPException(400, str(e))


# ── Vault endpoints ──

@router.get("/vault")
def get_vault(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    balance = _denom_repo.get_vault_balance()
    return _vault_summary(balance)


@router.post("/vault/entry")
def record_vault_entry(
    body: VaultEntryRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    if body.entry_type not in ("vault_in", "adjustment"):
        raise HTTPException(400, "entry_type must be 'vault_in' or 'adjustment'")
    denoms = _parse_denominations(body.denominations)
    total = sum(d * q for d, q in denoms.items())
    if total == 0:
        raise HTTPException(400, "Total must be greater than zero")
    _denom_repo.record_bulk_entry(
        entry_type=body.entry_type,
        denominations=denoms,
        created_by=current_user["user_id"],
        note=body.note,
    )
    balance = _denom_repo.get_vault_balance()
    return _vault_summary(balance)


@router.get("/vault/logs")
def get_vault_logs(current_user: dict = Depends(get_current_user)) -> list[dict]:
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    logs = _denom_repo.get_logs(limit=100)
    return [asdict(log) for log in logs]


@router.get("/vault/inventory")
def get_vault_inventory(current_user: dict = Depends(get_current_user)) -> dict:
    """Full denomination inventory across main vault and all active employee floats."""
    if current_user["role"] not in ("cashier", "owner"):
        raise HTTPException(403, "Cashier or owner access only")
    return _vault_service.get_denomination_inventory()


# ── Float endpoints ──

@router.get("/floats")
def get_floats(current_user: dict = Depends(get_current_user)) -> list[dict]:
    role = current_user["role"]
    if role in ("cashier", "owner"):
        floats = _float_repo.get_all_floats()
    elif role == "employee":
        floats = _float_repo.get_floats_for_employee(current_user["user_id"])
    else:
        raise HTTPException(403, "Access denied")
    return [asdict(f) for f in floats]


@router.post("/floats")
def issue_float(
    body: IssueFloatRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Cashier issues float — main vault debited immediately."""
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    try:
        cash_float = _vault_service.issue_float(
            cashier_id=current_user["user_id"],
            employee_id=body.employee_id,
            denominations=body.denominations,
            note=body.note,
        )
    except Exception as e:
        raise _service_error(e)
    return asdict(cash_float)


@router.get("/floats/my-pending")
def get_my_pending_float(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] not in ("employee",):
        raise HTTPException(403, "Employee access only")
    cash_float = _float_repo.get_pending_float_for_employee(current_user["user_id"])
    if cash_float is None:
        raise HTTPException(404, "No pending float")
    return asdict(cash_float)


@router.get("/floats/{float_id}")
def get_float(
    float_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    cash_float = _float_repo.get_float(float_id)
    if cash_float is None:
        raise HTTPException(404, "Float not found")
    if current_user["role"] == "employee" and cash_float.employee_id != current_user["user_id"]:
        raise HTTPException(403, "Access denied")
    return asdict(cash_float)


@router.get("/floats/{float_id}/denominations")
def get_float_denomination_balance(
    float_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return current per-denomination balance for a float."""
    cash_float = _float_repo.get_float(float_id)
    if cash_float is None:
        raise HTTPException(404, "Float not found")
    if current_user["role"] == "employee" and cash_float.employee_id != current_user["user_id"]:
        raise HTTPException(403, "Access denied")
    balance = _vault_service.get_float_denomination_balance(float_id)
    total = sum(d * q for d, q in balance.items())
    return {
        "float_id": float_id,
        "denominations": {str(d): balance.get(d, 0) for d in DENOMINATIONS},
        "total": total,
    }


@router.post("/floats/{float_id}/receive")
def receive_float(
    float_id: int,
    body: ReceiveFloatRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Employee confirms receipt with PIN + denomination count verification."""
    if current_user["role"] != "employee":
        raise HTTPException(403, "Employee access only")
    try:
        updated = _vault_service.confirm_receipt(
            float_id=float_id,
            employee_id=current_user["user_id"],
            employee_pin=body.pin,
            verified_denominations=body.denominations,
        )
    except ValueError as e:
        msg = str(e)
        status = 401 if "Incorrect PIN" in msg else 400
        raise HTTPException(status, msg)
    except (DenominationMismatchError, FloatStateError) as e:
        raise HTTPException(422, str(e))
    return asdict(updated)


@router.post("/floats/{float_id}/initiate-return")
def initiate_float_return(
    float_id: int,
    body: InitiateReturnRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Employee declares remaining denominations to return."""
    if current_user["role"] != "employee":
        raise HTTPException(403, "Employee access only")
    try:
        updated = _vault_service.initiate_return(
            float_id=float_id,
            employee_id=current_user["user_id"],
            return_denominations=body.denominations,
            note=body.note,
        )
    except Exception as e:
        raise _service_error(e)
    return asdict(updated)


@router.post("/floats/{float_id}/confirm-return")
def confirm_float_return(
    float_id: int,
    body: ConfirmReturnRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Cashier verifies returned cash with PIN — credits main vault."""
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    try:
        updated = _vault_service.confirm_return(
            float_id=float_id,
            cashier_id=current_user["user_id"],
            cashier_pin=body.pin,
        )
    except ValueError as e:
        msg = str(e)
        status = 401 if "Incorrect PIN" in msg else 400
        raise HTTPException(status, msg)
    except FloatStateError as e:
        raise HTTPException(409, str(e))
    return asdict(updated)



# ── Transaction cash approval ──

@router.post("/transactions/{txn_id}/approve")
def approve_transaction(
    txn_id: int,
    body: ReceivedCashRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Only cashiers can approve cash for transactions")

    txn_repo = TransactionRepository()
    txn = txn_repo.get_by_id(txn_id)
    if txn is None:
        raise HTTPException(404, "Transaction not found")

    denoms = _parse_denominations(body.denominations)
    entered_total = sum(d * q for d, q in denoms.items())
    if entered_total == 0:
        raise HTTPException(400, "Denomination total must be greater than zero")

    expected = int(txn.amount)
    diff = entered_total - expected
    if abs(diff) > CASH_TOLERANCE_MMK:
        raise HTTPException(422, detail={
            "message": "Cash total does not match transaction amount",
            "expected": expected,
            "entered": entered_total,
            "difference": diff,
            "tolerance": CASH_TOLERANCE_MMK,
        })

    entry_type = "vault_in" if txn.transaction_type == "deposit" else "vault_out"
    note = body.note or f"Txn #{txn_id} ({txn.transaction_type})"

    with atomic():
        updated = txn_repo.approve_if_pending(txn_id, current_user["user_id"])
        if updated is None:
            raise HTTPException(409, "Transaction already approved")
        _denom_repo.record_bulk_entry(
            entry_type=entry_type,
            denominations=denoms,
            created_by=current_user["user_id"],
            note=note,
        )
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO activity_logs (user_id, action, entity_type, entity_id, details) "
                "VALUES (?, 'transaction_cash_approved', 'transaction', ?, ?)",
                (
                    current_user["user_id"],
                    txn_id,
                    json.dumps({
                        "txn_type": txn.transaction_type,
                        "amount": txn.amount,
                        "entered_total": entered_total,
                        "vault_entry_type": entry_type,
                    }),
                ),
            )

    return asdict(updated)
