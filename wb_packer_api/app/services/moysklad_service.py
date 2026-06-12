# app/services/moysklad_service.py
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class MoyskladService:
    """Service for Moysklad API integration"""

    BASE_URL = "https://api.moysklad.ru/api/remap/1.2"

    def __init__(self, token: str = ""):
        self.token = token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip",
        }

    def sync_stocks(self, shipment_id: Optional[int] = None) -> dict:
        """Sync stock quantities from Moysklad into stock_cache table"""
        if not self.token:
            return {"error": "No Moysklad token configured"}

        try:
            url = f"{self.BASE_URL}/entity/assortment"
            params = {"stockMode": "all", "limit": 1000}

            all_stocks = {}
            while url:
                resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("rows", []):
                    barcodes = []
                    for b in item.get("barcodes", []):
                        barcodes.append(b.get("value", ""))
                        for extra in b.get("additional", []):
                            barcodes.append(extra.get("value", ""))

                    stock = item.get("quantity", 0)
                    for bc in barcodes:
                        if bc:
                            all_stocks[bc] = stock

                url = None
                meta = data.get("meta", {})
                if meta.get("nextHref"):
                    url = meta["nextHref"]
                    params = {}

            # Save to stock_cache
            from ..database import get_connection

            with get_connection() as conn:
                with conn.cursor() as cur:
                    for barcode, stock in all_stocks.items():
                        cur.execute(
                            "INSERT INTO stock_cache (barcode, quantity) VALUES (%s, %s) "
                            "ON CONFLICT (barcode) DO UPDATE SET quantity = EXCLUDED.quantity, "
                            "updated_at = CURRENT_TIMESTAMP",
                            (barcode, stock),
                        )

            logger.info(f"Moysklad sync completed: {len(all_stocks)} items updated")
            return {"updated": len(all_stocks)}

        except requests.RequestException as e:
            logger.error(f"Moysklad API error: {e}")
            return {"error": str(e), "updated": 0}
