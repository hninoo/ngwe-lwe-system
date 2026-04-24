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
            service_type_id=row["service_type_id"],
            company_id=row.get("company_id"),
            account_name=row["account_name"],
            phone_number=row["phone_number"],
            balance=float(row["balance"]),
            commission_rate=float(row["commission_rate"]),
            is_active=bool(row["is_active"]),
        )

    def get_all_active(self) -> list[Account]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT a.*, st.company_id "
                "FROM accounts a "
                "JOIN service_types st ON a.service_type_id = st.id "
                "JOIN companies c ON st.company_id = c.id "
                "WHERE a.is_active = 1 AND st.is_active = 1 AND c.is_active = 1"
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_by_id(self, record_id: int) -> Optional[Account]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT a.*, st.company_id "
                "FROM accounts a "
                "JOIN service_types st ON a.service_type_id = st.id "
                "WHERE a.id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
        return self._row_to_model(row) if row else None

    def get_by_service_type(self, service_type_id: int) -> list[Account]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT a.*, st.company_id "
                "FROM accounts a "
                "JOIN service_types st ON a.service_type_id = st.id "
                "WHERE a.service_type_id = ? AND a.is_active = 1",
                (service_type_id,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_by_company(self, company_id: int) -> list[Account]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT a.*, st.company_id "
                "FROM accounts a "
                "JOIN service_types st ON a.service_type_id = st.id "
                "WHERE st.company_id = ? AND a.is_active = 1",
                (company_id,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def update_balance(self, account_id: int, new_balance: float) -> bool:
        return self.update(account_id, {"balance": new_balance})
