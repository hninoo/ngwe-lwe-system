from dataclasses import asdict
from decimal import Decimal
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator

import json

from backend.auth import get_current_user
from backend.database import atomic, get_cursor
from backend.rate_limit import RateLimiter
from backend.websocket_manager import ConnectionManager
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

CASH_TOLERANCE_MMK: int = 500

_denom_repo = CashDenominationRepository()
_float_repo = CashFloatRepository()
_user_repo = UserRepository()
_vault_service = VaultService(float_repo=_float_repo, denom_repo=_denom_repo)
_pin_limiter = RateLimiter(max_attempts=5, window_seconds=300)
ws_manager: Optional[ConnectionManager] = None


# ── Pydantic request models ──

def _validate_non_negative_denominations(value: dict[str, int]) -> dict[str, int]:
    for denom, qty in value.items():
        if qty < 0:
            raise ValueError(f"Quantity for {denom} must be a non-negative integer")
    return value


class VaultEntryRequest(BaseModel):
    entry_type: str
    denominations: dict[str, int]
    note: Optional[str] = None

    @field_validator("denominations")
    @classmethod
    def denominations_must_not_be_negative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_non_negative_denominations(value)


class IssueFloatRequest(BaseModel):
    employee_id: int
    denominations: dict[str, int]
    note: Optional[str] = None

    @field_validator("denominations")
    @classmethod
    def denominations_must_not_be_negative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_non_negative_denominations(value)


class ReceiveFloatRequest(BaseModel):
    pin: str
    denominations: dict[str, int]

    @field_validator("denominations")
    @classmethod
    def denominations_must_not_be_negative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_non_negative_denominations(value)


class InitiateReturnRequest(BaseModel):
    denominations: dict[str, int]
    note: Optional[str] = None
    pin: Optional[str] = None

    @field_validator("denominations")
    @classmethod
    def denominations_must_not_be_negative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_non_negative_denominations(value)


class ConfirmReturnRequest(BaseModel):
    pin: str


class ReceivedCashRequest(BaseModel):
    denominations: dict[str, int]
    note: Optional[str] = None

    @field_validator("denominations")
    @classmethod
    def denominations_must_not_be_negative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_non_negative_denominations(value)


class TransactionDenominationRequest(BaseModel):
    """Physical denomination tracker for transaction approval (gives + receives)."""
    gives: dict[str, int] = {}
    receives: dict[str, int] = {}
    note: Optional[str] = None

    @field_validator("gives", "receives")
    @classmethod
    def denominations_must_not_be_negative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_non_negative_denominations(value)


class TransactionPaymentRequest(BaseModel):
    fee_amount: Optional[int] = None
    received_denominations: dict[str, int]
    change_denominations: Optional[dict[str, int]] = None
    note: Optional[str] = None

    @field_validator("received_denominations", "change_denominations")
    @classmethod
    def denominations_must_not_be_negative(
        cls,
        value: Optional[dict[str, int]],
    ) -> Optional[dict[str, int]]:
        if value is None:
            return value
        return _validate_non_negative_denominations(value)


class ConfirmCashInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pin: str
    gives: dict[str, int] = {}
    receives: dict[str, int] = {}
    note: Optional[str] = None

    @field_validator("gives", "receives")
    @classmethod
    def denominations_must_not_be_negative(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_non_negative_denominations(value)


class CancelCashInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pin: str
    note: Optional[str] = None


# ── Employees (cashier-accessible) ──

@router.get("/employees")
def list_employees(current_user: dict = Depends(get_current_user)) -> list[dict]:
    """Active employees visible to cashier for float issuance."""
    if current_user["role"] not in ("cashier", "owner"):
        raise HTTPException(403, "Cashier or owner access only")
    return [
        {"id": u.id, "full_name": u.full_name, "username": u.username}
        for u in _user_repo.get_employees()
    ]


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


def _verify_cashier_pin_or_401(cashier_id: int, pin: str, key: str) -> None:
    _pin_limiter.check(key)
    stored_hash = _user_repo.get_pin_hash(cashier_id)
    if not stored_hash or not bcrypt.checkpw(pin.encode(), stored_hash.encode()):
        _pin_limiter.record_failure(key)
        raise HTTPException(401, "Invalid cashier PIN")
    _pin_limiter.clear(key)


def _validate_cash_in_denominations_total(
    denominations: dict[int, int],
    amount: float,
) -> tuple[Decimal, Decimal, Decimal]:
    entered_total = sum(Decimal(denom) * Decimal(qty) for denom, qty in denominations.items())
    expected = Decimal(str(amount or 0))
    diff = entered_total - expected
    if entered_total <= 0:
        raise HTTPException(400, "Denomination total must be greater than zero")
    if abs(diff) > Decimal(CASH_TOLERANCE_MMK):
        raise HTTPException(422, detail={
            "message": "Cash total does not match Cash In amount",
            "expected": float(expected),
            "entered": float(entered_total),
            "difference": float(diff),
            "tolerance": CASH_TOLERANCE_MMK,
        })
    return entered_total, expected, diff


def _publish_ws(method_name: str, *args) -> None:
    if ws_manager is None:
        return
    method = getattr(ws_manager, method_name)
    try:
        import anyio
        anyio.from_thread.run(method, *args)
    except RuntimeError:
        import asyncio
        asyncio.run(method(*args))


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


@router.get("/denominations")
def get_denominations(current_user: dict = Depends(get_current_user)) -> list[dict]:
    if current_user["role"] not in ("cashier", "owner", "employee"):
        raise HTTPException(403, "Access denied")
    return _denom_repo.get_note_denominations()


@router.get("/vault/denominations")
def get_vault_denominations(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] not in ("cashier", "owner"):
        raise HTTPException(403, "Cashier or owner access only")
    balance = _denom_repo.get_vault_balance()
    return {
        "denominations": {str(d): balance.get(d, 0) for d in DENOMINATIONS},
        "total": sum(d * balance.get(d, 0) for d in DENOMINATIONS),
    }


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
    result = asdict(cash_float)
    _publish_ws(
        "broadcast_to_user",
        body.employee_id,
        {
            "type": "float_issued",
            "float": result,
            "message": "You have received a new cash float. Please confirm receipt.",
        },
    )
    _publish_ws(
        "broadcast_to_roles",
        ["cashier", "owner"],
        {
            "type": "float_update",
            "float": result,
        },
    )
    return result


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
    key = f"pin:receive:{current_user['user_id']}"
    _pin_limiter.check(key)
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
        if status == 401:
            _pin_limiter.record_failure(key)
        raise HTTPException(status, msg)
    except (DenominationMismatchError, FloatStateError) as e:
        raise HTTPException(422, str(e))
    _pin_limiter.clear(key)
    result = asdict(updated)
    _publish_ws(
        "broadcast_to_roles",
        ["cashier", "owner"],
        {
            "type": "float_received",
            "float": result,
            "message": f"Employee #{current_user['user_id']} confirmed float receipt.",
        },
    )
    return result


@router.post("/floats/{float_id}/initiate-return")
def initiate_float_return(
    float_id: int,
    body: InitiateReturnRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Employee declares remaining denominations to return."""
    if current_user["role"] != "employee":
        raise HTTPException(403, "Employee access only")
    key = f"pin:initiate-return:{current_user['user_id']}"
    if not body.pin:
        raise HTTPException(422, "PIN is required to return cash.")
    _pin_limiter.check(key)
    stored_hash = _user_repo.get_pin_hash(current_user["user_id"])
    if not stored_hash or not bcrypt.checkpw(body.pin.encode(), stored_hash.encode()):
        _pin_limiter.record_failure(key)
        raise HTTPException(401, "Incorrect PIN.")
    try:
        updated = _vault_service.initiate_return(
            float_id=float_id,
            employee_id=current_user["user_id"],
            return_denominations=body.denominations,
            note=body.note,
        )
    except Exception as e:
        raise _service_error(e)
    _pin_limiter.clear(key)
    result = asdict(updated)
    _publish_ws(
        "broadcast_to_roles",
        ["cashier", "owner"],
        {
            "type": "float_return_initiated",
            "float": result,
            "message": "An employee has initiated a float return.",
        },
    )
    return result


@router.post("/floats/{float_id}/confirm-return")
def confirm_float_return(
    float_id: int,
    body: ConfirmReturnRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Cashier verifies returned cash with PIN — credits main vault."""
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    key = f"pin:return:{current_user['user_id']}"
    _pin_limiter.check(key)
    try:
        updated = _vault_service.confirm_return(
            float_id=float_id,
            cashier_id=current_user["user_id"],
            cashier_pin=body.pin,
        )
    except ValueError as e:
        msg = str(e)
        status = 401 if "Incorrect PIN" in msg else 400
        if status == 401:
            _pin_limiter.record_failure(key)
        raise HTTPException(status, msg)
    except FloatStateError as e:
        raise HTTPException(409, str(e))
    _pin_limiter.clear(key)
    result = asdict(updated)
    employee_id = result.get("employee_id")
    if employee_id:
        _publish_ws(
            "broadcast_to_user",
            int(employee_id),
            {
                "type": "float_return_confirmed",
                "float": result,
                "message": "Your float return has been confirmed by cashier.",
            },
        )
    _publish_ws(
        "broadcast_to_roles",
        ["cashier", "owner"],
        {
            "type": "float_update",
            "float": result,
        },
    )
    return result



# ── Transaction cash approval ──

@router.get("/pending-cash-ins")
def get_pending_cash_ins(current_user: dict = Depends(get_current_user)) -> list[dict]:
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    return [asdict(txn) for txn in TransactionRepository().get_pending_cash_ins()]


@router.post("/transactions/{txn_id}/confirm-cash-in")
def confirm_pending_cash_in(
    txn_id: int,
    body: ConfirmCashInRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    _verify_cashier_pin_or_401(
        current_user["user_id"],
        body.pin,
        f"pin:confirm-cash-in:{current_user['user_id']}",
    )

    txn_repo = TransactionRepository()
    txn = txn_repo.get_by_id(txn_id)
    if txn is None:
        raise HTTPException(404, "Transaction not found")
    if txn.transaction_type != "cash_in":
        raise HTTPException(400, "Only Cash In transactions can be completed here.")
    if txn.status != "PENDING_CASHIER_CONFIRM":
        raise HTTPException(409, f"Invalid status transition: {txn.status} -> COMPLETED")

    gives_denoms = _parse_denominations(body.gives)
    receives_denoms = _parse_denominations(body.receives)
    gives_total = sum(d * q for d, q in gives_denoms.items())
    receives_total = sum(d * q for d, q in receives_denoms.items())

    if gives_total > 0:
        raise HTTPException(
            400,
            "Cash In confirmation only accepts received denominations. "
            "Employee note-change must be handled from the employee mini vault.",
        )
    if receives_total == 0:
        raise HTTPException(400, "Received denominations are required")

    # Cash in: cashier receives the exact Cash In amount after employee note-change.
    net = Decimal(str(receives_total))
    expected = Decimal(str(txn.amount or 0))
    diff = net - expected
    if abs(diff) > Decimal(CASH_TOLERANCE_MMK):
        raise HTTPException(422, detail={
            "message": "Received cash total does not match Cash In amount",
            "expected": float(expected),
            "entered": float(net),
            "difference": float(diff),
            "tolerance": CASH_TOLERANCE_MMK,
        })

    with atomic():
        updated = txn_repo.confirm_pending_cash_in(txn_id, current_user["user_id"])
        if updated is None:
            raise HTTPException(409, "Cash In is no longer pending confirmation")
        from repositories.account_repository import AccountRepository
        account_repo = AccountRepository()
        if txn.fee_account_id is not None and float(txn.customer_fee or 0) > 0:
            if not account_repo.increment_balance(
                txn.fee_account_id, float(txn.customer_fee or 0)
            ):
                raise HTTPException(
                    500,
                    f"Fee credit failed: Fee account #{txn.fee_account_id} not found or inactive.",
                )
        # Cash received from customer (vault in)
        if receives_denoms:
            _denom_repo.record_bulk_entry(
                entry_type="vault_in",
                denominations=receives_denoms,
                created_by=current_user["user_id"],
                transaction_id=txn_id,
                note=body.note or f"Completed pending Cash In Txn #{txn_id}",
            )
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO activity_logs (user_id, action, entity_type, entity_id, details) "
                "VALUES (?, 'cash_in_cashier_completed', 'transaction', ?, ?)",
                (
                    current_user["user_id"],
                    txn_id,
                    json.dumps({
                        "amount": txn.amount,
                        "gives_total": gives_total,
                        "receives_total": receives_total,
                        "net": float(net),
                        "difference": float(diff),
                    }),
                ),
            )
    result = asdict(updated)
    _publish_ws(
        "broadcast_to_user",
        int(txn.created_by),
        {
            "type": "cash_in_confirmed",
            "transaction": result,
            "message": f"Your Cash In #{txn_id} has been confirmed by cashier.",
        },
    )
    _publish_ws(
        "broadcast_to_roles",
        ["cashier", "owner"],
        {
            "type": "pending_cash_in_update",
            "transaction_id": txn_id,
            "transaction": result,
        },
    )
    return result


@router.post("/transactions/{txn_id}/cancel-cash-in")
def cancel_pending_cash_in(
    txn_id: int,
    body: CancelCashInRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Cashier access only")
    _verify_cashier_pin_or_401(
        current_user["user_id"],
        body.pin,
        f"pin:cancel-cash-in:{current_user['user_id']}",
    )
    txn = TransactionRepository().get_by_id(txn_id)
    if txn is None:
        raise HTTPException(404, "Transaction not found")
    if txn.transaction_type != "cash_in":
        raise HTTPException(400, "Only Cash In transactions can be cancelled here.")
    if txn.status != "PENDING_CASHIER_CONFIRM":
        raise HTTPException(409, f"Invalid status transition: {txn.status} -> CANCELLED")
    from repositories.cash_in_repository import CashInRepository
    try:
        updated = CashInRepository().cancel_pending_cash_in(
            txn_id, current_user["user_id"], body.note
        )
    except RuntimeError as exc:
        raise HTTPException(
            500,
            detail={
                "message": "Cash In cancellation failed due to reversal safety check.",
                "error": str(exc),
                "txn_id": txn_id,
                "status": "PENDING_CASHIER_CONFIRM",
                "action_required": "Investigate account status and retry manually.",
            },
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if updated is None:
        raise HTTPException(409, "Cash In is no longer pending confirmation")
    result = asdict(updated)
    _publish_ws(
        "broadcast_to_user",
        int(txn.created_by),
        {
            "type": "cash_in_cancelled",
            "transaction_id": txn_id,
            "transaction": result,
            "message": f"Your Cash In #{txn_id} was cancelled by cashier.",
        },
    )
    _publish_ws(
        "broadcast_to_roles",
        ["cashier", "owner"],
        {
            "type": "pending_cash_in_update",
            "transaction_id": txn_id,
            "transaction": result,
        },
    )
    return result


@router.post("/transactions/{txn_id}/approve")
def approve_transaction(
    txn_id: int,
    body: TransactionDenominationRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Only cashiers can approve cash for transactions")

    txn_repo = TransactionRepository()
    txn = txn_repo.get_by_id(txn_id)
    if txn is None:
        raise HTTPException(404, "Transaction not found")
    if txn.transaction_type == "cash_in" and txn.status == "PENDING_CASHIER_CONFIRM":
        raise HTTPException(
            409,
            "Pending Cash In transactions must be completed through the cashier PIN flow.",
        )
    if txn.transaction_type == "transfer":
        raise HTTPException(400, "Transfers are not cash-approval transactions.")
    creator = _user_repo.get_by_id(txn.created_by)
    if creator and creator.role == "employee" and txn.transaction_type in ("cash_out", "exchange"):
        raise HTTPException(
            409,
            "Employee cash-out transactions are already deducted from the employee float.",
        )

    gives_denoms = _parse_denominations(body.gives)
    receives_denoms = _parse_denominations(body.receives)
    gives_total = sum(d * q for d, q in gives_denoms.items())
    receives_total = sum(d * q for d, q in receives_denoms.items())

    if gives_total == 0 and receives_total == 0:
        raise HTTPException(400, "At least one of gives or receives must have denominations")

    # Net vault flow: cash_in gains (receives − gives), cash_out loses (gives − receives)
    is_cash_in = (txn.transaction_type == "cash_in")
    net = (receives_total - gives_total) if is_cash_in else (gives_total - receives_total)
    expected = int(txn.amount)
    diff = net - expected
    if abs(diff) > CASH_TOLERANCE_MMK:
        raise HTTPException(422, detail={
            "message": "Net cash total does not match transaction amount",
            "expected": expected,
            "entered": net,
            "difference": diff,
            "tolerance": CASH_TOLERANCE_MMK,
        })

    note = body.note or f"Txn #{txn_id} ({txn.transaction_type})"

    with atomic():
        updated = txn_repo.approve_if_pending(txn_id, current_user["user_id"])
        if updated is None:
            raise HTTPException(409, "Transaction already approved")
        if gives_denoms:
            available = _denom_repo.get_vault_balance()
            for denom, qty in gives_denoms.items():
                if qty > available.get(denom, 0):
                    raise HTTPException(
                        409,
                        f"Insufficient main vault denomination {denom:,} MMK: "
                        f"available {available.get(denom, 0)}, requested {qty}",
                    )
            _denom_repo.record_bulk_entry(
                entry_type="vault_out",
                denominations=gives_denoms,
                created_by=current_user["user_id"],
                transaction_id=txn_id,
                note=note,
            )
        if receives_denoms:
            _denom_repo.record_bulk_entry(
                entry_type="vault_in",
                denominations=receives_denoms,
                created_by=current_user["user_id"],
                transaction_id=txn_id,
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
                        "gives_total": gives_total,
                        "receives_total": receives_total,
                        "net": net,
                    }),
                ),
            )

    result = asdict(updated)
    _publish_ws(
        "broadcast_to_user",
        int(txn.created_by),
        {
            "type": "transaction_approved",
            "transaction": result,
            "message": f"Your transaction #{txn_id} has been approved.",
        },
    )
    _publish_ws(
        "broadcast_to_roles",
        ["cashier", "owner"],
        {
            "type": "transaction_update",
            "transaction": result,
        },
    )
    return result


@router.post("/transactions/{txn_id}/payment")
def record_transaction_payment(
    txn_id: int,
    body: TransactionPaymentRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "cashier":
        raise HTTPException(403, "Only cashiers can record transaction payments")
    txn = TransactionRepository().get_by_id(txn_id)
    if txn is None:
        raise HTTPException(404, "Transaction not found")
    fee_amount = body.fee_amount
    if fee_amount is None:
        fee_amount = int(float(txn.customer_fee or 0))
    if fee_amount < 0:
        raise HTTPException(422, "fee_amount cannot be negative")
    try:
        result = _vault_service.record_transaction_payment(
            transaction_id=txn_id,
            cashier_id=current_user["user_id"],
            fee_amount=fee_amount,
            received_denominations=body.received_denominations,
            change_denominations=body.change_denominations,
            note=body.note,
        )
    except Exception as e:
        raise _service_error(e)
    _publish_ws(
        "broadcast_to_roles",
        ["cashier", "owner"],
        {
            "type": "transaction_payment_recorded",
            "payment": result,
        },
    )
    if txn.created_by:
        _publish_ws(
            "broadcast_to_user",
            int(txn.created_by),
            {
                "type": "transaction_payment_recorded",
                "payment": result,
            },
        )
    return result
