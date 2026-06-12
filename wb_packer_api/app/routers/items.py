# app/routers/items.py
from fastapi import APIRouter, HTTPException
from typing import List

from ..database import get_connection
from ..models import ShipmentItemCreate, ShipmentItemUpdate, ShipmentItemOut

router = APIRouter()


def _row_to_item(row) -> ShipmentItemOut:
    return ShipmentItemOut(
        id=row[0], barcode=row[2], sku=row[3] or "",
        total_qty=row[4], allocated_qty=row[5],
    )


@router.get("/{shipment_id}/items")
async def list_items(shipment_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, shipment_id, barcode, sku, total_qty, allocated_qty "
                "FROM shipment_items WHERE shipment_id = %s ORDER BY barcode",
                (shipment_id,),
            )
            rows = cur.fetchall()
    return {"items": [_row_to_item(r) for r in rows]}


@router.put("/{shipment_id}/items/{barcode}")
async def update_item(shipment_id: int, barcode: str, data: ShipmentItemUpdate):
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, "No fields to update")

    set_parts = [f"{k} = %s" for k in fields]
    params = list(fields.values()) + [shipment_id, barcode]
    sql = f"UPDATE shipment_items SET {', '.join(set_parts)} WHERE shipment_id = %s AND barcode = %s"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.rowcount == 0:
                raise HTTPException(404, "Item not found")
    return {"message": "Item updated"}


@router.post("/{shipment_id}/items")
async def bulk_create_items(shipment_id: int, items: List[ShipmentItemCreate]):
    from ..database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(
                    "INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty) "
                    "VALUES (%s,%s,%s,%s,%s) "
                    "ON CONFLICT (shipment_id, barcode) DO UPDATE SET sku=EXCLUDED.sku, "
                    "total_qty=EXCLUDED.total_qty, allocated_qty=EXCLUDED.allocated_qty",
                    (shipment_id, item.barcode, item.sku, item.total_qty, item.allocated_qty),
                )
    return {"message": f"{len(items)} items created/updated"}


@router.delete("/{shipment_id}/items/{barcode}")
async def delete_item(shipment_id: int, barcode: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM shipment_items WHERE shipment_id = %s AND barcode = %s",
                (shipment_id, barcode),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Item not found")
    return {"message": "Item deleted"}
