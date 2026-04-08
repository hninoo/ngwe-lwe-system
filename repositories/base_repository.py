from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseRepository(ABC):
    """Abstract base class for all repositories."""

    @property
    @abstractmethod
    def table(self) -> str:
        """Table name for this repository."""

    @abstractmethod
    def _row_to_model(self, row: dict) -> Any:
        """Convert a DB row dict to a model instance."""

    def get_by_id(self, record_id: int) -> Optional[Any]:
        from backend.database import get_cursor

        with get_cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {self.table} WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
        return self._row_to_model(row) if row else None

    def get_all(self) -> list[Any]:
        from backend.database import get_cursor

        with get_cursor() as cursor:
            cursor.execute(f"SELECT * FROM {self.table}")
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def create(self, data: dict) -> int:
        from backend.database import get_cursor

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                tuple(data.values()),
            )
            return cursor.lastrowid

    def update(self, record_id: int, data: dict) -> bool:
        from backend.database import get_cursor

        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                f"UPDATE {self.table} SET {set_clause} WHERE id = ?",
                (*data.values(), record_id),
            )
            return cursor.rowcount > 0

    def delete(self, record_id: int) -> bool:
        from backend.database import get_cursor

        with get_cursor(commit=True) as cursor:
            cursor.execute(
                f"DELETE FROM {self.table} WHERE id = ?",
                (record_id,),
            )
            return cursor.rowcount > 0
