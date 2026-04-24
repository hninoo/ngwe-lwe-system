from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from repositories.account_repository import AccountRepository
from viewmodels.account_viewmodel import AccountViewModel

router = APIRouter(prefix="/accounts", tags=["accounts"])


class BalanceUpdate(BaseModel):
    balance: float


class AccountCreate(BaseModel):
    service_type_id: int
    account_name: str
    phone_number: str
    balance: float = 0.0


class AccountUpdate(BaseModel):
    account_name: Optional[str] = None
    phone_number: Optional[str] = None
    balance: Optional[float] = None
    is_active: Optional[bool] = None


_account_vm = AccountViewModel()
_account_repo = AccountRepository()


@router.get("/")
def get_accounts(
    company_id: Optional[int] = None,
    service_type_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    if service_type_id is not None:
        # service_type already implies company; use service_type filter
        accounts = _account_vm.get_accounts_by_service_type(service_type_id)
    elif company_id is not None:
        accounts = _account_vm.get_accounts_by_company(company_id)
    else:
        accounts = _account_vm.get_all_active()
    return [asdict(a) for a in accounts]


@router.get("/{account_id}")
def get_account(
    account_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    account = _account_vm._account_repo.get_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return asdict(account)


@router.post("/")
def create_account(
    body: AccountCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    account_id = _account_repo.create({
        "service_type_id": body.service_type_id,
        "account_name": body.account_name,
        "phone_number": body.phone_number,
        "balance": body.balance,
    })
    return {"message": "Account created", "account_id": account_id}


@router.patch("/{account_id}")
def update_account(
    account_id: int,
    body: AccountUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    _account_repo.update(account_id, data)
    return {"message": "Account updated", "account_id": account_id}


@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    _account_repo.update(account_id, {"is_active": 0})
    return {"message": "Account deactivated", "account_id": account_id}


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
