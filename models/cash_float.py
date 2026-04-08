from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CashFloatDenomination:
    id: Optional[int] = None
    float_id: Optional[int] = None
    denomination: Optional[int] = None
    quantity: Optional[int] = None


@dataclass
class CashFloat:
    id: Optional[int] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    issued_by: Optional[int] = None
    issued_by_name: Optional[str] = None
    status: Optional[str] = None  # PENDING|ACTIVE|CLOSED
    total_amount: Optional[float] = None
    received_at: Optional[str] = None
    closed_at: Optional[str] = None
    closing_total: Optional[float] = None
    note: Optional[str] = None
    created_at: Optional[str] = None
    denominations: list = field(default_factory=list)
