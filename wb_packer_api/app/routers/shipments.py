# app/routers/shipments.py
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..database import get_connection
from ..models import ShipmentCreate, ShipmentUpdate, ShipmentOut

router = APIRouter()


def _row_to_shipment(row) -> ShipmentOut:
    import json
    return ShipmentOut(
        id=row[0], destination_name=row[1], font_size=row[2],
        label_font_size=row[3], theme=row[4],
        removed_items=json.loads(row[5]) if row[5] else {},
        parent_group=row[6],
        properties=json.loads(row[7]) if row[7] else {},
        archived=bool(row[8]),
        archived_date=row[9].isoformat() if row[9] else None,
        archived_by=row[10],
    )


@router.get("")
async def list_shipments(
    archived: bool = False,
    limit: int = 100,
    offset: int = 0,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, destination_name, font_size, label_font_size, theme, "
                "removed_items, parent_group, properties, archived, archived_date, archived_by "
                "FROM shipments WHERE archived = %s ORDER BY destination_name LIMIT %s OFFSET %s",
                (archived, limit, offset),
            )
            rows = cur.fetchall()
    return {"shipments": [_row_to_shipment(r) for r in rows]}


@router.get("/{shipment_id}")
async def get_shipment(shipment_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, destination_name, font_size, label_font_size, theme, "
                "removed_items, parent_group, properties, archived, archived_date, archived_by "
                "FROM shipments WHERE id = %s", (shipment_id,)
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Shipment not found")
    return {"shipment": _row_to_shipment(row)}


@router.get("/by-name/{name}")
async def get_shipment_by_name(name: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, destination_name, font_size, label_font_size, theme, "
                "removed_items, parent_group, properties, archived, archived_date, archived_by "
                "FROM shipments WHERE destination_name = %s", (name,)
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Shipment not found")
    return {"shipment": _row_to_shipment(row)}


@router.post("", status_code=201)
async def create_shipment(data: ShipmentCreate):
    import json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shipments (destination_name, font_size, label_font_size, theme, "
                "removed_items, parent_group, properties, archived, archived_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (data.destination_name, data.font_size, data.label_font_size, data.theme,
                 json.dumps(data.removed_items, ensure_ascii=False),
                 data.parent_group,
                 json.dumps(data.properties, ensure_ascii=False),
                 data.archived, data.archived_by),
            )
            shipment_id = cur.fetchone()[0]
    return {"id": shipment_id, "message": "Shipment created"}


@router.put("/{shipment_id}")
async def update_shipment(shipment_id: int, data: ShipmentUpdate):
    import json
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, "No fields to update")

    set_parts = []
    params = []
    for key, val in fields.items():
        if key in ("removed_items", "properties"):
            val = json.dumps(val, ensure_ascii=False)
            key = f"{key} = %s"
        else:
            key = f"{key} = %s"
        set_parts.append(key)
        params.append(val)

    params.append(shipment_id)
    sql = f"UPDATE shipments SET {', '.join(set_parts)} WHERE id = %s"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.rowcount == 0:
                raise HTTPException(404, "Shipment not found")
    return {"message": "Shipment updated"}


@router.delete("/{shipment_id}")
async def delete_shipment(shipment_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shipments WHERE id = %s", (shipment_id,))
            if cur.rowcount == 0:
                raise HTTPException(404, "Shipment not found")
    return {"message": "Shipment deleted"}


@router.post("/{shipment_id}/archive")
async def archive_shipment(shipment_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE shipments SET archived = TRUE, archived_date = CURRENT_TIMESTAMP WHERE id = %s",
                (shipment_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Shipment not found")
    return {"message": "Shipment archived"}


@router.post("/{shipment_id}/unarchive")
async def unarchive_shipment(shipment_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE shipments SET archived = FALSE, archived_date = NULL WHERE id = %s",
                (shipment_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Shipment not found")
    return {"message": "Shipment unarchived"}
