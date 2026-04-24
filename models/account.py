from dataclasses import dataclass
from typing import Optional


@dataclass
class Account:
    id: Optional[int] = None
    service_type_id: Optional[int] = None   # FK → service_types (replaces service_id + service_type TEXT)
    company_id: Optional[int] = None         # denormalized from service_types JOIN, for display
    account_name: Optional[str] = None
    phone_number: Optional[str] = None
    balance: Optional[float] = None
    commission_rate: Optional[float] = None  # deprecated — use commission_tiers
    is_active: Optional[bool] = None
