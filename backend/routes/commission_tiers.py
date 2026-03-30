from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from repositories.commission_tier_repository import CommissionTierRepository

router = APIRouter(prefix="/commission-tiers", tags=["commission_tiers"])

_tier_repo = CommissionTierRepository()


class TierRequest(BaseModel):
    service_type: str
    account_type: str = "agent"
    amount_from: float
    amount_to: float
    fee_amount: float = 0.0
    comm_send: float = 0.0
    comm_receive: float = 0.0


@router.get("/")
def get_tiers(
    service_type: str = "KPAY",
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
        return {"fee_amount": 0, "comm_send": 0, "comm_receive": 0}
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
        "fee_amount": body.fee_amount,
        "comm_send": body.comm_send,
        "comm_receive": body.comm_receive,
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
        "fee_amount": body.fee_amount,
        "comm_send": body.comm_send,
        "comm_receive": body.comm_receive,
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
