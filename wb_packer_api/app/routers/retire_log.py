# app/routers/retire_log.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime

from ..database import get_connection
from ..models import RetireLogCreate, RetireLogOut

router = APIRouter()


def _row_to_log(row) -> RetireLogOut:
    return RetireLogOut(
        id=row[0],
        shipment_id=row[1],
        barcode=row[2],
        qty=row[3],
        reason=row[4] or "",
        retired_by=row[5] or "",
        retired_at=row[6].isoformat() if row[6] else None,
    )


@router.get("/{shipment_id}/retire-log")
async def list_retire_log(shipment_id: int, barcode: Optional[str] = None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if barcode:
                cur.execute(
                    "SELECT id, shipment_id, barcode, qty, reason, retired_by, retired_at "
                    "FROM item_retire_log WHERE shipment_id = %s AND barcode = %s ORDER BY retired_at DESC",
                    (shipment_id, barcode),
                )
            else:
                cur.execute(
                    "SELECT id, shipment_id, barcode, qty, reason, retired_by, retired_at "
                    "FROM item_retire_log WHERE shipment_id = %s ORDER BY retired_at DESC",
                    (shipment_id,),
                )
            rows = cur.fetchall()
    return {"logs": [_row_to_log(r) for r in rows]}


@router.post("/{shipment_id}/retire-log", status_code=201)
async def create_retire_log(shipment_id: int, data: RetireLogCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO item_retire_log (shipment_id, barcode, qty, reason, retired_by) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (shipment_id, data.barcode, data.qty, data.reason, data.retired_by),
            )
            log_id = cur.fetchone()[0]
    return {"id": log_id, "message": "Log entry created"}


@router.post("/{shipment_id}/retire-log/batch", status_code=201)
async def bulk_create_retire_log(shipment_id: int, items: List[RetireLogCreate]):
    with get_connection() as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(
                    "INSERT INTO item_retire_log (shipment_id, barcode, qty, reason, retired_by) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (shipment_id, item.barcode, item.qty, item.reason, item.retired_by),
                )
    return {"message": f"{len(items)} log entries created"}


@router.delete("/{shipment_id}/retire-log/{log_id}")
async def delete_retire_log(shipment_id: int, log_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM item_retire_log WHERE id = %s AND shipment_id = %s",
                (log_id, shipment_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Log entry not found")
    return {"message": "Log entry deleted"}


@router.delete("/{shipment_id}/retire-log")
async def clear_retire_log(shipment_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM item_retire_log WHERE shipment_id = %s", (shipment_id,))
            deleted = cur.rowcount
    return {"message": f"Cleared {deleted} log entries"}
