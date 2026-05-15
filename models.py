# models.py
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)


class ShipmentProperties:
    def __init__(self, marketplace: str = "", destination_warehouse: str = "",
                 shipment_date: str = "", shipment_number: str = "",
                 shipment_id: str = "", legal_entity: str = "", box_ids: str = ""):
        self.marketplace = marketplace
        self.destination_warehouse = destination_warehouse
        self.shipment_date = shipment_date
        self.shipment_number = shipment_number
        self.shipment_id = shipment_id
        self.legal_entity = legal_entity
        self.box_ids = box_ids

    def to_dict(self) -> Dict[str, str]:
        return {
            "marketplace": self.marketplace,
            "destination_warehouse": self.destination_warehouse,
            "shipment_date": self.shipment_date,
            "shipment_number": self.shipment_number,
            "shipment_id": self.shipment_id,
            "legal_entity": self.legal_entity,
            "box_ids": self.box_ids
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShipmentProperties':
        return cls(
            marketplace=data.get("marketplace", ""),
            destination_warehouse=data.get("destination_warehouse", ""),
            shipment_date=data.get("shipment_date", ""),
            shipment_number=data.get("shipment_number", ""),
            shipment_id=data.get("shipment_id", ""),
            legal_entity=data.get("legal_entity", ""),
            box_ids=data.get("box_ids", "")
        )


class ShipmentItem:
    def __init__(self, barcode: Union[str, int], sku: str, total_qty: int, allocated_qty: int = 0):
        self.barcode = str(barcode).strip()
        self.sku = str(sku).strip()
        self.total_qty = int(total_qty)
        self.allocated_qty = int(allocated_qty)

    @property
    def remaining_qty(self) -> int:
        return self.total_qty - self.allocated_qty


class Box:
    def __init__(self, box_id: str, items: Optional[Dict[str, int]] = None):
        self.box_id = box_id
        self.items: Dict[str, int] = items or {}
        self._total_items_cache: Optional[int] = None

    def total_items_count(self) -> int:
        if self._total_items_cache is None:
            self._total_items_cache = sum(self.items.values())
        return self._total_items_cache

    def add_item(self, barcode: str, qty: int = 1) -> None:
        self.items[barcode] = self.items.get(barcode, 0) + qty
        self._total_items_cache = None

    def set_item_qty(self, barcode: str, qty: int) -> None:
        if qty <= 0:
            self.items.pop(barcode, None)
        else:
            self.items[barcode] = qty
        self._total_items_cache = None

    def remove_item(self, barcode: str) -> None:
        self.items.pop(barcode, None)
        self._total_items_cache = None

    def invalidate_cache(self) -> None:
        """Сбросить кэш при изменении содержимого коробки"""
        self._total_items_cache = None

class Shipment:
    def __init__(self, destination_name: str, font_size: int, label_font_size: int, theme: str):
        self.destination_name = destination_name
        self.font_size = font_size
        self.label_font_size = label_font_size
        self.theme = theme
        self.shipment_items: Dict[str, 'ShipmentItem'] = {}
        self.boxes: List['Box'] = []
        self.current_box_index = -1
        self.removed_items: Dict[str, Dict[str, Any]] = {}
        self.parent_group: Optional['GroupShipment'] = None
        self.current_user: Optional[str] = None
        self.last_activity: Optional[datetime] = None
        self.is_expanded = False
        self.properties = ShipmentProperties()

        # Кэши для оптимизации производительности
        self._completion_status_cache: Optional[bool] = None
        self._discrepancies_status_cache: Optional[bool] = None
        self._progress_info_cache: Optional[tuple] = None
        self._status_icon_cache: Optional[str] = None

        # Новые поля для архива
        self.archived = False
        self.archived_date: Optional[datetime] = None
        self.archived_by: Optional[str] = None

        # Поле для отслеживания товаров с частичным уменьшением
        self.partial_decrease_items: set = set()

        # Активные пользователи
        self.active_users: set = set()

        # Поле для скрытия полностью собранных строк
        self.hide_completed_items = False

    def get_next_box_number(self) -> int:
        max_num = 0
        for box in self.boxes:
            box_id = box.box_id
            if box_id.startswith("Коробка-"):
                try:
                    number_part = box_id.split("-")[1]
                    num = int(''.join(filter(str.isdigit, number_part)))
                    if num > max_num:
                        max_num = num
                except (IndexError, ValueError):
                    continue
            elif box_id.startswith("Коробка "):
                try:
                    number_part = box_id.split(" ", 1)[1]
                    num = int(''.join(filter(str.isdigit, number_part)))
                    if num > max_num:
                        max_num = num
                except (IndexError, ValueError):
                    continue
        
        # Также проверяем БД для предотвращения дублирования номеров при многопользовательской работе
        try:
            shipment_id = getattr(self, 'shipment_id', None)
            if shipment_id is not None:
                from database import execute_query
                from db_connection import get_db_type
                db_type = get_db_type()
                placeholder = "?" if db_type == "sqlite" else "%s"
                result = execute_query(
                    f"SELECT box_id FROM boxes WHERE shipment_id = {placeholder}",
                    (shipment_id,),
                    fetchall=True
                )
                if result:
                    for row in result:
                        db_box_id = row[0]
                        if db_box_id and isinstance(db_box_id, str):
                            if db_box_id.startswith("Коробка-"):
                                try:
                                    num = int(''.join(filter(str.isdigit, db_box_id.split("-")[1])))
                                    if num > max_num:
                                        max_num = num
                                except (IndexError, ValueError):
                                    continue
                            elif db_box_id.startswith("Коробка "):
                                try:
                                    num = int(''.join(filter(str.isdigit, db_box_id.split(" ", 1)[1])))
                                    if num > max_num:
                                        max_num = num
                                except (IndexError, ValueError):
                                    continue
        except Exception:
            pass  # Если БД недоступна, используем локальный результат
        
        return max_num + 1

    def update_table_rows_visibility(self) -> bool:
        """Обновляет видимость строк в таблице поставки в зависимости от настройки скрытия полностью собранных строк"""
        if not hasattr(self, 'hide_completed_items'):
            self.hide_completed_items = False
        return self.hide_completed_items
        
    def invalidate_caches(self) -> None:
        """Сбросить все кэши при изменении состояния поставки"""
        self._completion_status_cache = None
        self._discrepancies_status_cache = None
        self._progress_info_cache = None
        self._status_icon_cache = None

    def recalculate_allocated_qty_from_boxes(self) -> None:
        """Пересчитать allocated_qty для всех товаров на основе содержимого коробок"""
        for item in self.shipment_items.values():
            item.allocated_qty = 0

        for box in self.boxes:
            for barcode, qty in box.items.items():
                if barcode in self.shipment_items:
                    self.shipment_items[barcode].allocated_qty += qty

        self.invalidate_caches()

    def is_completed(self) -> bool:
        if self._completion_status_cache is not None:
            return self._completion_status_cache

        if not self.shipment_items:
            self._completion_status_cache = False
            return False

        for item in self.shipment_items.values():
            if item.remaining_qty > 0:
                self._completion_status_cache = False
                return False

        self._completion_status_cache = True
        return True

    def has_discrepancies(self) -> bool:
        if self._discrepancies_status_cache is not None:
            return self._discrepancies_status_cache

        for item in self.shipment_items.values():
            if item.allocated_qty > item.total_qty:
                self._discrepancies_status_cache = True
                return True

        result = len(self.removed_items) > 0
        self._discrepancies_status_cache = result
        return result

    def get_status_icon(self) -> str:
        if self._status_icon_cache is not None:
            return self._status_icon_cache

        from app_constants import STATUS_ICONS, ShipmentStatus

        if self.is_completed() and not self.has_discrepancies():
            icon = STATUS_ICONS[ShipmentStatus.COMPLETED]
        elif self.has_discrepancies():
            icon = STATUS_ICONS[ShipmentStatus.HAS_DISCREPANCIES]
        else:
            icon = STATUS_ICONS[ShipmentStatus.IN_PROGRESS]

        self._status_icon_cache = icon
        return icon

    def get_progress_info(self) -> tuple:
        if self._progress_info_cache is not None:
            return self._progress_info_cache

        total_items = 0
        allocated_items = 0

        for item in self.shipment_items.values():
            total_items += item.total_qty
            allocated_items += item.allocated_qty

        # removed_items: товары удалены из поставки, их allocated уже не считается
        # в прогрессе — мы вычитаем их total_qty из общего и allocated из собранного
        for barcode, item_data in self.removed_items.items():
            # Вычитаем allocated удалённых товаров из собранного
            # (они были циклично перенесены из shipment_items в removed_items)
            allocated_items -= item_data.get('allocated_qty', 0)

        result = (max(0, allocated_items), total_items)
        self._progress_info_cache = result
        return result
        
    def add_shipment_item(self, barcode: str, sku: str, total_qty: int) -> None:
        item = ShipmentItem(barcode, sku, total_qty)
        self.shipment_items[barcode] = item
        self.invalidate_caches()

    def remove_shipment_item(self, barcode: str) -> None:
        if barcode in self.shipment_items:
            del self.shipment_items[barcode]
            self.invalidate_caches()

    def update_item_allocation(self, barcode: str, new_allocation: int) -> None:
        if barcode in self.shipment_items:
            self.shipment_items[barcode].allocated_qty = new_allocation
            self.invalidate_caches()

    def add_to_removed_items(self, barcode: str, sku: str, allocated_qty: int) -> None:
        self.removed_items[barcode] = {
            'sku': sku,
            'allocated_qty': allocated_qty
        }
        self.invalidate_caches()

    def remove_from_removed_items(self, barcode: str) -> None:
        if barcode in self.removed_items:
            del self.removed_items[barcode]
            self.invalidate_caches()

    def set_current_user(self) -> None:
        self.last_activity = datetime.now()

    def archive(self, user_icon: str) -> None:
        self.archived = True
        self.archived_date = datetime.now()
        self.archived_by = user_icon

    def unarchive(self) -> None:
        self.archived = False
        self.archived_date = None
        self.archived_by = None

class GroupShipment:
    def __init__(self, group_name: str, font_size: int, label_font_size: int, theme: str):
        self.group_name = group_name
        self.font_size = font_size
        self.label_font_size = label_font_size
        self.theme = theme
        self.sub_shipments: Dict[str, 'Shipment'] = {}
        self.is_expanded = True

        # Кэши для оптимизации производительности
        self._status_icon_cache: Optional[str] = None
        self._progress_info_cache: Optional[tuple] = None
        self._completion_status_cache: Optional[bool] = None
        self._discrepancies_status_cache: Optional[bool] = None

        # Новые поля для архивации
        self.archived = False
        self.archived_date: Optional[datetime] = None
        self.archived_by: Optional[str] = None

    def invalidate_caches(self) -> None:
        self._status_icon_cache = None
        self._progress_info_cache = None
        self._completion_status_cache = None
        self._discrepancies_status_cache = None

    def get_status_icon(self) -> str:
        if self._status_icon_cache is not None:
            return self._status_icon_cache

        all_completed = True
        has_discrepancies = False

        for shipment in self.sub_shipments.values():
            if not shipment.is_completed():
                all_completed = False
            if shipment.has_discrepancies():
                has_discrepancies = True

        from app_constants import STATUS_ICONS, ShipmentStatus

        if all_completed and not has_discrepancies:
            icon = STATUS_ICONS[ShipmentStatus.COMPLETED]
        elif has_discrepancies:
            icon = STATUS_ICONS[ShipmentStatus.HAS_DISCREPANCIES]
        else:
            icon = STATUS_ICONS[ShipmentStatus.IN_PROGRESS]

        self._status_icon_cache = icon
        return icon

    def get_progress_info(self) -> tuple:
        if self._progress_info_cache is not None:
            return self._progress_info_cache

        total_items = 0
        allocated_items = 0

        for shipment in self.sub_shipments.values():
            for item in shipment.shipment_items.values():
                total_items += item.total_qty
                allocated_items += item.allocated_qty

            for item_data in shipment.removed_items.values():
                allocated_items += item_data['allocated_qty']

        result = allocated_items, total_items
        self._progress_info_cache = result
        logger.debug(f"GroupShipment {self.group_name} progress: allocated={allocated_items}, total={total_items}, sub_shipments={len(self.sub_shipments)}")
        return result

    def is_completed(self) -> bool:
        if self._completion_status_cache is not None:
            return self._completion_status_cache

        for shipment in self.sub_shipments.values():
            if not shipment.is_completed():
                self._completion_status_cache = False
                return False

        self._completion_status_cache = True
        return True

    def has_discrepancies(self) -> bool:
        if self._discrepancies_status_cache is not None:
            return self._discrepancies_status_cache

        for shipment in self.sub_shipments.values():
            if shipment.has_discrepancies():
                self._discrepancies_status_cache = True
                return True

        self._discrepancies_status_cache = False
        return False

    def add_sub_shipment(self, destination_name: str, shipment: 'Shipment') -> None:
        shipment.parent_group = self
        if hasattr(shipment, 'original_destination_name'):
            self.sub_shipments[shipment.original_destination_name] = shipment
        else:
            self.sub_shipments[destination_name] = shipment
        self.invalidate_caches()

    def remove_sub_shipment(self, destination_name: str) -> None:
        shipment_to_remove = None
        has_original_names = any(hasattr(shipment, 'original_destination_name') for shipment in self.sub_shipments.values())

        if has_original_names:
            for key, shipment in self.sub_shipments.items():
                if (hasattr(shipment, 'original_destination_name') and
                    shipment.original_destination_name == destination_name):
                    shipment_to_remove = key
                    break
        else:
            if destination_name in self.sub_shipments:
                shipment_to_remove = destination_name

        if shipment_to_remove and shipment_to_remove in self.sub_shipments:
            del self.sub_shipments[shipment_to_remove]
        self.invalidate_caches()

    def archive(self, user_icon: str) -> None:
        self.archived = True
        self.archived_date = datetime.now()
        self.archived_by = user_icon
        for shipment in self.sub_shipments.values():
            shipment.archive(user_icon)

    def unarchive(self) -> None:
        self.archived = False
        self.archived_date = None
        self.archived_by = None
        for shipment in self.sub_shipments.values():
            shipment.unarchive()