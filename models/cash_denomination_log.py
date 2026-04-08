from dataclasses import dataclass
from typing import Optional


@dataclass
class CashDenominationLog:
    id: Optional[int] = None
    entry_type: Optional[str] = None  # vault_in|vault_out|float_returned|adjustment
    denomination: Optional[int] = None
    quantity: Optional[int] = None
    float_id: Optional[int] = None
    created_by: Optional[int] = None
    note: Optional[str] = None
    created_at: Optional[str] = None
