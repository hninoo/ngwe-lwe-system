from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.auth import get_current_user
from backend.money import normalize_money
from repositories.exchange_rate_repository import ExchangeRateRepository

router = APIRouter(prefix="/exchange-rates", tags=["exchange_rates"])

_rate_repo = ExchangeRateRepository()


class RateUpdateRequest(BaseModel):
    base_currency: str = Field(default="THB", min_length=1)
    quote_currency: str = Field(default="MMK", min_length=1)
    base_amount: float = 1.0
    buy_rate: float
    sell_rate: float

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def currency_not_blank(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Currency is required.")
        return value


class RatePatchRequest(BaseModel):
    base_currency: Optional[str] = None
    quote_currency: Optional[str] = None
    base_amount: Optional[float] = None
    buy_rate: Optional[float] = None
    sell_rate: Optional[float] = None

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def optional_currency_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip().upper()
        if not value:
            raise ValueError("Currency is required.")
        return value


def _normalize_rate_payload(data: dict) -> dict:
    normalized = dict(data)
    for field in ("base_amount", "buy_rate", "sell_rate"):
        if field not in normalized:
            continue
        try:
            normalized[field] = normalize_money(normalized[field], places=4)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    if "base_amount" in normalized and normalized["base_amount"] <= 0:
        raise HTTPException(status_code=422, detail="base_amount must be greater than zero.")
    if "buy_rate" in normalized and normalized["buy_rate"] <= 0:
        raise HTTPException(status_code=422, detail="buy_rate must be greater than zero.")
    if "sell_rate" in normalized and normalized["sell_rate"] <= 0:
        raise HTTPException(status_code=422, detail="sell_rate must be greater than zero.")
    return normalized


@router.get("/")
def get_rates(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    limit = max(1, min(limit, 200))
    return [asdict(rate) for rate in _rate_repo.get_all_recent(limit)]


@router.get("/latest")
def get_latest(
    base: str = "THB",
    quote: str = "MMK",
    current_user: dict = Depends(get_current_user),
) -> dict:
    base = base.strip().upper()
    quote = quote.strip().upper()
    rate = _rate_repo.get_latest(base, quote)
    if rate is None:
        return {
            "base_currency": base,
            "quote_currency": quote,
            "base_amount": 1,
            "buy_rate": 0,
            "sell_rate": 0,
        }
    return asdict(rate)


@router.get("/{rate_id}")
def get_rate(
    rate_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    rate = _rate_repo.get_by_id(rate_id)
    if rate is None:
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    return asdict(rate)


@router.post("/")
def create_rate(
    body: RateUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    rate_id = _rate_repo.create(_normalize_rate_payload(body.model_dump()))
    return {"message": "Rate saved", "id": rate_id}


@router.patch("/{rate_id}")
def update_rate(
    rate_id: int,
    body: RatePatchRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    data = _normalize_rate_payload(body.model_dump(exclude_none=True))
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    if not _rate_repo.update(rate_id, data):
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    return {"message": "Rate updated"}


@router.delete("/{rate_id}")
def delete_rate(
    rate_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    if not _rate_repo.delete(rate_id):
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    return {"message": "Rate deleted"}
