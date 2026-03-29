from datetime import datetime
from typing import Optional

from backend.database import get_cursor
from models.transaction import Transaction
from repositories.base_repository import BaseRepository


class TransactionRepository(BaseRepository):

    @property
    def table(self) -> str:
        return "transactions"

    def _row_to_model(self, row: dict) -> Transaction:
        return Transaction(
            id=row["id"],
            transaction_type=row["transaction_type"],
            account_id=row["account_id"],
            to_account_id=row.get("to_account_id"),
            customer_name=row.get("customer_name"),
            customer_phone=row.get("customer_phone"),
            amount=float(row["amount"]),
            commission_amount=float(row["commission_amount"]),
            customer_fee=float(row["customer_fee"]),
            balance_change=float(row["balance_change"]),
            currency=row["currency"],
            exchange_rate=float(row["exchange_rate"]) if row.get("exchange_rate") else None,
            fee_account_id=row.get("fee_account_id"),
            screenshot_path=row.get("screenshot_path"),
            note=row.get("note"),
            created_by=row["created_by"],
            created_at=row["created_at"],
        )

    def get_by_date_range(
        self, start: datetime, end: datetime
    ) -> list[Transaction]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM transactions "
                "WHERE created_at BETWEEN %s AND %s "
                "ORDER BY created_at DESC",
                (start, end),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_by_employee(self, user_id: int) -> list[Transaction]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM transactions "
                "WHERE created_by = %s "
                "ORDER BY created_at DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_recent(self, limit: int = 50) -> list[Transaction]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM transactions "
                "ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]
