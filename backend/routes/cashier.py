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
    """Cashier-only: record vault_in or adjustment."""
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    allowed_types = ("vault_in", "adjustment")
    if body.entry_type not in allowed_types:
        raise HTTPException(400, f"entry_type must be one of {allowed_types}")
    denoms = _parse_denominations(body.denominations)
    total = sum(d * q for d, q in denoms.items())
    if total == 0:
        raise HTTPException(400, "Total denomination amount must be greater than zero")
    _denom_repo.record_bulk_entry(
        entry_type=body.entry_type,
        denominations=denoms,
        created_by=current_user["user_id"],
        note=body.note,
    )
    return {"message": "Vault entry recorded", "total": total}


@router.get("/vault/logs")
def get_vault_logs(current_user: dict = Depends(get_current_user)) -> list[dict]:
    """Cashier-only: recent 50 denomination log entries."""
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    logs = _denom_repo.get_logs(limit=50)
    return [asdict(log) for log in logs]


# ── Float listing ──

@router.get("/floats")
def list_floats(current_user: dict = Depends(get_current_user)) -> list[dict]:
    """Cashier sees all floats; employee sees only their own."""
    role = current_user["role"]
    if role == "cashier":
        floats = _float_repo.list_floats()
    elif role == "employee":
        floats = _float_repo.list_floats(employee_id=current_user["user_id"])
    else:
        raise HTTPException(403, "Access denied")
    return [asdict(f) for f in floats]


# ── Issue float ──

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

    # Check employee exists
    employee = _user_repo.get_by_id(body.employee_id)
    if employee is None or employee.role != "employee":
        raise HTTPException(404, "Employee not found")

    # Max 1 open float check
    existing_pending = _float_repo.get_pending_float_for_employee(body.employee_id)
    existing_active = _float_repo.get_active_float_for_employee(body.employee_id)
    if existing_pending is not None or existing_active is not None:
        raise HTTPException(409, "Employee already has an open float (PENDING or ACTIVE)")

    # Vault sufficiency check
    available = _denom_repo.get_available_balance()
    for denom, qty in denoms.items():
        if qty > 0 and available.get(denom, 0) < qty:
            raise HTTPException(
                422,
                f"Insufficient vault balance for {denom} MMK: "
                f"requested {qty}, available {available.get(denom, 0)}",
            )

    float_id = _float_repo.create_float(
        employee_id=body.employee_id,
        issued_by=current_user["user_id"],
        denominations=denoms,
        total_amount=total,
        note=body.note,
    )
    cash_float = _float_repo.get_float(float_id)
    return asdict(cash_float)


# ── Employee: get my pending float ──

@router.get("/floats/my-pending")
def get_my_pending_float(current_user: dict = Depends(get_current_user)) -> dict:
    """Employee-only: get their PENDING float (with denominations)."""
    if current_user["role"] != "employee":
        raise HTTPException(403, "Employee access only")
    pending = _float_repo.get_pending_float_for_employee(current_user["user_id"])
    if pending is None:
        raise HTTPException(404, "No pending float found")
    return asdict(pending)


# ── Get specific float ──

@router.get("/floats/{float_id}")
def get_float(float_id: int, current_user: dict = Depends(get_current_user)) -> dict:
    """Cashier or the assigned employee can view a specific float."""
    cash_float = _float_repo.get_float(float_id)
    if cash_float is None:
        raise HTTPException(404, "Float not found")
    role = current_user["role"]
    if role == "cashier":
        pass  # cashier can see all
    elif role == "employee":
        if cash_float.employee_id != current_user["user_id"]:
            raise HTTPException(403, "Access denied")
    else:
        raise HTTPException(403, "Access denied")
    return asdict(cash_float)


# ── Receive float (employee confirms with PIN) ──

@router.post("/floats/{float_id}/receive")
def receive_float(
    float_id: int,
    body: ReceiveFloatRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Employee-only: confirm receipt of float by verifying PIN."""
    if current_user["role"] != "employee":
        raise HTTPException(403, "Employee access only")

    cash_float = _float_repo.get_float(float_id)
    if cash_float is None:
        raise HTTPException(404, "Float not found")
    if cash_float.employee_id != current_user["user_id"]:
        raise HTTPException(403, "This float is not assigned to you")
    if cash_float.status != "PENDING":
        raise HTTPException(409, f"Float is not PENDING (status={cash_float.status})")

    # Verify PIN
    stored_pin_hash = _user_repo.get_pin_hash(current_user["user_id"])
    if stored_pin_hash is None:
        raise HTTPException(400, "PIN not set. Please ask your cashier to set your PIN.")
    if not bcrypt.checkpw(body.pin.encode(), stored_pin_hash.encode()):
        raise HTTPException(401, "Invalid PIN")

    updated = _float_repo.activate_float(float_id, _denom_repo)
    return asdict(updated)


# ── Close float ──

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
