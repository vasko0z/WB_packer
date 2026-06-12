# app/routers/settings.py
from fastapi import APIRouter, HTTPException

from ..database import get_connection
from ..models import AppSettingCreate

router = APIRouter()


@router.get("/{key}")
async def get_setting(key: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Setting not found")
    return {"key": key, "value": row[0]}


@router.put("/{key}")
async def save_setting(key: str, data: AppSettingCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, data.value),
            )
    return {"message": "Setting saved"}
