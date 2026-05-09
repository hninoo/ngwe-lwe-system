from typing import Optional

from backend.database import get_cursor


class VaultTransactionRepository:
    """Immutable audit trail for all inter-vault denomination movements."""

    def record_bulk(
        self,
        txn_type: str,
        denominations: dict[int, int],
        performed_by: int,
        float_id: Optional[int] = None,
        verified_by: Optional[int] = None,
        transaction_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> None:
        rows = [
            (txn_type, float_id, denom, qty, transaction_id, performed_by, verified_by, note)
            for denom, qty in denominations.items()
            if qty > 0
        ]
        if not rows:
            return
        with get_cursor(commit=True) as cursor:
            cursor.executemany(
                """INSERT INTO vault_transactions
                   (txn_type, float_id, denomination, quantity,
                    transaction_id, performed_by, verified_by, note)
                   VALUES (?,?,?,?,?,?,?,?)""",
                rows,
            )

    def get_by_float(self, float_id: int) -> list[dict]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM vault_transactions WHERE float_id = ? ORDER BY created_at",
                (float_id,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_recent(self, limit: int = 200) -> list[dict]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM vault_transactions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cursor.fetchall()]
