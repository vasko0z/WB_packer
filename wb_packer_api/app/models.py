# app/models.py
from pydantic import BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime


# --- Shipment ---
class ShipmentCreate(BaseModel):
    destination_name: str
    font_size: int = 10
    label_font_size: int = 20
    theme: str = "Светлая"
    removed_items: Dict[str, Any] = {}
    parent_group: Optional[str] = None
    properties: Dict[str, Any] = {}
    archived: bool = False
    archived_by: Optional[str] = None
    wb_shipment_number: Optional[str] = None
    wb_metadata: Optional[Dict[str, Any]] = None


class ShipmentUpdate(BaseModel):
    destination_name: Optional[str] = None
    font_size: Optional[int] = None
    label_font_size: Optional[int] = None
    theme: Optional[str] = None
    removed_items: Optional[Dict[str, Any]] = None
    parent_group: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    wb_shipment_number: Optional[str] = None
    wb_metadata: Optional[Dict[str, Any]] = None


class ShipmentOut(BaseModel):
    id: int
    destination_name: str
    font_size: int
    label_font_size: int
    theme: str
    removed_items: Dict[str, Any] = {}
    parent_group: Optional[str] = None
    properties: Dict[str, Any] = {}
    archived: bool = False
    archived_date: Optional[str] = None
    archived_by: Optional[str] = None
    version: int = 0
    wb_shipment_number: Optional[str] = None
    wb_metadata: Optional[Dict[str, Any]] = None


# --- ShipmentItem ---
class ShipmentItemUpdate(BaseModel):
    sku: Optional[str] = None
    total_qty: Optional[int] = None
    allocated_qty: Optional[int] = None


class ShipmentItemOut(BaseModel):
    id: Optional[int] = None
    barcode: str
    sku: str = ""
    total_qty: int = 1
    allocated_qty: int = 0

    @property
    def remaining_qty(self) -> int:
        return self.total_qty - self.allocated_qty


class ShipmentItemCreate(BaseModel):
    barcode: str
    sku: str = ""
    total_qty: int = 1
    allocated_qty: int = 0


# --- Box ---
class BoxCreate(BaseModel):
    box_id: str
    is_current: bool = False


class BoxUpdate(BaseModel):
    box_id: Optional[str] = None
    is_current: Optional[bool] = None


class BoxOut(BaseModel):
    id: int
    box_id: str
    is_current: bool = False
    total_items: int = 0


class BoxItemCreate(BaseModel):
    barcode: str
    qty: int = 1


class BoxItemUpdate(BaseModel):
    qty: int = 1


class BoxItemOut(BaseModel):
    id: int
    barcode: str
    qty: int = 1


# --- SKU ---
class SKUCreate(BaseModel):
    barcode: str
    article: str = ""
    name: str = ""


class SKUOut(BaseModel):
    barcode: str
    article: str = ""
    name: str = ""


# --- Packer User ---
class PackerUserSettingsCreate(BaseModel):
    current_shipment: Optional[str] = None
    font_size: int = 10
    label_font_size: int = 20
    current_theme: str = "macOS"
    ok_sound: str = "ok.wav"
    error_sound: str = "error.wav"
    tone_sound: bool = False
    sound_volume: int = 100
    colored_buttons: bool = True
    show_sku: bool = True
    show_name: bool = False
    show_total: bool = True
    show_stock: bool = False
    hide_completed: bool = False
    shipment_columns_width: Optional[str] = None
    box_columns_width: Optional[str] = None
    main_splitter_sizes: Optional[str] = None
    window_width: int = 1300
    window_height: int = 800
    window_x: int = 0
    window_y: int = 0


class PackerUserOut(BaseModel):
    username: str
    current_shipment: Optional[str] = None
    font_size: int = 10


# --- App Settings ---
class AppSettingCreate(BaseModel):
    key: str
    value: str


class AppSettingOut(BaseModel):
    key: str
    value: str


# --- Session ---
class SessionUpdate(BaseModel):
    shipment_name: str
    username: str


# --- Google Sheets ---
class GsheetsImportRequest(BaseModel):
    spreadsheet_id: str
    sheet_name: str
    destination_name: Optional[str] = None
    is_group_shipment: bool = False
    font_size: int = 10
    label_font_size: int = 20


class GsheetsUpdateRequest(BaseModel):
    spreadsheet_id: str
    sheet_name: str
    group_id: int


# --- Moysklad ---
class MoyskladSettings(BaseModel):
    token: str = ""
    enabled: bool = False
    stores: List[Dict[str, Any]] = []


class MoyskladSyncRequest(BaseModel):
    shipment_id: Optional[int] = None


# --- Stock ---
class StockBatchRequest(BaseModel):
    barcodes: List[str]


class StockUpdate(BaseModel):
    quantity: int


# --- Retire Log ---
class RetireLogCreate(BaseModel):
    barcode: str
    qty: int = 1
    reason: str = ""
    retired_by: str = ""


class RetireLogOut(BaseModel):
    id: int
    shipment_id: int
    barcode: str
    qty: int
    reason: str = ""
    retired_by: str = ""
    retired_at: Optional[str] = None


# --- Admin ---
class ImportData(BaseModel):
    shipments: List[Dict[str, Any]] = []
    users: List[Dict[str, Any]] = []
    settings: List[Dict[str, Any]] = []
