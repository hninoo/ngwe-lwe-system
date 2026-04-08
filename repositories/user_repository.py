from typing import Optional

from backend.database import get_cursor
from models.user import User
from repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):

    @property
    def table(self) -> str:
        return "users"

    def _row_to_model(self, row: dict) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            full_name=row["full_name"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            pin_hash=row.get("pin_hash"),
        )

    def get_by_username(self, username: str) -> Optional[User]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()
        return self._row_to_model(row) if row else None

    def get_password_hash(self, username: str) -> Optional[str]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT password_hash FROM users WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()
        return row["password_hash"] if row else None

    def get_pin_hash(self, user_id: int) -> Optional[str]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT pin_hash FROM users WHERE id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
        return row["pin_hash"] if row else None

    def get_employees(self) -> list[User]:
        """Return all active users with role='employee'."""
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE role = 'employee' AND is_active = 1 ORDER BY full_name"
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def update_is_active(self, user_id: int, is_active: bool) -> bool:
        return self.update(user_id, {"is_active": is_active})
