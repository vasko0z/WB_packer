# app/routers/users.py
from fastapi import APIRouter, HTTPException

from ..database import get_connection
from ..models import PackerUserSettingsCreate

router = APIRouter()

ALL_COLUMNS = [
    "current_shipment", "font_size", "label_font_size", "current_theme",
    "ok_sound", "error_sound", "tone_sound", "sound_volume", "colored_buttons",
    "show_sku", "show_name", "show_total", "show_stock", "hide_completed",
    "shipment_columns_width", "box_columns_width", "main_splitter_sizes",
    "window_width", "window_height", "window_x", "window_y",
]


def _row_to_user(row):
    d = {"username": row[0]}
    for i, col in enumerate(ALL_COLUMNS, start=1):
        d[col] = row[i] if i < len(row) else None
    return d


@router.get("")
async def list_users():
    cols = ", ".join(ALL_COLUMNS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT username, {cols} FROM packer_users ORDER BY username")
            rows = cur.fetchall()
    return {"users": [_row_to_user(r) for r in rows]}


@router.get("/{username}")
async def get_user(username: str):
    cols = ", ".join(ALL_COLUMNS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT username, {cols} FROM packer_users WHERE username = %s", (username,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    return {"user": _row_to_user(row)}


@router.put("/{username}")
async def save_user(username: str, data: PackerUserSettingsCreate):
    cols = ", ".join(ALL_COLUMNS)
    placeholders = ", ".join(["%s"] * len(ALL_COLUMNS))
    updates = ", ".join([f"{c} = EXCLUDED.{c}" for c in ALL_COLUMNS])
    vals = tuple(getattr(data, c) for c in ALL_COLUMNS)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO packer_users (username, {cols}) VALUES (%s, {placeholders}) "
                f"ON CONFLICT (username) DO UPDATE SET {updates}",
                (username, *vals),
            )
    return {"message": "User settings saved"}


@router.delete("/{username}")
async def delete_user(username: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM packer_users WHERE username = %s", (username,))
            if cur.rowcount == 0:
                raise HTTPException(404, "User not found")
    return {"message": "User deleted"}
