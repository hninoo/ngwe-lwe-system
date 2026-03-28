from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: Optional[int] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None  # 'owner' | 'employee'
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
