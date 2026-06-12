# app/routers/sku.py
from typing import List

from fastapi import APIRouter, HTTPException

from ..database import get_connection
from ..models import SKUCreate

router = APIRouter()


@router.get("")
async def list_sku(barcodes: str = ""):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if barcodes:
                bc_list = [b.strip() for b in barcodes.split(",") if b.strip()]
                placeholders = ",".join(["%s"] * len(bc_list))
                cur.execute(
                    f"SELECT barcode, article, name FROM sku WHERE barcode IN ({placeholders})",
                    bc_list,
                )
            else:
                cur.execute("SELECT barcode, article, name FROM sku ORDER BY barcode")
            rows = cur.fetchall()
    return {
        "sku": [
            {"barcode": r[0], "article": r[1] or "", "name": r[2] or ""}
            for r in rows
        ]
    }


@router.get("/{barcode}")
async def get_sku(barcode: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT barcode, article, name FROM sku WHERE barcode = %s", (barcode,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "SKU not found")
    return {
        "sku": {"barcode": row[0], "article": row[1] or "", "name": row[2] or ""}
    }


@router.post("")
async def bulk_upsert_sku(sku_list: List[SKUCreate]):
    with get_connection() as conn:
        with conn.cursor() as cur:
            for s in sku_list:
                cur.execute(
                    "INSERT INTO sku (barcode, article, name) VALUES (%s,%s,%s) "
                    "ON CONFLICT (barcode) DO UPDATE SET article=EXCLUDED.article, name=EXCLUDED.name, "
                    "updated_at=CURRENT_TIMESTAMP",
                    (s.barcode, s.article, s.name),
                )
    return {"message": f"{len(sku_list)} SKUs upserted"}


@router.delete("")
async def clear_sku():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sku")
    return {"message": "SKU table cleared"}
