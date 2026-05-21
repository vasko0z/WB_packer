"""
Модуль для управления операциями с базой данных в приложении WB Packer
"""
import logging
from typing import TYPE_CHECKING, List, Dict, Any, Optional
import config
from db_connection import get_db_type

if TYPE_CHECKING:
    from main_window import MainWindow

logger = logging.getLogger(__name__)

class DataController:
    """
    Контроллер для управления операциями с базой данных
    """
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        logger.info("Инициализация DataController")

    def load_shipments(self) -> Dict[str, Any]:
        """
        Загрузка поставок из базы данных
        """
        try:
            from database import execute_query
            from db_connection import get_db_type

            logger.info("Начало загрузки поставок из базы данных")

            # Определяем тип БД и используем правильный плейсхолдер
            # Используем get_db_type() вместо config.DATABASE_TYPE для учёта fallback
            db_type = get_db_type()
            placeholder = "?" if db_type == "sqlite" else "%s"
            archived_value = 0 if db_type == "sqlite" else False
            
            shipments_data = execute_query(
                f"""
                SELECT id, destination_name, font_size, label_font_size, theme, removed_items, parent_group, properties,
                       archived, archived_date, archived_by
                FROM shipments
                WHERE archived = {placeholder} AND id IS NOT NULL
                ORDER BY destination_name
                """,
                (archived_value,),
                fetchall=True
            )

            logger.info(f"Загружено {len(shipments_data)} поставок из базы данных")

            shipments = {}
            group_shipments = {}

            for row in shipments_data:
                # execute_query теперь всегда возвращает кортежи
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

                # Проверка типа shipment_id_value - пропускаем записи с None ID (групповые поставки без ID)
                if shipment_id_value is None:
                    logger.debug(f"Пропущена запись с None ID: {destination_name}")
                    continue
                    
                if not isinstance(shipment_id_value, int):
                    try:
                        shipment_id_value = int(shipment_id_value)
                    except (ValueError, TypeError):
                        logger.error(f"Ошибка: невозможно преобразовать в число ID: {shipment_id_value}, строка: {row}")
                        continue

                shipment = self.create_shipment_from_data(
                    destination_name, font_size, label_font_size, theme,
                    archived, archived_date, archived_by, removed_items_json,
                    properties_json, shipment_id_value
                )
                
                # Сохраняем ID поставки
                shipment.shipment_id = shipment_id_value

                # Восстанавливаем display_name для поставок в группе
                if parent_group and '::' in destination_name:
                    # Извлекаем название направления из уникального имени
                    display_name = destination_name.split('::', 1)[1]
                    shipment.display_name = display_name
                elif parent_group:
                    # Если есть parent_group, но нет ::, используем destination_name как display_name
                    shipment.display_name = destination_name

                if parent_group:
                    if parent_group not in group_shipments:
                        from models import GroupShipment
                        group_shipments[parent_group] = GroupShipment(
                            parent_group, font_size, label_font_size, theme
                        )
                    group_shipments[parent_group].add_sub_shipment(destination_name, shipment)
                else:
                    shipments[destination_name] = shipment

            # Оптимизация: batch загрузка всех товаров и коробок одним запросом
            self._batch_load_shipment_items(shipments, group_shipments)
            self._batch_load_boxes(shipments, group_shipments)

            # Сбрасываем кэши после загрузки данных
            for shipment in shipments.values():
                shipment.invalidate_caches()
            for group in group_shipments.values():
                for sub in group.sub_shipments.values():
                    sub.invalidate_caches()

            logger.info(f"Загрузка завершена: {len(shipments)} обычных поставок, {len(group_shipments)} групповых поставок")

            return {
                'shipments': shipments,
                'group_shipments': group_shipments
            }
        except Exception as e:
            logger.error(f"Ошибка при загрузке поставок из базы данных: {e}", exc_info=True)
            return {'shipments': {}, 'group_shipments': {}}

    def _get_all_shipments(self, shipments, group_shipments):
        """Возвращает dict всех поставок (обычных + подпоставки групп)"""
        all_shipments = dict(shipments)
        for group in group_shipments.values():
            all_shipments.update(group.sub_shipments)
        return all_shipments

    def _batch_load_shipment_items(self, shipments, group_shipments):
        """Batch загрузка всех товаров поставок одним запросом"""
        all_shipments = self._get_all_shipments(shipments, group_shipments)
        shipment_ids = [s.shipment_id for s in all_shipments.values() if hasattr(s, 'shipment_id') and s.shipment_id]
        
        if not shipment_ids:
            return
        
        db_type = get_db_type()
        placeholder = "?" if db_type == "sqlite" else "%s"
        placeholders = ", ".join([placeholder] * len(shipment_ids))
        
        from database import execute_query
        from models import ShipmentItem
        
        items_data = execute_query(
            f"SELECT shipment_id, barcode, sku, total_qty, allocated_qty FROM shipment_items WHERE shipment_id IN ({placeholders})",
            tuple(shipment_ids),
            fetchall=True
        )
        
        # Создаём мапу shipment_id -> shipment
        id_to_shipment = {}
        for s in all_shipments.values():
            if hasattr(s, 'shipment_id'):
                id_to_shipment[s.shipment_id] = s
        
        for row in items_data:
            sid, barcode, sku, total_qty, allocated_qty = row
            if sid in id_to_shipment:
                id_to_shipment[sid].shipment_items[barcode] = ShipmentItem(barcode, sku, total_qty, allocated_qty)

    def _batch_load_boxes(self, shipments, group_shipments):
        """Batch загрузка всех коробок и их содержимого двумя запросами"""
        all_shipments = self._get_all_shipments(shipments, group_shipments)
        shipment_ids = [s.shipment_id for s in all_shipments.values() if hasattr(s, 'shipment_id') and s.shipment_id]
        
        if not shipment_ids:
            return
        
        db_type = get_db_type()
        placeholder = "?" if db_type == "sqlite" else "%s"
        placeholders = ", ".join([placeholder] * len(shipment_ids))
        
        from database import execute_query
        from models import Box
        
        # Загружаем все коробки
        boxes_data = execute_query(
            f"SELECT id, shipment_id, box_id, is_current FROM boxes WHERE shipment_id IN ({placeholders}) ORDER BY box_id",
            tuple(shipment_ids),
            fetchall=True
        )
        
        id_to_shipment = {}
        for s in all_shipments.values():
            if hasattr(s, 'shipment_id'):
                id_to_shipment[s.shipment_id] = s
        
        # Создаём коробки
        box_id_to_db_id = {}
        for row in boxes_data:
            box_db_id, sid, box_id, is_current = row
            if sid in id_to_shipment:
                box = Box(box_id)
                id_to_shipment[sid].boxes.append(box)
                if is_current:
                    id_to_shipment[sid].current_box_index = len(id_to_shipment[sid].boxes) - 1
                box_id_to_db_id[box_db_id] = (sid, box)
        
        # Загружаем содержимое всех коробок
        if box_id_to_db_id:
            box_db_ids = list(box_id_to_db_id.keys())
            box_placeholders = ", ".join([placeholder] * len(box_db_ids))
            
            box_items_data = execute_query(
                f"SELECT box_id, barcode, qty FROM box_items WHERE box_id IN ({box_placeholders})",
                tuple(box_db_ids),
                fetchall=True
            )
            
            for row in box_items_data:
                box_db_id, barcode, qty = row
                if box_db_id in box_id_to_db_id:
                    _, box = box_id_to_db_id[box_db_id]
                    box.items[barcode] = qty

    def create_shipment_from_data(self, destination_name, font_size, label_font_size, theme,
                                  archived, archived_date, archived_by, removed_items_json,
                                  properties_json, shipment_id_value):
        """
        Создание объекта поставки из данных базы данных
        """
        from models import Shipment, ShipmentProperties
        
        shipment = Shipment(destination_name, font_size, label_font_size, theme)
        
        # Устанавливаем поля архива
        shipment.archived = bool(archived)
        if archived_date:
            from datetime import datetime
            try:
                shipment.archived_date = datetime.fromisoformat(archived_date)
            except ValueError:
                logger.warning(f"Неверный формат даты архивации для поставки {destination_name}: {archived_date}")
                shipment.archived_date = None
        shipment.archived_by = archived_by
        
        if removed_items_json:
            import json
            try:
                shipment.removed_items = json.loads(removed_items_json)
            except json.JSONDecodeError:
                logger.warning(f"Ошибка декодирования JSON для удаленных товаров поставки {destination_name}")
                shipment.removed_items = {}
        
        # Загружаем свойства поставки
        if properties_json:
            try:
                properties_data = json.loads(properties_json)
                shipment.properties = ShipmentProperties.from_dict(properties_data)
            except json.JSONDecodeError:
                logger.warning(f"Ошибка декодирования JSON для свойств поставки {destination_name}")
                shipment.properties = ShipmentProperties()
        
        return shipment

    def load_shipment_items(self, shipment_id_value: int) -> Dict[str, Any]:
        """
        Загрузка товаров поставки
        """
        from database import execute_query
        from models import ShipmentItem

        # Определяем тип БД и используем правильный плейсхолдер
        db_type = get_db_type()
        placeholder = "?" if db_type == "sqlite" else "%s"

        items_data = execute_query(
            f"""
            SELECT barcode, sku, total_qty, allocated_qty
            FROM shipment_items
            WHERE shipment_id = {placeholder}
            """,
            (shipment_id_value,),
            fetchall=True
        )

        shipment_items_dict = {}
        for barcode, sku, total_qty, allocated_qty in items_data:
            shipment_items_dict[barcode] = ShipmentItem(barcode, sku, total_qty, allocated_qty)
        return shipment_items_dict

    def load_boxes_data(self, shipment_id_value: int) -> List[tuple]:
        """
        Загрузка данных коробок
        """
        from database import execute_query

        # Определяем тип БД и используем правильный плейсхолдер
        db_type = get_db_type()
        placeholder = "?" if db_type == "sqlite" else "%s"

        logger.debug(f"Загрузка коробок для shipment_id={shipment_id_value}")

        result = execute_query(
            f"""
            SELECT id, box_id, is_current
            FROM boxes
            WHERE shipment_id = {placeholder}
            ORDER BY box_id
            """,
            (shipment_id_value,),
            fetchall=True
        )
        
        logger.debug(f"Найдено коробок в БД: {len(result)}")
        for r in result:
            logger.debug(f"  БД: id={r[0]}, box_id={r[1]!r}, is_current={r[2]}")

        return result

    def load_boxes_and_items(self, shipment, boxes_data: List[tuple]):
        """
        Загрузка коробок и товаров в них
        """
        from database import execute_query
        from models import Box

        # Определяем тип БД и используем правильный плейсхолдер
        db_type = get_db_type()
        placeholder = "?" if db_type == "sqlite" else "%s"

        current_box_index = -1
        logger.debug(f"Загрузка коробок: {len(boxes_data)} коробок найдено")

        for i, (box_db_id, box_id, is_current) in enumerate(boxes_data):
            # Декодируем box_id если это bytes
            if isinstance(box_id, bytes):
                box_id = box_id.decode('utf-8')
            elif isinstance(box_id, str):
                box_id = box_id
            
            logger.debug(f"Коробка {i}: box_db_id={box_db_id}, box_id={box_id}, is_current={is_current}")

            box = Box(box_id)

            # Загружаем товары в коробке
            box_items = execute_query(
                f"""
                SELECT barcode, qty
                FROM box_items
                WHERE box_id = {placeholder}
                """,
                (box_db_id,),
                fetchall=True
            )

            logger.debug(f"Коробка {box_id}: загружено {len(box_items)} товаров")
            
            # Оптимизированная загрузка товаров в коробке
            box_items_dict = {}
            for barcode, qty in box_items:
                # Декодируем barcode если это bytes
                if isinstance(barcode, bytes):
                    barcode = barcode.decode('utf-8')
                box_items_dict[barcode] = qty
            box.items = box_items_dict

            shipment.boxes.append(box)
            if is_current:
                current_box_index = i
        shipment.current_box_index = current_box_index
        logger.debug(f"Всего коробок в поставке: {len(shipment.boxes)}, current_box_index={shipment.current_box_index}")

    def save_shipment(self, shipment, preserve_box_items=False) -> bool:
        """
        Сохранение поставки в базу данных.
        Использует UPSERT-паттерн для предотвращения конфликтов при многопользовательской работе.
        preserve_box_items: если True, то сохраняет содержимое коробок без удаления
        """
        try:
            import json
            from database import execute_query
            from db_connection import get_db_type, execute_transaction, get_connection

            removed_items_json = json.dumps(shipment.removed_items, ensure_ascii=False)
            parent_group = shipment.parent_group.group_name if shipment.parent_group else None
            properties_json = json.dumps(shipment.properties.to_dict(), ensure_ascii=False)

            archived_date = shipment.archived_date.isoformat() if shipment.archived_date else None

            db_type = get_db_type()
            use_sqlite = db_type == "sqlite"
            placeholder = "?" if use_sqlite else "%s"

            # 1. UPSERT данных поставки (не трогаем поля других пользователей)
            if use_sqlite:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO shipments (
                        destination_name, font_size, label_font_size, theme,
                        removed_items, parent_group, properties,
                        archived, archived_date, archived_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    shipment.destination_name,
                    shipment.font_size,
                    shipment.label_font_size,
                    shipment.theme,
                    removed_items_json,
                    parent_group if parent_group else None,
                    properties_json,
                    1 if shipment.archived else 0,
                    archived_date if archived_date else None,
                    shipment.archived_by if shipment.archived_by else None
                ))
                conn.commit()
                result = execute_query(
                    "SELECT id FROM shipments WHERE destination_name = ?",
                    (shipment.destination_name,),
                    fetchone=True
                )
                shipment_id = result[0] if result else None
            else:
                result = execute_query(
                    f"""
                    INSERT INTO shipments (destination_name, font_size, label_font_size, theme, removed_items, parent_group, properties, archived, archived_date, archived_by)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                    ON CONFLICT (destination_name) DO UPDATE SET
                        font_size = EXCLUDED.font_size,
                        label_font_size = EXCLUDED.label_font_size,
                        theme = EXCLUDED.theme,
                        removed_items = EXCLUDED.removed_items,
                        parent_group = EXCLUDED.parent_group,
                        properties = EXCLUDED.properties,
                        archived = EXCLUDED.archived,
                        archived_date = EXCLUDED.archived_date,
                        archived_by = EXCLUDED.archived_by
                    RETURNING id
                    """,
                    (shipment.destination_name, shipment.font_size, shipment.label_font_size,
                     shipment.theme, removed_items_json,
                     parent_group if parent_group else None, properties_json,
                     shipment.archived, archived_date if archived_date else None,
                     shipment.archived_by if shipment.archived_by else None),
                    fetchone=True
                )
                shipment_id = result[0] if result else None

            if shipment_id is None:
                logger.error(f"Ошибка: shipment_id равен None для поставки {shipment.destination_name}")
                return False

            # 2. UPSERT элементов поставки (НЕ перезаписываем allocated_qty — она управляется атомарно)
            all_queries = []

            current_barcodes = set(shipment.shipment_items.keys())
            for item in shipment.shipment_items.values():
                if use_sqlite:
                    # SQLite: используем INSERT OR REPLACE, но обновляем только sku и total_qty
                    # allocated_qty управляется атомарно через atomic_increment/decrement
                    all_queries.append((
                        f"""INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty)
                        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                        ON CONFLICT(shipment_id, barcode) DO UPDATE SET
                            sku = excluded.sku,
                            total_qty = excluded.total_qty""",
                        (shipment_id, item.barcode, item.sku, item.total_qty, item.allocated_qty)
                    ))
                else:
                    all_queries.append((
                        f"""INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty)
                        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                        ON CONFLICT (shipment_id, barcode) DO UPDATE SET
                            sku = EXCLUDED.sku,
                            total_qty = EXCLUDED.total_qty""",
                        (shipment_id, item.barcode, item.sku, item.total_qty, item.allocated_qty)
                    ))

            # Удаляем элементы поставки, которых больше нет в локальной модели
            # (только те, которые были явно удалены пользователем)
            if hasattr(shipment, 'removed_items') and shipment.removed_items:
                for barcode in shipment.removed_items:
                    all_queries.append((
                        f"DELETE FROM shipment_items WHERE shipment_id = {placeholder} AND barcode = {placeholder}",
                        (shipment_id, barcode)
                    ))

            # 3. UPSERT коробок (добавляем/обновляем, не трогаем чужие)
            current_box_ids = set()
            for i, box in enumerate(shipment.boxes):
                is_current = (i == shipment.current_box_index)
                box_id_str = box.box_id if isinstance(box.box_id, str) else str(box.box_id)
                current_box_ids.add(box_id_str)

                if use_sqlite:
                    is_current_int = 1 if is_current else 0
                    all_queries.append((
                        f"INSERT OR REPLACE INTO boxes (shipment_id, box_id, is_current) VALUES ({placeholder}, {placeholder}, {placeholder})",
                        (shipment_id, box_id_str, is_current_int)
                    ))
                else:
                    all_queries.append((
                        f"""INSERT INTO boxes (shipment_id, box_id, is_current)
                        VALUES ({placeholder}, {placeholder}, {placeholder})
                        ON CONFLICT (shipment_id, box_id) DO UPDATE SET is_current = EXCLUDED.is_current""",
                        (shipment_id, box_id_str, is_current)
                    ))

            # Удаляем коробки, которых нет в локальной модели
            # Сначала получаем все коробки из БД
            select_placeholder = "?" if use_sqlite else "%s"
            db_boxes = execute_query(
                f"SELECT box_id FROM boxes WHERE shipment_id = {select_placeholder}",
                (shipment_id,),
                fetchall=True
            )
            db_box_ids = set(row[0] for row in db_boxes) if db_boxes else set()
            
            # Удаляем коробки, которые есть в БД, но отсутствуют в локальной модели
            boxes_to_delete = db_box_ids - current_box_ids
            for box_id_to_delete in boxes_to_delete:
                all_queries.append((
                    f"DELETE FROM boxes WHERE shipment_id = {select_placeholder} AND box_id = {select_placeholder}",
                    (shipment_id, box_id_to_delete)
                ))

            # Сбрасываем is_current у всех коробок этой поставки, кроме текущей
            current_box_index = shipment.current_box_index
            if current_box_index >= 0 and current_box_index < len(shipment.boxes):
                all_queries.append((
                    f"UPDATE boxes SET is_current = {placeholder} WHERE shipment_id = {placeholder} AND box_id != {placeholder}",
                    (0 if use_sqlite else False, shipment_id, shipment.boxes[current_box_index].box_id if isinstance(shipment.boxes[current_box_index].box_id, str) else str(shipment.boxes[current_box_index].box_id))
                ))

            # Выполняем основные запросы в одной транзакции
            try:
                execute_transaction(all_queries)
            except Exception as e:
                logger.error(f"Ошибка при сохранении основных данных поставки: {e}", exc_info=True)
                return False

            # Обновляем version
            try:
                execute_query(
                    f"UPDATE shipments SET version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE id = {placeholder}",
                    (shipment_id,)
                )
            except Exception as e:
                logger.warning(f"Не удалось обновить version поставки: {e}")

            # 4. UPSERT содержимого коробок
            for i, box in enumerate(shipment.boxes):
                box_id_str = box.box_id if isinstance(box.box_id, str) else str(box.box_id)
                box_result = execute_query(
                    f"SELECT id FROM boxes WHERE shipment_id = {placeholder} AND box_id = {placeholder}",
                    (shipment_id, box_id_str),
                    fetchone=True
                )
                box_db_id = box_result[0] if box_result else None

                if not box_db_id:
                    logger.warning(f"Не найдена коробка {box_id_str} после сохранения, пропускаем")
                    continue

                box_queries = []
                # Удаляем только те товары коробки, которых нет в локальной модели
                current_item_barcodes = list(box.items.keys())
                if current_item_barcodes:
                    placeholders_list = ','.join([placeholder] * len(current_item_barcodes))
                    box_queries.append((
                        f"DELETE FROM box_items WHERE box_id = {placeholder} AND barcode NOT IN ({placeholders_list})",
                        (box_db_id, *current_item_barcodes)
                    ))
                else:
                    box_queries.append((
                        f"DELETE FROM box_items WHERE box_id = {placeholder}",
                        (box_db_id,)
                    ))

                for barcode, qty in box.items.items():
                    if use_sqlite:
                        box_queries.append((
                            f"INSERT OR REPLACE INTO box_items (box_id, barcode, qty) VALUES ({placeholder}, {placeholder}, {placeholder})",
                            (box_db_id, barcode, qty)
                        ))
                    else:
                        box_queries.append((
                            f"""INSERT INTO box_items (box_id, barcode, qty)
                            VALUES ({placeholder}, {placeholder}, {placeholder})
                            ON CONFLICT (box_id, barcode) DO UPDATE SET qty = EXCLUDED.qty""",
                            (box_db_id, barcode, qty)
                        ))

                if box_queries:
                    try:
                        execute_transaction(box_queries)
                    except Exception as e:
                        logger.error(f"Ошибка при сохранении товаров коробки {box_id_str}: {e}", exc_info=True)

            logger.info(f"Поставка успешно сохранена (upsERT): {shipment.destination_name}")
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения поставки: {e}", exc_info=True)
            return False

    def save_shipment_immediate(self, shipment, box_index: int = None) -> bool:
        """
        Немедленное сохранение поставки с оптимизацией для частых вызовов.
        Сохраняет только текущую коробку и основные данные поставки.
        
        Args:
            shipment: объект поставки для сохранения
            box_index: индекс коробки для сохранения (по умолчанию текущая)
        
        Returns:
            bool: True если сохранение успешно, False иначе
        """
        try:
            import json
            from database import execute_query
            from db_connection import get_db_type, execute_transaction

            if box_index is None:
                box_index = shipment.current_box_index

            if box_index < 0 or box_index >= len(shipment.boxes):
                logger.warning(f"Некорректный индекс коробки: {box_index}")
                return False

            current_box = shipment.boxes[box_index]
            logger.debug(f"Немедленное сохранение коробки {current_box.box_id} ({len(current_box.items)} товаров)")

            # Определяем тип БД
            db_type = get_db_type()
            use_sqlite = db_type == "sqlite"
            placeholder = "?" if use_sqlite else "%s"

            # 1. Сохраняем основные данные поставки (быстрое обновление)
            removed_items_json = json.dumps(shipment.removed_items, ensure_ascii=False)
            parent_group = shipment.parent_group.group_name if shipment.parent_group else None
            properties_json = json.dumps(shipment.properties.to_dict(), ensure_ascii=False)
            archived_date = shipment.archived_date.isoformat() if shipment.archived_date else None

            if use_sqlite:
                execute_query("""
                    INSERT OR REPLACE INTO shipments (
                        destination_name, font_size, label_font_size, theme,
                        removed_items, parent_group, properties,
                        archived, archived_date, archived_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    shipment.destination_name,
                    shipment.font_size,
                    shipment.label_font_size,
                    shipment.theme,
                    removed_items_json,
                    parent_group if parent_group else None,
                    properties_json,
                    1 if shipment.archived else 0,
                    archived_date if archived_date else None,
                    shipment.archived_by if shipment.archived_by else None
                ))

                # Получаем ID поставки
                result = execute_query(
                    "SELECT id FROM shipments WHERE destination_name = ?",
                    (shipment.destination_name,),
                    fetchone=True
                )
                shipment_id = result[0] if result else None
            else:
                result = execute_query("""
                    INSERT INTO shipments (destination_name, font_size, label_font_size, theme, removed_items, parent_group, properties, archived, archived_date, archived_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (destination_name) DO UPDATE SET
                        font_size = EXCLUDED.font_size,
                        label_font_size = EXCLUDED.label_font_size,
                        theme = EXCLUDED.theme,
                        removed_items = EXCLUDED.removed_items,
                        parent_group = EXCLUDED.parent_group,
                        properties = EXCLUDED.properties,
                        archived = EXCLUDED.archived,
                        archived_date = EXCLUDED.archived_date,
                        archived_by = EXCLUDED.archived_by
                    RETURNING id
                """, (
                    shipment.destination_name, shipment.font_size, shipment.label_font_size,
                    shipment.theme, removed_items_json,
                    parent_group if parent_group else None, properties_json,
                    shipment.archived, archived_date if archived_date else None,
                    shipment.archived_by if shipment.archived_by else None
                ), fetchone=True)
                shipment_id = result[0] if result else None

            if shipment_id is None:
                logger.error(f"Не удалось получить ID поставки {shipment.destination_name}")
                return False

            # 2. ОПТИМИЗАЦИЯ: Обновляем элементы поставки (shipment_items) пакетно через UPSERT
            queries_with_params = []

            if use_sqlite:
                # Для SQLite: не перезаписываем allocated_qty при конфликтe
                for item in shipment.shipment_items.values():
                    queries_with_params.append((
                        f"""
                        INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty)
                        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                        ON CONFLICT(shipment_id, barcode) DO UPDATE SET
                            sku = excluded.sku,
                            total_qty = excluded.total_qty
                        """,
                        (shipment_id, item.barcode, item.sku, item.total_qty, item.allocated_qty)
                    ))
            else:
                # Для PostgreSQL: allocated_qty НЕ перезаписываем — управляется атомарно
                for item in shipment.shipment_items.values():
                    queries_with_params.append((
                        f"""
                        INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty)
                        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                        ON CONFLICT (shipment_id, barcode) DO UPDATE SET
                            sku = EXCLUDED.sku,
                            total_qty = EXCLUDED.total_qty
                        """,
                        (shipment_id, item.barcode, item.sku, item.total_qty, item.allocated_qty)
                    ))

            # 3. Обновляем статус текущей коробки
            is_current = 1 if use_sqlite else True
            not_current = 0 if use_sqlite else False

            # Сбрасываем флаг is_current у всех коробок
            queries_with_params.append((
                f"UPDATE boxes SET is_current = {placeholder} WHERE shipment_id = {placeholder}",
                (not_current, shipment_id)
            ))

            # Получаем или создаем запись для текущей коробки
            box_id_str = current_box.box_id if isinstance(current_box.box_id, str) else str(current_box.box_id)

            if use_sqlite:
                # Для SQLite используем INSERT OR REPLACE
                queries_with_params.append((
                    f"""
                    INSERT OR REPLACE INTO boxes (shipment_id, box_id, is_current)
                    VALUES ({placeholder}, {placeholder}, {placeholder})
                    """,
                    (shipment_id, box_id_str, is_current)
                ))
            else:
                # Для PostgreSQL сначала проверяем существование, затем UPDATE или INSERT
                box_result = execute_query(
                    f"SELECT id FROM boxes WHERE shipment_id = {placeholder} AND box_id = {placeholder}",
                    (shipment_id, box_id_str),
                    fetchone=True
                )
                if box_result:
                    # Коробка существует - обновляем
                    queries_with_params.append((
                        f"UPDATE boxes SET is_current = {placeholder} WHERE shipment_id = {placeholder} AND box_id = {placeholder}",
                        (is_current, shipment_id, box_id_str)
                    ))
                else:
                    # Коробка не существует - вставляем
                    queries_with_params.append((
                        f"""
                        INSERT INTO boxes (shipment_id, box_id, is_current)
                        VALUES ({placeholder}, {placeholder}, {placeholder})
                        """,
                        (shipment_id, box_id_str, is_current)
                    ))

            # Выполняем обновление статуса коробок
            try:
                execute_transaction(queries_with_params)
            except Exception as e:
                logger.error(f"Ошибка при обновлении данных поставки: {e}", exc_info=True)
                return False

            # Обновляем version поставки после успешного сохранения
            try:
                if use_sqlite:
                    execute_query("""
                        UPDATE shipments SET version = version + 1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (shipment_id,))
                else:
                    execute_query("""
                        UPDATE shipments SET version = version + 1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (shipment_id,))
            except Exception as e:
                logger.warning(f"Не удалось обновить version поставки: {e}")

            # Создаём запись об инвалидации кэша для других клиентов
            try:
                from database import invalidate_cache_for_shipment
                invalidate_cache_for_shipment(
                    shipment_id,
                    ['shipments', 'shipment_items', 'boxes', 'box_items'],
                    getattr(self.main_window, 'current_user', 'unknown')
                )
            except Exception as e:
                logger.warning(f"Не удалось создать запись об инвалидации кэша: {e}")

            # 4. Получаем ID коробки
            box_result = execute_query(
                f"SELECT id FROM boxes WHERE shipment_id = {placeholder} AND box_id = {placeholder}",
                (shipment_id, box_id_str),
                fetchone=True
            )
            box_db_id = box_result[0] if box_result else None

            if not box_db_id:
                logger.error(f"Не удалось получить ID коробки {box_id_str}")
                return False

            # 5. ОПТИМИЗАЦИЯ: Сохраняем элементы коробки пакетно через UPSERT
            box_queries = []

            for barcode, qty in current_box.items.items():
                if use_sqlite:
                    box_queries.append((
                        f"""
                        INSERT OR REPLACE INTO box_items (box_id, barcode, qty)
                        VALUES ({placeholder}, {placeholder}, {placeholder})
                        """,
                        (box_db_id, barcode, qty)
                    ))
                else:
                    # Для PostgreSQL используем ON CONFLICT DO UPDATE (UPSERT) - БЕЗ отдельных SELECT!
                    box_queries.append((
                        f"""
                        INSERT INTO box_items (box_id, barcode, qty)
                        VALUES ({placeholder}, {placeholder}, {placeholder})
                        ON CONFLICT (box_id, barcode) DO UPDATE SET
                            qty = EXCLUDED.qty
                        """,
                        (box_db_id, barcode, qty)
                    ))

            # Выполняем сохранение элементов коробки
            if box_queries:
                try:
                    execute_transaction(box_queries)
                except Exception as e:
                    logger.error(f"Ошибка при сохранении товаров коробки {box_id_str}: {e}", exc_info=True)
                    return False

            logger.debug(f"Коробка {current_box.box_id} успешно сохранена ({len(current_box.items)} товаров)")
            return True

        except Exception as e:
            logger.error(f"Ошибка немедленного сохранения: {e}", exc_info=True)
            return False

    def archive_shipment(self, shipment_name: str, username: str) -> bool:
        """
        Архивировать поставку
        """
        try:
            from database import execute_query
            from datetime import datetime

            db_type = get_db_type()
            placeholder = "?" if db_type == "sqlite" else "%s"
            archived_value = 1 if db_type == "sqlite" else True
            archived_date = datetime.now().isoformat()
            
            execute_query(
                f"UPDATE shipments SET archived = {placeholder}, archived_date = {placeholder}, archived_by = {placeholder} WHERE destination_name = {placeholder}",
                (archived_value, archived_date, username, shipment_name)
            )
            logger.info(f"Поставка {shipment_name} архивирована пользователем {username}")
            return True
        except Exception as e:
            logger.error(f"Ошибка архивации поставки {shipment_name}: {e}", exc_info=True)
            return False

    def unarchive_shipment(self, shipment_name: str) -> bool:
        """
        Восстановить поставку из архива
        """
        try:
            from database import execute_query

            db_type = get_db_type()
            placeholder = "?" if db_type == "sqlite" else "%s"
            archived_value = 0 if db_type == "sqlite" else False
            
            execute_query(
                f"UPDATE shipments SET archived = {placeholder}, archived_date = NULL, archived_by = NULL WHERE destination_name = {placeholder}",
                (archived_value, shipment_name)
            )
            logger.info(f"Поставка {shipment_name} восстановлена из архива")
            return True
        except Exception as e:
            logger.error(f"Ошибка восстановления поставки {shipment_name}: {e}", exc_info=True)
            return False

    def delete_shipment(self, shipment_name: str) -> bool:
        """
        Удалить поставку
        """
        try:
            from database import execute_query

            db_type = get_db_type()
            placeholder = "?" if db_type == "sqlite" else "%s"
            
            execute_query(
                f"DELETE FROM shipments WHERE destination_name = {placeholder}",
                (shipment_name,)
            )
            logger.info(f"Поставка {shipment_name} удалена")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления поставки {shipment_name}: {e}", exc_info=True)
            return False

    def get_archived_shipments(self) -> List[tuple]:
        """
        Получить список архивированных поставок
        """
        try:
            from database import execute_query

            db_type = get_db_type()
            placeholder = "?" if db_type == "sqlite" else "%s"
            archived_value = 1 if db_type == "sqlite" else True

            result = execute_query(
                f"""
                SELECT destination_name, archived_date, archived_by
                FROM shipments
                WHERE archived = {placeholder}
                ORDER BY archived_date DESC
                """,
                (archived_value,),
                fetchall=True
            )
            return result
        except Exception as e:
            logger.error(f"Ошибка получения архивированных поставок: {e}", exc_info=True)
            return []

    def delete_archived_shipment(self, shipment_name: str) -> bool:
        """
        Удалить архивированную поставку
        """
        try:
            from database import get_connection

            db_type = get_db_type()
            placeholder = "?" if db_type == "sqlite" else "%s"
            
            conn = get_connection()
            cursor = conn.cursor()

            # Получаем ID поставки
            cursor.execute(
                f"SELECT id FROM shipments WHERE destination_name = {placeholder}",
                (shipment_name,)
            )
            result = cursor.fetchone()
            if not result:
                return False

            shipment_id = result[0]

            # Удаляем связанные записи
            cursor.execute(
                f"DELETE FROM box_items WHERE box_id IN (SELECT id FROM boxes WHERE shipment_id = {placeholder})",
                (shipment_id,)
            )
            cursor.execute(
                f"DELETE FROM boxes WHERE shipment_id = {placeholder}",
                (shipment_id,)
            )
            cursor.execute(
                f"DELETE FROM shipment_items WHERE shipment_id = {placeholder}",
                (shipment_id,)
            )
            cursor.execute(
                f"DELETE FROM shipments WHERE id = {placeholder}",
                (shipment_id,)
            )

            conn.commit()
            conn.close()
            logger.info(f"Архивированная поставка {shipment_name} удалена")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления архивированной поставки {shipment_name}: {e}", exc_info=True)
            return False