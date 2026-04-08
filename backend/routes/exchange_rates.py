from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from repositories.exchange_rate_repository import ExchangeRateRepository

router = APIRouter(prefix="/exchange-rates", tags=["exchange_rates"])

_rate_repo = ExchangeRateRepository()


class RateUpdateRequest(BaseModel):
    base_currency: str = "THB"
    quote_currency: str = "MMK"
    base_amount: float = 1.0   # reference quantity of base currency
    buy_rate: float            # quote per base_amount — business buys base
    sell_rate: float           # quote per base_amount — business sells base


@router.get("/latest")
def get_latest(
    base: str = "THB",
    quote: str = "MMK",
    current_user: dict = Depends(get_current_user),
) -> dict:
    rate = _rate_repo.get_latest(base, quote)
    if rate is None:
        return {"base_currency": base, "quote_currency": quote, "base_amount": 1, "buy_rate": 0, "sell_rate": 0}
    return asdict(rate)


@router.post("/")
def create_rate(
    body: RateUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    rate_id = _rate_repo.create({
        "base_currency": body.base_currency,
        "quote_currency": body.quote_currency,
        "base_amount": body.base_amount,
        "buy_rate": body.buy_rate,
        "sell_rate": body.sell_rate,
    })
    return {"message": "Rate saved", "id": rate_id}
