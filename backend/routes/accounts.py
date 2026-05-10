from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import json

from backend.auth import get_current_user
from backend.database import atomic, get_cursor
from backend.money import normalize_money
from repositories.account_repository import AccountRepository
from viewmodels.account_viewmodel import AccountViewModel

router = APIRouter(prefix="/accounts", tags=["accounts"])


class BalanceAdjust(BaseModel):
    amount: float
    remark: str = ""


class AccountCreate(BaseModel):
    service_type_id: int
    account_name: str
    phone_number: str
    balance: float = 0.0
    is_fee_account: bool = False


class AccountUpdate(BaseModel):
    service_type_id: Optional[int] = None
    account_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None
    is_fee_account: Optional[bool] = None


_account_vm = AccountViewModel()
_account_repo = AccountRepository()


@router.get("/")
def get_accounts(
    company_id: Optional[int] = None,
    service_type_id: Optional[int] = None,
    fee_only: bool = False,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    if fee_only:
        accounts = _account_repo.get_fee_accounts()
    elif service_type_id is not None:
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
    try:
        balance = normalize_money(body.balance)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    account_id = _account_repo.create({
        "service_type_id": body.service_type_id,
        "account_name": body.account_name,
        "phone_number": body.phone_number,
        "balance": balance,
        "is_fee_account": int(body.is_fee_account),
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
        return {"message": "No changes", "account_id": account_id}
    if "is_fee_account" in data:
        data["is_fee_account"] = int(data["is_fee_account"])
    if "is_active" in data:
        data["is_active"] = int(data["is_active"])
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



@router.post("/{account_id}/balance-adjust")
def adjust_balance(
    account_id: int,
    body: BalanceAdjust,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    if _account_repo.get_by_id(account_id) is None:
        raise HTTPException(status_code=404, detail="Account not found")
    try:
        amount = normalize_money(body.amount)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    with atomic():
        # Re-read inside the write lock so concurrent adjustments don't skew the audit log.
        account = _account_repo.get_by_id(account_id)
        old_balance = account.balance
        new_balance = round(old_balance + amount, 2)
        _account_repo.increment_balance(account_id, amount)
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO activity_logs (user_id, action, entity_type, entity_id, details) "
                "VALUES (?, ?, 'account', ?, ?)",
                (
                    current_user["user_id"],
                    "balance_adjust",
                    account_id,
                    json.dumps({
                        "amount": amount,
                        "old_balance": old_balance,
                        "new_balance": new_balance,
                        "remark": body.remark,
                    }),
                ),
            )
    return {
        "message": "Balance adjusted",
        "account_id": account_id,
        "old_balance": old_balance,
        "new_balance": new_balance,
    }
