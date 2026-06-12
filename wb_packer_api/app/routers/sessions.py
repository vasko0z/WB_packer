# app/routers/sessions.py
from fastapi import APIRouter

from ..database import get_connection
from ..models import SessionUpdate

router = APIRouter()


@router.put("")
async def update_session(data: SessionUpdate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_sessions (shipment_name, username, last_activity) VALUES (%s, %s, CURRENT_TIMESTAMP) "
                "ON CONFLICT (shipment_name, username) DO UPDATE SET last_activity = CURRENT_TIMESTAMP",
                (data.shipment_name, data.username),
            )
    return {"message": "Session updated"}


@router.delete("/old")
async def cleanup_old_sessions():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_sessions WHERE last_activity < CURRENT_TIMESTAMP - INTERVAL '24 hours'"
            )
            deleted = cur.rowcount
    return {"message": f"Cleaned up {deleted} old sessions"}
