"""
Модуль для получения данных о поставках из базы данных
"""
import json
from datetime import datetime
import database
from models import Shipment, GroupShipment, ShipmentProperties


class ShipmentDataFetcher:
    """
    Класс для получения данных о поставках из базы данных
    """
    
    def get_current_shipments(self):
        """
        Получает список текущих (не архивных) поставок с информацией о прогрессе
        """
        try:
            # Загружаем только неархивированные поставки
            shipments_data = database.execute_query(
                """
                SELECT id, destination_name, font_size, label_font_size, theme, removed_items, parent_group, properties,
                       archived, archived_date, archived_by
                FROM shipments
                WHERE archived = %s
                ORDER BY destination_name
                """,
                (False,),
                fetchall=True
            )
            
            shipments = {}
            group_shipments = {}
            
            for row in shipments_data:
                shipment_id_value = row[0]
                destination_name = row[1]
                font_size = row[2]
                label_font_size = row[3]
                theme = row[4]
                removed_items_json = row[5]
                parent_group = row[6]
                properties_json = row[7]
                archived = row[8]
                archived_date = row[9]
                archived_by = row[10]
                
                # Проверим тип shipment_id_value
                if not isinstance(shipment_id_value, int):
                    try:
                        shipment_id_value = int(shipment_id_value)
                    except (ValueError, TypeError):
                        continue
                
                shipment = Shipment(destination_name, font_size, label_font_size, theme)
                
                # Устанавливаем поля архива
                shipment.archived = bool(archived)
                if archived_date:
                    try:
                        shipment.archived_date = datetime.fromisoformat(archived_date)
                    except ValueError:
                        shipment.archived_date = None
                shipment.archived_by = archived_by
                
                if removed_items_json:
                    try:
                        shipment.removed_items = json.loads(removed_items_json)
                    except json.JSONDecodeError:
                        shipment.removed_items = {}
                
                # Загружаем свойства поставки
                if properties_json:
                    try:
                        properties_data = json.loads(properties_json)
                        shipment.properties = ShipmentProperties.from_dict(properties_data)
                    except json.JSONDecodeError:
                        shipment.properties = ShipmentProperties()
                
                # Загружаем товары поставки
                items_data = database.execute_query(
                    """
                    SELECT barcode, sku, total_qty, allocated_qty
                    FROM shipment_items
                    WHERE shipment_id = %s
                    """,
                    (shipment_id_value,),
                    fetchall=True
                )
                
                # Оптимизированная загрузка товаров
                shipment_items_dict = {}
                for barcode, sku, total_qty, allocated_qty in items_data:
                    from models import ShipmentItem
                    shipment_items_dict[barcode] = ShipmentItem(barcode, sku, total_qty, allocated_qty)
                shipment.shipment_items = shipment_items_dict
                
                # Загружаем коробки для поставки (аналогично как в shipment_manager.py)
                boxes_data = database.execute_query(
                    """
                    SELECT id, box_id, is_current
                    FROM boxes
                    WHERE shipment_id = %s
                    ORDER BY box_id
                    """,
                    (shipment_id_value,),
                    fetchall=True
                )
                
                current_box_index = -1
                # Загружаем все коробки для поставки
                for i, (box_db_id, box_id, is_current) in enumerate(boxes_data):
                    from models import Box
                    box = Box(box_id)
                    
                    # Загружаем товары в коробке
                    box_items = database.execute_query(
                        """
                        SELECT barcode, qty
                        FROM box_items
                        WHERE box_id = %s
                        """,
                        (box_db_id,),
                        fetchall=True
                    )
                    
                    # Оптимизированная загрузка товаров в коробке
                    box_items_dict = {}
                    for barcode, qty in box_items:
                        box_items_dict[barcode] = qty
                    box.items = box_items_dict
                    
                    shipment.boxes.append(box)
                    if is_current:
                        current_box_index = i
                shipment.current_box_index = current_box_index
                
                if parent_group:
                    if parent_group not in group_shipments:
                        group_shipments[parent_group] = GroupShipment(
                            parent_group, font_size, label_font_size, theme
                        )
                    group_shipments[parent_group].add_sub_shipment(destination_name, shipment)
                else:
                    shipments[destination_name] = shipment
            
            return {
                'shipments': shipments,
                'group_shipments': group_shipments
            }
        except Exception as e:
            print(f"Ошибка при получении данных о поставках: {e}")
            return {
                'shipments': {},
                'group_shipments': {}
            }
    
    def get_shipment_progress_info(self, shipment):
        """
        Возвращает информацию о прогрессе поставки (как в Shipment.get_progress_info())
        """
        return shipment.get_progress_info()
    
    def get_shipment_status_icon(self, shipment):
        """
        Возвращает иконку статуса поставки
        """
        return shipment.get_status_icon()
    
    def format_shipment_info(self, shipment):
        """
        Форматирует информацию о поставке для отображения
        """
        allocated, total = self.get_shipment_progress_info(shipment)
        status_icon = self.get_shipment_status_icon(shipment)
        
        return {
            'name': shipment.destination_name,
            'progress': f"{allocated}/{total}",
            'allocated': allocated,
            'total': total,
            'status_icon': status_icon,
            'completed': shipment.is_completed(),
            'has_discrepancies': shipment.has_discrepancies()
        }