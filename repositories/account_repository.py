from typing import Optional

from backend.database import get_cursor
from models.account import Account
from repositories.base_repository import BaseRepository


class AccountRepository(BaseRepository):

    @property
    def table(self) -> str:
        return "accounts"

    def _row_to_model(self, row: dict) -> Account:
        return Account(
            id=row["id"],
            service_id=row["service_id"],
            account_name=row["account_name"],
            account_type=row["account_type"],
            phone_number=row["phone_number"],
            balance=float(row["balance"]),
            commission_rate=float(row["commission_rate"]),
            is_active=bool(row["is_active"]),
        )

    def get_by_service(self, service_id: int) -> list[Account]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM accounts WHERE service_id = %s AND is_active = TRUE",
                (service_id,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_all_active(self) -> list[Account]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM accounts WHERE is_active = TRUE"
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def update_balance(self, account_id: int, new_balance: float) -> bool:
        return self.update(account_id, {"balance": new_balance})
