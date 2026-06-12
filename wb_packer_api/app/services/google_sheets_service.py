# app/services/google_sheets_service.py
import json
import logging
import sys
from typing import Optional, Any

import pandas as pd

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Service for importing shipments from Google Sheets"""

    def __init__(self, credentials_json: str = "", default_spreadsheet_id: str = ""):
        self.credentials_json = credentials_json
        self.default_spreadsheet_id = default_spreadsheet_id
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        import gspread
        from google.oauth2.service_account import Credentials

        if self.credentials_json:
            import json
            creds_dict = json.loads(self.credentials_json)
            creds = Credentials.from_service_account_info(
                creds_dict,
                scopes=[
                    "https://spreadsheets.google.com/feeds",
                    "https://www.googleapis.com/auth/drive",
                ],
            )
        else:
            # Use default credentials (for development)
            from google.auth import default
            creds, _ = default()
            creds = creds.with_scopes([
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ])

        self._client = gspread.authorize(creds)
        return self._client

    def get_sheets(self, spreadsheet_id: str) -> list[dict]:
        client = self._get_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        return [{"title": ws.title, "index": i} for i, ws in enumerate(spreadsheet.worksheets())]

    def get_sheet_data(self, spreadsheet_id: str, sheet_name: str):
        client = self._get_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet.get_all_values()

    def _detect_columns(self, header_row: list[str]) -> dict:
        barcode_col = None
        sku_col = None
        qty_cols = {}

        for i, col in enumerate(header_row):
            col_lower = str(col).lower().strip()
            if any(x in col_lower for x in ["штрихкод", "шк", "barcode"]):
                barcode_col = i
            elif any(x in col_lower for x in ["артикул", "арт", "article"]):
                sku_col = i
            elif any(x in col_lower for x in ["количество", "кол-во", "qty", "quantity"]):
                qty_cols[col] = i

        return {
            "barcode_col": barcode_col,
            "sku_col": sku_col,
            "qty_cols": qty_cols,
        }

    def import_shipment(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        destination_name: Optional[str] = None,
        is_group_shipment: bool = False,
        font_size: int = 10,
        label_font_size: int = 20,
    ) -> dict:
        """Import shipment from Google Sheet"""
        from ..database import get_connection
        from datetime import datetime

        logger.info(f"Importing from Google Sheets: {spreadsheet_id}/{sheet_name}")

        values = self.get_sheet_data(spreadsheet_id, sheet_name)
        if not values:
            raise ValueError("Sheet is empty")

        header_row = values[0]
        col_info = self._detect_columns(header_row)
        if col_info["barcode_col"] is None:
            col_info["barcode_col"] = 0  # fallback to first column

        data_rows = values[1:]

        items = []
        for row in data_rows:
            if len(row) <= col_info["barcode_col"]:
                continue
            barcode = str(row[col_info["barcode_col"]]).strip()
            if not barcode or barcode.lower() == "nan":
                continue

            sku = ""
            if col_info["sku_col"] is not None and len(row) > col_info["sku_col"]:
                sku = str(row[col_info["sku_col"]]).strip()

            qty = 1
            for col_name, col_idx in col_info["qty_cols"].items():
                if len(row) > col_idx:
                    try:
                        qty = int(float(row[col_idx]))
                        break
                    except (ValueError, TypeError):
                        continue

            if is_group_shipment:
                # Detect destination columns beyond barcode/sku/qty
                for i in range(len(header_row)):
                    if i in (col_info["barcode_col"], col_info["sku_col"]):
                        continue
                    header = str(header_row[i]).strip()
                    if not header or header.startswith("Unnamed"):
                        continue
                    if len(row) > i:
                        try:
                            dest_qty = int(float(row[i]))
                            if dest_qty > 0:
                                items.append({
                                    "barcode": barcode,
                                    "sku": sku,
                                    "total_qty": dest_qty,
                                    "destination": header,
                                })
                        except (ValueError, TypeError):
                            continue
            else:
                items.append({
                    "barcode": barcode,
                    "sku": sku,
                    "total_qty": qty,
                    "allocated_qty": 0,
                })

        if not items:
            raise ValueError("No items found in sheet")

        # Create shipment and items in DB
        name = destination_name or f"GS_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        with get_connection() as conn:
            with conn.cursor() as cur:
                if is_group_shipment:
                    # Group shipment: create parent + sub-shipments
                    destinations = set()
                    for item in items:
                        if item.get("destination"):
                            destinations.add(item["destination"])
                    destinations = sorted(destinations)

                    # Create parent shipment
                    parent_name = name
                    cur.execute(
                        "INSERT INTO shipments (destination_name, font_size, label_font_size, theme, properties) "
                        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                        (parent_name, font_size, label_font_size, "macOS",
                         json.dumps({"is_group": True, "sheets": sheet_name}, ensure_ascii=False)),
                    )
                    parent_id = cur.fetchone()[0]

                    # Create sub-shipments for each destination
                    for dest in destinations:
                        sub_name = f"{parent_name}::{dest}"
                        cur.execute(
                            "INSERT INTO shipments (destination_name, font_size, label_font_size, theme, parent_group) "
                            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                            (sub_name, font_size, label_font_size, "macOS", parent_name),
                        )
                        sub_id = cur.fetchone()[0]

                        # Add items for this destination
                        for item in items:
                            if item.get("destination") == dest:
                                cur.execute(
                                    "INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty) "
                                    "VALUES (%s, %s, %s, %s, %s)",
                                    (sub_id, item["barcode"], item["sku"], item["total_qty"], 0),
                                )

                    return {
                        "shipment_id": parent_id,
                        "destination_name": parent_name,
                        "items_count": len(items),
                        "sub_shipments": len(destinations),
                    }
                else:
                    # Regular shipment
                    cur.execute(
                        "INSERT INTO shipments (destination_name, font_size, label_font_size, theme) "
                        "VALUES (%s, %s, %s, %s) RETURNING id",
                        (name, font_size, label_font_size, "macOS"),
                    )
                    shipment_id = cur.fetchone()[0]

                    for item in items:
                        cur.execute(
                            "INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            (shipment_id, item["barcode"], item["sku"], item["total_qty"], item.get("allocated_qty", 0)),
                        )

                    return {
                        "shipment_id": shipment_id,
                        "destination_name": name,
                        "items_count": len(items),
                    }

    def update_group_shipment(self, group_id: int, spreadsheet_id: str, sheet_name: str) -> dict:
        """Update existing group shipment from Google Sheet"""
        from ..database import get_connection

        logger.info(f"Updating group {group_id} from Google Sheets: {spreadsheet_id}/{sheet_name}")

        values = self.get_sheet_data(spreadsheet_id, sheet_name)
        if not values:
            raise ValueError("Sheet is empty")

        header_row = values[0]
        col_info = self._detect_columns(header_row)
        if col_info["barcode_col"] is None:
            col_info["barcode_col"] = 0

        data_rows = values[1:]

        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get parent group
                cur.execute("SELECT destination_name FROM shipments WHERE id = %s", (group_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Group {group_id} not found")
                parent_name = row[0]

                # Get existing sub-shipments
                cur.execute(
                    "SELECT id, destination_name FROM shipments WHERE parent_group = %s",
                    (parent_name,),
                )
                existing = {r[1].split("::")[-1]: r[0] for r in cur.fetchall()}

                updated = 0
                for row in data_rows:
                    if len(row) <= col_info["barcode_col"]:
                        continue
                    barcode = str(row[col_info["barcode_col"]]).strip()
                    if not barcode:
                        continue

                    # Update qty in each sub-shipment
                    for dest_name, dest_id in existing.items():
                        dest_col = None
                        for i, h in enumerate(header_row):
                            if str(h).strip() == dest_name:
                                dest_col = i
                                break
                        if dest_col is not None and len(row) > dest_col:
                            try:
                                qty = int(float(row[dest_col]))
                                cur.execute(
                                    "UPDATE shipment_items SET total_qty = %s "
                                    "WHERE shipment_id = %s AND barcode = %s",
                                    (qty, dest_id, barcode),
                                )
                                if cur.rowcount > 0:
                                    updated += 1
                            except (ValueError, TypeError):
                                continue

        return {"group_id": group_id, "updated_items": updated}
