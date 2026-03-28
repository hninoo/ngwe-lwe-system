from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ExchangeRate:
    id: Optional[int] = None
    currency_pair: Optional[str] = None  # e.g. 'MMK/THB'
    buy_rate: Optional[float] = None
    sell_rate: Optional[float] = None
    updated_at: Optional[datetime] = None
