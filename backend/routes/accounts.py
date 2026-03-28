from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from viewmodels.account_viewmodel import AccountViewModel

router = APIRouter(prefix="/accounts", tags=["accounts"])


class BalanceUpdate(BaseModel):
    balance: float


_account_vm = AccountViewModel()


@router.get("/")
def get_accounts(
    service_id: int | None = None,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    if service_id is not None:
        accounts = _account_vm.get_accounts_by_service(service_id)
    else:
        accounts = _account_vm.get_all_active()
    return [asdict(a) for a in accounts]


@router.get("/{account_id}")
def get_account(
    account_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    from repositories.account_repository import AccountRepository
    account = AccountRepository().get_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return asdict(account)


@router.patch("/{account_id}/balance")
def update_balance(
    account_id: int,
    body: BalanceUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    _account_vm.update_balance(account_id, body.balance)
    return {"message": "Balance updated", "account_id": account_id}
