# app/routers/admin.py
import json
import logging

from fastapi import APIRouter

from ..database import get_connection
from ..models import ImportData

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/db-info")
async def db_info():
    with get_connection() as conn:
        with conn.cursor() as cur:
            info = {}
            for table in ["shipments", "packer_users", "app_settings", "sku", "stock_cache"]:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                info[table] = cur.fetchone()[0]
            cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            info["db_size"] = cur.fetchone()[0]
    return info


@router.get("/export")
async def export_data():
    data = {}
    tables = ["shipments", "shipment_items", "boxes", "box_items", "sku", "stock_cache",
              "packer_users", "app_settings", "window_state", "user_sessions",
              "item_locks", "cache_invalidation"]
    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in tables:
                try:
                    cur.execute(f"SELECT * FROM {table}")
                    cols = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    data[table] = [dict(zip(cols, r)) for r in rows]
                except Exception:
                    data[table] = []
    return data


@router.post("/import")
async def import_data(data: ImportData):
    with get_connection() as conn:
        with conn.cursor() as cur:
            for s in data.shipments:
                cur.execute(
                    "INSERT INTO shipments (destination_name, font_size, label_font_size, theme, "
                    "removed_items, parent_group, properties, archived) "
                    "VALUES (%(destination_name)s, %(font_size)s, %(label_font_size)s, %(theme)s, "
                    "%(removed_items)s, %(parent_group)s, %(properties)s, %(archived)s) "
                    "ON CONFLICT DO NOTHING",
                    s,
                )
            for u in data.users:
                cols = ", ".join(u.keys())
                placeholders = ", ".join(["%(" + k + ")s" for k in u])
                cur.execute(
                    f"INSERT INTO packer_users ({cols}) VALUES ({placeholders}) "
                    f"ON CONFLICT (username) DO UPDATE SET {', '.join([f'{k}=EXCLUDED.{k}' for k in u])}",
                    u,
                )
            for kv in data.settings:
                cur.execute(
                    "INSERT INTO app_settings (key, value) VALUES (%(key)s, %(value)s) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    kv,
                )
    return {"message": "Data imported"}


@router.post("/clear")
async def clear_database():
    tables = ["box_items", "boxes", "shipment_items", "shipments", "user_sessions",
              "item_locks", "cache_invalidation", "sku", "stock_cache",
              "packer_users", "app_settings", "window_state"]
    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in tables:
                cur.execute(f"DELETE FROM {table}")
    return {"message": "Database cleared"}
