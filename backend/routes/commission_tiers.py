from dataclasses import asdict
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from backend.money import normalize_money
from repositories.commission_tier_repository import CommissionTierRepository
from repositories.service_type_repository import ServiceTypeRepository

router = APIRouter(prefix="/commission-tiers", tags=["commission_tiers"])

_tier_repo = CommissionTierRepository()
_service_type_repo = ServiceTypeRepository()


def _money(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        return normalize_money(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _amount(value: Optional[float], field_name: str) -> float:
    normalized = _money(value)
    if normalized is None or normalized <= 0:
        raise HTTPException(status_code=422, detail=f"{field_name} is required.")
    return normalized


def _money_or_default(value: Optional[float], default: float = 0.0) -> float:
    normalized = _money(value)
    normalized = default if normalized is None else normalized
    if normalized < 0:
        raise HTTPException(status_code=422, detail="Money values cannot be negative.")
    return normalized


def _first_present(*values: Optional[float]) -> Optional[float]:
    for value in values:
        if value is not None:
            return value
    return None


def _tier_to_dict(tier) -> dict:
    data = asdict(tier)
    data.update({
        "fee_amount_deposit": data["fee_amount_cash_in"],
        "fee_amount_withdraw": data["fee_amount_cash_out"],
        "comm_deposit": data["comm_cash_in"],
        "comm_withdraw": data["comm_cash_out"],
        "additional_fee_deposit_amount": data["additional_fee_cash_in_amount"],
        "additional_fee_withdraw_amount": data["additional_fee_cash_out_amount"],
    })
    return data


def _require_service_type(service_type_id: int) -> None:
    if _service_type_repo.get_by_id(service_type_id) is None:
        raise HTTPException(status_code=404, detail="ServiceType not found")


class TierRequest(BaseModel):
    service_type_id: int
    amount_from: Optional[float] = None
    amount_to: Optional[float] = None
    fee_amount_type: Literal["FIXED", "PERCENTAGE"]
    fee_amount_deposit: Optional[float] = None
    fee_amount_withdraw: Optional[float] = None
    fee_amount_cash_in: Optional[float] = None
    fee_amount_cash_out: Optional[float] = None
    comm_type: Optional[Literal["FIXED", "PERCENTAGE"]] = "FIXED"
    comm_deposit: Optional[float] = None
    comm_withdraw: Optional[float] = None
    comm_cash_in: Optional[float] = None
    comm_cash_out: Optional[float] = None
    additional_fee_type: Optional[Literal["FIXED", "PERCENTAGE"]] = "FIXED"
    additional_fee_deposit_amount: Optional[float] = None
    additional_fee_withdraw_amount: Optional[float] = None
    additional_fee_cash_in_amount: Optional[float] = None
    additional_fee_cash_out_amount: Optional[float] = None


@router.get("/")
def get_tiers(
    service_type_id: int,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    _require_service_type(service_type_id)
    tiers = _tier_repo.get_by_service_type(service_type_id)
    return [_tier_to_dict(t) for t in tiers]


@router.get("/lookup")
def lookup_tier(
    service_type_id: int,
    amount: float,
    current_user: dict = Depends(get_current_user),
) -> dict:
    amount = _amount(amount, "amount")
    _require_service_type(service_type_id)
    tier = _tier_repo.get_tier_for_amount(service_type_id, amount)
    if tier is None:
        return {
            "fee_amount_deposit": 0, "fee_amount_withdraw": 0,
            "comm_deposit": 0, "comm_withdraw": 0,
            "additional_fee_deposit_amount": 0, "additional_fee_withdraw_amount": 0,
            "fee_amount_cash_in": 0, "fee_amount_cash_out": 0,
            "comm_cash_in": 0, "comm_cash_out": 0,
        }
    return _tier_to_dict(tier)


@router.post("/")
def create_tier(
    body: TierRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    _require_service_type(body.service_type_id)
    amount_from = _amount(body.amount_from, "amount_from")
    amount_to = _amount(body.amount_to, "amount_to")
    err = _tier_repo.check_overlap(body.service_type_id, amount_from, amount_to)
    if err:
        raise HTTPException(status_code=422, detail=err)
    tier_id = _tier_repo.create({
        "service_type_id": body.service_type_id,
        "amount_from": amount_from,
        "amount_to": amount_to,
        "fee_amount_type": body.fee_amount_type,
        "fee_amount_deposit": _money_or_default(
            _first_present(body.fee_amount_deposit, body.fee_amount_cash_in)
        ),
        "fee_amount_withdraw": _money_or_default(
            _first_present(body.fee_amount_withdraw, body.fee_amount_cash_out)
        ),
        "comm_type": body.comm_type or "FIXED",
        "comm_deposit": _money_or_default(
            _first_present(body.comm_deposit, body.comm_cash_in)
        ),
        "comm_withdraw": _money_or_default(
            _first_present(body.comm_withdraw, body.comm_cash_out)
        ),
        "additional_fee_type": body.additional_fee_type or "FIXED",
        "additional_fee_deposit_amount": _money_or_default(
            _first_present(body.additional_fee_deposit_amount, body.additional_fee_cash_in_amount)
        ),
        "additional_fee_withdraw_amount": _money_or_default(
            _first_present(body.additional_fee_withdraw_amount, body.additional_fee_cash_out_amount)
        ),
    })
    return {"message": "Tier created", "id": tier_id}


@router.put("/{tier_id}")
def update_tier(
    tier_id: int,
    body: TierRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    if _tier_repo.get_by_id(tier_id) is None:
        raise HTTPException(status_code=404, detail="Tier not found")
    _require_service_type(body.service_type_id)
    amount_from = _amount(body.amount_from, "amount_from")
    amount_to = _amount(body.amount_to, "amount_to")
    err = _tier_repo.check_overlap(body.service_type_id, amount_from, amount_to, exclude_id=tier_id)
    if err:
        raise HTTPException(status_code=422, detail=err)
    _tier_repo.update(tier_id, {
        "service_type_id": body.service_type_id,
        "amount_from": amount_from,
        "amount_to": amount_to,
        "fee_amount_type": body.fee_amount_type,
        "fee_amount_deposit": _money_or_default(
            _first_present(body.fee_amount_deposit, body.fee_amount_cash_in)
        ),
        "fee_amount_withdraw": _money_or_default(
            _first_present(body.fee_amount_withdraw, body.fee_amount_cash_out)
        ),
        "comm_type": body.comm_type or "FIXED",
        "comm_deposit": _money_or_default(
            _first_present(body.comm_deposit, body.comm_cash_in)
        ),
        "comm_withdraw": _money_or_default(
            _first_present(body.comm_withdraw, body.comm_cash_out)
        ),
        "additional_fee_type": body.additional_fee_type or "FIXED",
        "additional_fee_deposit_amount": _money_or_default(
            _first_present(body.additional_fee_deposit_amount, body.additional_fee_cash_in_amount)
        ),
        "additional_fee_withdraw_amount": _money_or_default(
            _first_present(body.additional_fee_withdraw_amount, body.additional_fee_cash_out_amount)
        ),
    })
    return {"message": "Tier updated"}


@router.delete("/{tier_id}")
def delete_tier(
    tier_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    if not _tier_repo.delete(tier_id):
        raise HTTPException(status_code=404, detail="Tier not found")
    return {"message": "Tier deleted"}
