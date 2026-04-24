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
            additional_fee_amount=float(row.get("additional_fee_amount", 0)),
            balance_change=float(row["balance_change"]),
            currency=row["currency"],
            exchange_rate=float(row["exchange_rate"]) if row.get("exchange_rate") else None,
            fee_account_id=row.get("fee_account_id"),
            screenshot_path=row.get("screenshot_path"),
            note=row.get("note"),
            created_by=row["created_by"],
            created_at=row["created_at"],
            cash_approved_by=row.get("cash_approved_by"),
            cash_approved_at=row.get("cash_approved_at"),
        )

    def get_by_date_range(
        self, start: datetime, end: datetime
    ) -> list[Transaction]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM transactions "
                "WHERE created_at BETWEEN ? AND ? "
                "ORDER BY created_at DESC",
                (start, end),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_by_employee(self, user_id: int) -> list[Transaction]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM transactions "
                "WHERE created_by = ? "
                "ORDER BY created_at DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_recent(self, limit: int = 50) -> list[Transaction]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM transactions "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_all_filtered(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        txn_type: Optional[str] = None,
        account_id: Optional[int] = None,
        limit: int = 200,
    ) -> list["Transaction"]:
        conditions: list[str] = []
        params: list = []
        if date_from:
            conditions.append("date(created_at) >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("date(created_at) <= ?")
            params.append(date_to)
        if txn_type:
            conditions.append("transaction_type = ?")
            params.append(txn_type)
        if account_id is not None:
            conditions.append("(account_id = ? OR to_account_id = ?)")
            params.extend([account_id, account_id])
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)
        with get_cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM transactions {where} ORDER BY created_at DESC LIMIT ?",
                tuple(params),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_by_date(self, date_str: str) -> list[Transaction]:
        """Return all transactions for a given date (YYYY-MM-DD)."""
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM transactions "
                "WHERE date(created_at) = ? "
                "ORDER BY created_at DESC",
                (date_str,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def approve(self, txn_id: int, approved_by: int) -> Optional[Transaction]:
        """Mark a transaction as cash-approved."""
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE transactions SET cash_approved_by=?, cash_approved_at=datetime('now') "
                "WHERE id=?",
                (approved_by, txn_id),
            )
            cursor.execute("SELECT * FROM transactions WHERE id=?", (txn_id,))
            row = cursor.fetchone()
        return self._row_to_model(row) if row else None
