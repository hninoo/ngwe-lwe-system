from dataclasses import asdict
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from repositories.commission_tier_repository import CommissionTierRepository

router = APIRouter(prefix="/commission-tiers", tags=["commission_tiers"])

_tier_repo = CommissionTierRepository()


class TierRequest(BaseModel):
    service_type: str
    account_type: Optional[str] = None
    amount_from: Optional[float] = None
    amount_to: Optional[float] = None
    fee_amount_type: Literal["FIXED", "PERCENTAGE"] = "FIXED"
    fee_amount_deposit: float = 0.0
    fee_amount_withdraw: float = 0.0
    comm_type: Literal["FIXED", "PERCENTAGE"] = "FIXED"
    comm_deposit: float = 0.0
    comm_withdraw: float = 0.0
    additional_fee_type: Literal["FIXED", "PERCENTAGE"] = "FIXED"
    additional_fee_deposit_amount: float = 0.0
    additional_fee_withdraw_amount: float = 0.0


@router.get("/")
def get_tiers(
    service_type: str = "KPAY_WST",
    account_type: str = "agent",
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    tiers = _tier_repo.get_by_service_type(service_type, account_type)
    return [asdict(t) for t in tiers]


@router.get("/lookup")
def lookup_tier(
    service_type: str,
    account_type: str,
    amount: float,
    current_user: dict = Depends(get_current_user),
) -> dict:
    tier = _tier_repo.get_tier_for_amount(service_type, account_type, amount)
    if tier is None:
        return {
            "fee_amount_deposit": 0, "fee_amount_withdraw": 0,
            "comm_deposit": 0, "comm_withdraw": 0,
        }
    return asdict(tier)


@router.post("/")
def create_tier(
    body: TierRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    tier_id = _tier_repo.create({
        "service_type": body.service_type,
        "account_type": body.account_type,
        "amount_from": body.amount_from,
        "amount_to": body.amount_to,
        "fee_amount_type": body.fee_amount_type,
        "fee_amount_deposit": body.fee_amount_deposit,
        "fee_amount_withdraw": body.fee_amount_withdraw,
        "comm_type": body.comm_type,
        "comm_deposit": body.comm_deposit,
        "comm_withdraw": body.comm_withdraw,
        "additional_fee_type": body.additional_fee_type,
        "additional_fee_deposit_amount": body.additional_fee_deposit_amount,
        "additional_fee_withdraw_amount": body.additional_fee_withdraw_amount,
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
    _tier_repo.update(tier_id, {
        "service_type": body.service_type,
        "account_type": body.account_type,
        "amount_from": body.amount_from,
        "amount_to": body.amount_to,
        "fee_amount_type": body.fee_amount_type,
        "fee_amount_deposit": body.fee_amount_deposit,
        "fee_amount_withdraw": body.fee_amount_withdraw,
        "comm_type": body.comm_type,
        "comm_deposit": body.comm_deposit,
        "comm_withdraw": body.comm_withdraw,
        "additional_fee_type": body.additional_fee_type,
        "additional_fee_deposit_amount": body.additional_fee_deposit_amount,
        "additional_fee_withdraw_amount": body.additional_fee_withdraw_amount,
    })
    return {"message": "Tier updated"}


@router.delete("/{tier_id}")
def delete_tier(
    tier_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    _tier_repo.delete(tier_id)
    return {"message": "Tier deleted"}
