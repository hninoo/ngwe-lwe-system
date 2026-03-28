from dataclasses import dataclass
from typing import Optional


@dataclass
class Service:
    id: Optional[int] = None
    name: Optional[str] = None
    service_type: Optional[str] = None
    default_customer_fee: Optional[float] = None
    is_active: Optional[bool] = None
