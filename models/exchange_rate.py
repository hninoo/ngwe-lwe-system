from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ExchangeRate:
    id: Optional[int] = None
    base_currency: str = "THB"    # e.g. THB
    quote_currency: str = "MMK"   # e.g. MMK
    base_amount: float = 1.0      # reference quantity of base currency
    buy_rate: Optional[float] = None   # quote per base_amount — business buys base
    sell_rate: Optional[float] = None  # quote per base_amount — business sells base
    updated_at: Optional[datetime] = None
