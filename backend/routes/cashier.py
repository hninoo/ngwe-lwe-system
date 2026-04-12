from dataclasses import asdict
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from repositories.cash_denomination_repository import CashDenominationRepository, DENOMINATIONS
from repositories.cash_float_repository import CashFloatRepository
from repositories.user_repository import UserRepository

router = APIRouter(prefix="/cashier", tags=["cashier"])

# Maximum allowed mismatch between denomination total and transaction amount (MMK).
# Within tolerance the approval proceeds; beyond it the request is rejected.
CASH_TOLERANCE_MMK: int = 100

_denom_repo = CashDenominationRepository()
_float_repo = CashFloatRepository()
_user_repo = UserRepository()


# ── Pydantic request models ──

class VaultEntryRequest(BaseModel):
    entry_type: str  # vault_in | adjustment
    denominations: dict[str, int]
    note: Optional[str] = None


class IssueFloatRequest(BaseModel):
    employee_id: int
    denominations: dict[str, int]
    note: Optional[str] = None


class ReceiveFloatRequest(BaseModel):
    pin: str


class CloseFloatRequest(BaseModel):
    closing_denominations: dict[str, int]
    note: Optional[str] = None


class ReceivedCashRequest(BaseModel):
    denominations: dict[str, int]
    note: Optional[str] = None


# ── Helpers ──

def _parse_denominations(raw: dict[str, int]) -> dict[int, int]:
    """Convert string-keyed denomination dict to int-keyed, validating keys."""
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


# ── Vault endpoints ──

@router.get("/vault")
def get_vault(current_user: dict = Depends(get_current_user)) -> dict:
    """Cashier-only: current vault balance."""
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    balance = _denom_repo.get_vault_balance()
    return _vault_summary(balance)


@router.post("/vault/entry")
def record_vault_entry(
    body: VaultEntryRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Cashier-only: record a vault_in or adjustment entry."""
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
    """Cashier-only: recent denomination log entries."""
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    logs = _denom_repo.get_logs(limit=100)
    return [asdict(log) for log in logs]


# ── Float endpoints ──

@router.get("/floats")
def get_floats(current_user: dict = Depends(get_current_user)) -> list[dict]:
    """Cashier sees all floats; employee sees their own."""
    role = current_user["role"]
    if role == "cashier":
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
    """Cashier-only: issue a float to an employee."""
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    denoms = _parse_denominations(body.denominations)
    total = sum(d * q for d, q in denoms.items())
    if total == 0:
        raise HTTPException(400, "Float total must be greater than zero")
    cash_float = _float_repo.issue_float(
        employee_id=body.employee_id,
        issued_by=current_user["user_id"],
        denominations=denoms,
        denom_repo=_denom_repo,
        note=body.note,
    )
    return asdict(cash_float)


@router.get("/floats/my-pending")
def get_my_pending_float(current_user: dict = Depends(get_current_user)) -> dict:
    """Employee: get their own PENDING float (if any)."""
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
    return asdict(cash_float)


@router.post("/floats/{float_id}/receive")
def receive_float(
    float_id: int,
    body: ReceiveFloatRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Employee confirms receipt of float with PIN."""
    if current_user["role"] != "employee":
        raise HTTPException(403, "Employee access only")
    cash_float = _float_repo.get_float(float_id)
    if cash_float is None:
        raise HTTPException(404, "Float not found")
    if cash_float.employee_id != current_user["user_id"]:
        raise HTTPException(403, "This float is not assigned to you")
    if cash_float.status != "PENDING":
        raise HTTPException(409, f"Float is not pending (status={cash_float.status})")

    # Verify PIN
    user = _user_repo.get_by_id(current_user["user_id"])
    if user is None or user.pin_hash is None:
        raise HTTPException(400, "No PIN set. Ask your cashier to set your PIN first.")
    if not bcrypt.checkpw(body.pin.encode(), user.pin_hash.encode()):
        raise HTTPException(401, "Incorrect PIN")

    updated = _float_repo.receive_float(float_id)
    return asdict(updated)


@router.post("/floats/{float_id}/close")
def close_float(
    float_id: int,
    body: CloseFloatRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Employee or cashier: close a float by returning denominations."""
    cash_float = _float_repo.get_float(float_id)
    if cash_float is None:
        raise HTTPException(404, "Float not found")

    role = current_user["role"]
    if role == "employee":
        if cash_float.employee_id != current_user["user_id"]:
            raise HTTPException(403, "This float is not assigned to you")
    elif role != "cashier":
        raise HTTPException(403, "Access denied")

    if cash_float.status not in ("ACTIVE", "PENDING"):
        raise HTTPException(409, f"Float cannot be closed (status={cash_float.status})")

    closing_denoms = _parse_denominations(body.closing_denominations)

    updated = _float_repo.close_float(
        float_id=float_id,
        closing_denominations=closing_denoms,
        denom_repo=_denom_repo,
        note=body.note,
    )
    return asdict(updated)


# ── Transaction cash approval ──

@router.post("/transactions/{txn_id}/approve")
def approve_transaction(
    txn_id: int,
    body: ReceivedCashRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Cashier approves cash for a transaction with denomination breakdown."""
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Only cashiers can approve cash for transactions")

    from repositories.transaction_repository import TransactionRepository
    txn_repo = TransactionRepository()
    txn = txn_repo.get_by_id(txn_id)
    if txn is None:
        raise HTTPException(404, "Transaction not found")
    if txn.cash_approved_by is not None:
        raise HTTPException(409, "Transaction already approved")

    denoms = _parse_denominations(body.denominations)
    entered_total = sum(d * q for d, q in denoms.items())
    if entered_total == 0:
        raise HTTPException(400, "Denomination total must be greater than zero")

    # Validate denomination total against transaction amount
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

    # Deposits: cash comes in from customer (vault_in)
    # Withdrawals / exchanges: cash goes out to customer (vault_out)
    entry_type = "vault_in" if txn.transaction_type == "deposit" else "vault_out"
    total = entered_total  # alias used below
    note = body.note or f"Txn #{txn_id} ({txn.transaction_type})"
    _denom_repo.record_bulk_entry(
        entry_type=entry_type,
        denominations=denoms,
        created_by=current_user["user_id"],
        note=note,
    )

    updated = txn_repo.approve(txn_id, current_user["user_id"])
    return asdict(updated)
