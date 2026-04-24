from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.auth import get_current_user
from backend.database import get_cursor

router = APIRouter(prefix="/activity-logs", tags=["activity_logs"])


@router.get("/")
def get_activity_logs(
    user_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = 200,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")

    conditions: list[str] = []
    params: list = []

    if user_id is not None:
        conditions.append("al.user_id = ?")
        params.append(user_id)
    if entity_type:
        conditions.append("al.entity_type = ?")
        params.append(entity_type)
    if action:
        conditions.append("al.action LIKE ?")
        params.append(f"%{action}%")
    if date:
        conditions.append("date(al.created_at) = ?")
        params.append(date)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(min(limit, 1000))

    with get_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT al.*, u.username, u.full_name
            FROM activity_logs al
            LEFT JOIN users u ON al.user_id = u.id
            {where}
            ORDER BY al.created_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        rows = cursor.fetchall()

    return [dict(r) for r in rows]
