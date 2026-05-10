from typing import Optional

from backend.database import get_cursor


class DailyReconciliationRepository:

    def save(self, data: dict) -> int:
        with get_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO daily_reconciliation_logs (
                    recon_date, closed_by,
                    total_cash_in, total_cash_out, total_transfer, total_exchange,
                    total_commission, total_customer_fees,
                    main_vault_total, employee_floats_total,
                    total_cash, total_digital, grand_total,
                    employee_snapshots, account_snapshots, vault_snapshot, notes
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data["recon_date"], data["closed_by"],
                data.get("total_cash_in", 0), data.get("total_cash_out", 0),
                data.get("total_transfer", 0), data.get("total_exchange", 0),
                data.get("total_commission", 0), data.get("total_customer_fees", 0),
                data.get("main_vault_total", 0), data.get("employee_floats_total", 0),
                data.get("total_cash", 0), data.get("total_digital", 0),
                data.get("grand_total", 0),
                data.get("employee_snapshots"), data.get("account_snapshots"),
                data.get("vault_snapshot"), data.get("notes"),
            ))
            return cursor.lastrowid

    def get_recent(self, limit: int = 30) -> list[dict]:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT r.*, u.full_name AS closed_by_name
                FROM daily_reconciliation_logs r
                JOIN users u ON u.id = r.closed_by
                ORDER BY r.closed_at DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def get_by_date(self, date_str: str) -> Optional[dict]:
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT r.*, u.full_name AS closed_by_name
                FROM daily_reconciliation_logs r
                JOIN users u ON u.id = r.closed_by
                WHERE r.recon_date = ?
                ORDER BY r.closed_at DESC LIMIT 1
            """, (date_str,))
            row = cursor.fetchone()
        return dict(row) if row else None
