from typing import Optional

import bcrypt

from models.user import User
from repositories.user_repository import UserRepository


class AuthViewModel:

    def __init__(self, user_repo: Optional[UserRepository] = None) -> None:
        self._user_repo = user_repo or UserRepository()
        self._current_user: Optional[User] = None

    @property
    def current_user(self) -> Optional[User]:
        return self._current_user

    @property
    def is_logged_in(self) -> bool:
        return self._current_user is not None

    @property
    def is_owner(self) -> bool:
        return self._current_user is not None and self._current_user.role == "owner"

    def login(self, username: str, password: str) -> bool:
        stored_hash = self._user_repo.get_password_hash(username)
        if stored_hash is None:
            return False

        if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
            return False

        user = self._user_repo.get_by_username(username)
        if user is None or not user.is_active:
            return False

        self._current_user = user
        return True

    def logout(self) -> None:
        self._current_user = None
