# app/routers/moysklad.py
import logging

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..models import MoyskladSettings
from ..services.moysklad_service import MoyskladService

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_service():
    return MoyskladService(token=settings.MOYSKLAD_TOKEN or "")


@router.get("/settings")
async def get_moysklad_settings():
    return {
        "token": settings.MOYSKLAD_TOKEN,
        "enabled": bool(settings.MOYSKLAD_TOKEN),
        "stores": [],
    }


@router.put("/settings")
async def save_moysklad_settings(data: MoyskladSettings):
    # In a real deploy, persist to DB
    return {"message": "Moysklad settings saved (not persisted in this demo)"}


@router.post("/sync")
async def sync_moysklad(shipment_id: int = None):
    try:
        svc = _get_service()
        result = svc.sync_stocks(shipment_id=shipment_id)
        return {"success": True, **result}
    except Exception as e:
        logger.exception("Moysklad sync failed")
        raise HTTPException(500, f"Sync failed: {e}")
