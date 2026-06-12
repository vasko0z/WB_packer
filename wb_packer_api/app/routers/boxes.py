# app/routers/boxes.py

from fastapi import APIRouter, HTTPException
from typing import Dict

from ..database import get_connection
from ..models import BoxCreate, BoxUpdate, BoxOut, BoxItemCreate, BoxItemUpdate

router = APIRouter()


def _row_to_box(row) -> BoxOut:
    return BoxOut(
        id=row[0], box_id=row[1],
        is_current=bool(row[2]) if len(row) > 2 else False,
        total_items=0,
    )


# --- Boxes within a shipment ---
@router.get("/shipments/{shipment_id}/boxes")
async def list_boxes(shipment_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, box_id, is_current FROM boxes WHERE shipment_id = %s ORDER BY box_id",
                (shipment_id,),
            )
            rows = cur.fetchall()
    boxes = []
    for r in rows:
        box_id_db = r[0]
        with get_connection() as conn2:
            with conn2.cursor() as cur2:
                cur2.execute("SELECT COALESCE(SUM(qty), 0) FROM box_items WHERE box_id = %s", (box_id_db,))
                total = cur2.fetchone()[0]
        b = BoxOut(id=r[0], box_id=r[1], is_current=bool(r[2]), total_items=total)
        boxes.append(b)
    return {"boxes": boxes}


@router.post("/shipments/{shipment_id}/boxes", status_code=201)
async def create_box(shipment_id: int, data: BoxCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO boxes (shipment_id, box_id, is_current) VALUES (%s,%s,%s) RETURNING id",
                (shipment_id, data.box_id, data.is_current),
            )
            box_id_db = cur.fetchone()[0]
    return {"id": box_id_db, "box_id": data.box_id, "message": "Box created"}


@router.put("/shipments/{shipment_id}/boxes/{box_id}")
async def update_box(shipment_id: int, box_id: str, data: BoxUpdate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if data.box_id is not None and data.box_id != box_id:
                cur.execute(
                    "UPDATE boxes SET box_id = %s WHERE shipment_id = %s AND box_id = %s",
                    (data.box_id, shipment_id, box_id),
                )
            if data.is_current is not None:
                cur.execute(
                    "UPDATE boxes SET is_current = %s WHERE shipment_id = %s AND box_id = %s",
                    (data.is_current, shipment_id, box_id),
                )
    return {"message": "Box updated"}


@router.delete("/shipments/{shipment_id}/boxes/{box_id}")
async def delete_box(shipment_id: int, box_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM boxes WHERE shipment_id = %s AND box_id = %s",
                (shipment_id, box_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Box not found")
    return {"message": "Box deleted"}


# --- Box items via box_items table ---
@router.get("/boxes/{box_id}/items")
async def get_box_items(box_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, barcode, qty FROM box_items WHERE box_id = %s ORDER BY barcode",
                (box_id,),
            )
            rows = cur.fetchall()
    return {"items": [{"id": r[0], "barcode": r[1], "qty": r[2]} for r in rows]}


@router.post("/shipments/{shipment_id}/boxes/{box_id}/items", status_code=201)
async def add_items_to_box(shipment_id: int, box_id: str, items: Dict[str, int]):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM boxes WHERE shipment_id = %s AND box_id = %s", (shipment_id, box_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Box not found")
            box_pk = row[0]
            for barcode, qty in items.items():
                cur.execute("SELECT qty FROM box_items WHERE box_id = %s AND barcode = %s", (box_pk, barcode))
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "UPDATE box_items SET qty = qty + %s WHERE box_id = %s AND barcode = %s",
                        (qty, box_pk, barcode),
                    )
                else:
                    cur.execute(
                        "INSERT INTO box_items (box_id, barcode, qty) VALUES (%s, %s, %s)",
                        (box_pk, barcode, qty),
                    )
    return {"box_id": box_id, "message": "Items added"}


@router.put("/shipments/{shipment_id}/boxes/{box_id}/items/{barcode}")
async def update_box_item(shipment_id: int, box_id: str, barcode: str, data: BoxItemUpdate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM boxes WHERE shipment_id = %s AND box_id = %s", (shipment_id, box_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Box not found")
            box_pk = row[0]
            cur.execute(
                "UPDATE box_items SET qty = %s WHERE box_id = %s AND barcode = %s",
                (data.qty, box_pk, barcode),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Item not found in box")
    return {"barcode": barcode, "qty": data.qty}


@router.delete("/shipments/{shipment_id}/boxes/{box_id}/items/{barcode}")
async def remove_item_from_box(shipment_id: int, box_id: str, barcode: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM boxes WHERE shipment_id = %s AND box_id = %s", (shipment_id, box_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Box not found")
            box_pk = row[0]
            cur.execute(
                "DELETE FROM box_items WHERE box_id = %s AND barcode = %s",
                (box_pk, barcode),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Item not found in box")
    return {"message": "Item removed"}
