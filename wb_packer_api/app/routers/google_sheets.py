# app/routers/google_sheets.py
import json
import logging

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..models import GsheetsImportRequest, GsheetsUpdateRequest
from ..services.google_sheets_service import GoogleSheetsService

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_service():
    return GoogleSheetsService(
        credentials_json=settings.GSHEETS_CREDENTIALS,
        default_spreadsheet_id=settings.GSHEETS_SPREADSHEET_ID,
    )


@router.get("/sheets")
async def list_sheets(spreadsheet_id: str = ""):
    try:
        svc = _get_service()
        sheets = svc.get_sheets(spreadsheet_id or settings.GSHEETS_SPREADSHEET_ID)
        return {"sheets": sheets}
    except Exception as e:
        raise HTTPException(500, f"Failed to list sheets: {e}")


@router.post("/import")
async def import_from_gsheets(data: GsheetsImportRequest):
    try:
        svc = _get_service()
        result = svc.import_shipment(
            spreadsheet_id=data.spreadsheet_id,
            sheet_name=data.sheet_name,
            destination_name=data.destination_name,
            is_group_shipment=data.is_group_shipment,
            font_size=data.font_size,
            label_font_size=data.label_font_size,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.exception("Google Sheets import failed")
        raise HTTPException(500, f"Import failed: {e}")


@router.post("/update/{group_id}")
async def update_group_from_gsheets(group_id: int, data: GsheetsUpdateRequest):
    try:
        svc = _get_service()
        result = svc.update_group_shipment(
            group_id=group_id,
            spreadsheet_id=data.spreadsheet_id,
            sheet_name=data.sheet_name,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.exception("Google Sheets update failed")
        raise HTTPException(500, f"Update failed: {e}")
