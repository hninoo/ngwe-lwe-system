from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from repositories.exchange_rate_repository import ExchangeRateRepository

router = APIRouter(prefix="/exchange-rates", tags=["exchange_rates"])

_rate_repo = ExchangeRateRepository()


class RateUpdateRequest(BaseModel):
    currency_pair: str = "MMK/THB"
    buy_rate: float
    sell_rate: float


@router.get("/latest")
def get_latest(
    pair: str = "MMK/THB",
    current_user: dict = Depends(get_current_user),
) -> dict:
    rate = _rate_repo.get_latest(pair)
    if rate is None:
        return {"currency_pair": pair, "buy_rate": 0, "sell_rate": 0}
    return asdict(rate)


@router.post("/")
def create_rate(
    body: RateUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    rate_id = _rate_repo.create({
        "currency_pair": body.currency_pair,
        "buy_rate": body.buy_rate,
        "sell_rate": body.sell_rate,
    })
    return {"message": "Rate saved", "id": rate_id}
