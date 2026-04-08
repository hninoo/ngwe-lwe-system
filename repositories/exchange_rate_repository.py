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
            base_currency=row["base_currency"],
            quote_currency=row["quote_currency"],
            base_amount=float(row["base_amount"]),
            buy_rate=float(row["buy_rate"]),
            sell_rate=float(row["sell_rate"]),
            updated_at=row["updated_at"],
        )

    def get_latest(
        self,
        base_currency: str = "THB",
        quote_currency: str = "MMK",
    ) -> Optional[ExchangeRate]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM exchange_rates "
                "WHERE base_currency = ? AND quote_currency = ? "
                "ORDER BY updated_at DESC LIMIT 1",
                (base_currency, quote_currency),
            )
            row = cursor.fetchone()
        return self._row_to_model(row) if row else None
