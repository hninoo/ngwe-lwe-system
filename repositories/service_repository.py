from typing import Optional

from backend.database import get_cursor
from models.service import Service
from repositories.base_repository import BaseRepository


class ServiceRepository(BaseRepository):

    @property
    def table(self) -> str:
        return "services"

    def _row_to_model(self, row: dict) -> Service:
        return Service(
            id=row["id"],
            name=row["name"],
            service_type=row["service_type"],
            default_customer_fee=float(row["default_customer_fee"]),
            is_active=bool(row["is_active"]),
        )

    def get_all_active(self) -> list[Service]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM services WHERE is_active = TRUE"
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]
