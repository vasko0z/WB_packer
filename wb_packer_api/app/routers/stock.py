# app/routers/stock.py
from fastapi import APIRouter, HTTPException

from ..database import get_connection
from ..models import StockBatchRequest, StockUpdate

router = APIRouter()


@router.get("/{barcode}")
async def get_stock(barcode: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT quantity FROM stock_cache WHERE barcode = %s", (barcode,))
            row = cur.fetchone()
    return {"barcode": barcode, "stock": row[0] if row else 0}


@router.post("/batch")
async def get_stock_batch(data: StockBatchRequest):
    if not data.barcodes:
        return {"stocks": {}}
    placeholders = ",".join(["%s"] * len(data.barcodes))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT barcode, quantity FROM stock_cache WHERE barcode IN ({placeholders})",
                data.barcodes,
            )
            rows = cur.fetchall()
    return {"stocks": {r[0]: r[1] or 0 for r in rows}}


@router.put("/{barcode}")
async def set_stock(barcode: str, data: StockUpdate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO stock_cache (barcode, quantity) VALUES (%s, %s) "
                "ON CONFLICT (barcode) DO UPDATE SET quantity = EXCLUDED.quantity, "
                "updated_at = CURRENT_TIMESTAMP",
                (barcode, data.quantity),
            )
    return {"barcode": barcode, "stock": data.quantity}
