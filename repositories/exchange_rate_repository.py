from typing import Optional

from backend.database import get_cursor
from models.exchange_rate import ExchangeRate
from repositories.base_repository import BaseRepository


class ExchangeRateRepository(BaseRepository):

    @property
    def table(self) -> str:
        return "exchange_rates"

    def _row_to_model(self, row: dict) -> ExchangeRate:
        return ExchangeRate(
            id=row["id"],
            currency_pair=row["currency_pair"],
            buy_rate=float(row["buy_rate"]),
            sell_rate=float(row["sell_rate"]),
            updated_at=row["updated_at"],
        )

    def get_latest(self, currency_pair: str = "MMK/THB") -> Optional[ExchangeRate]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM exchange_rates "
                "WHERE currency_pair = %s "
                "ORDER BY updated_at DESC LIMIT 1",
                (currency_pair,),
            )
            row = cursor.fetchone()
        return self._row_to_model(row) if row else None

    def get_by_pair(self, currency_pair: str) -> list[ExchangeRate]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM exchange_rates "
                "WHERE currency_pair = %s "
                "ORDER BY updated_at DESC",
                (currency_pair,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]
