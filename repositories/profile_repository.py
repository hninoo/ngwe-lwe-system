from repositories.transaction_ui_repository import TransactionUiRepository


class ProfileRepository:
    def __init__(self, transaction_repository: TransactionUiRepository) -> None:
        self._transactions = transaction_repository

    @property
    def current_user(self) -> dict:
        return self._transactions.current_user

    def change_password(self, old_password: str, new_password: str) -> dict:
        return self._transactions.change_password(old_password, new_password)

    def set_user_pin(self, user_id: int, pin: str) -> dict:
        return self._transactions.set_user_pin(user_id, pin)

    def change_pin(self, current_pin: str, new_pin: str) -> dict:
        return self._transactions.change_pin(current_pin, new_pin)
