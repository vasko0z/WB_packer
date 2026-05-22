# shipment_manager.py
import json
import pandas as pd
import logging
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QDialog, QMenu
from PyQt6.QtCore import Qt, QTimer
import database
import config
import utils
from db_connection import _release_connection
from models import Shipment, ShipmentItem, Box, GroupShipment, ShipmentProperties
from dialogs import DestinationDialog, RenameDialog, ShipmentPropertiesDialog, BoxNumberDialog
from app_constants import ColumnIndex, BoxColumnIndex

# Добавляем импорт для работы с Word
try:
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class ShipmentManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)
        self.logger.info("Инициализация ShipmentManager")
        # Timer for delayed saving to database
        self.save_timer = None
        # Flag to track if a save is pending
        self.save_pending = False
        # Extended delay for network operations using config value
        self.save_delay = config.NETWORK_OPERATION_DELAY  # Use delay from config for network operations
        # Local cache for shipments to minimize database queries
        self.shipment_cache = {}
        self.shipment_items_cache = {}
        self.boxes_cache = {}
        self.box_items_cache = {}
        # Защита от повторного сканирования (debouncing)
        self.is_scanning = False

    def save_shipment(self, shipment, preserve_box_items=False):
        try:
            self.logger.info(f"Начало сохранения поставки: {shipment.destination_name}")
            removed_items_json = json.dumps(shipment.removed_items, ensure_ascii=False)
            parent_group = shipment.parent_group.group_name if shipment.parent_group else None
            properties_json = json.dumps(shipment.properties.to_dict(), ensure_ascii=False)
            
            # Добавляем поля архива в запрос
            archived_date = shipment.archived_date.isoformat() if shipment.archived_date else None
            
            # Получаем соединение из пула
            conn = database.get_connection()
            try:
                cursor = conn.cursor()
                try:
                    # Определяем тип БД по фактическому соединению, а не по db_type,
                    # так как при fallback с PostgreSQL на SQLite db_type может остаться "postgresql"
                    from db_connection import is_sqlite_connection
                    use_sqlite = is_sqlite_connection(conn)
                    
                    # Плейсхолдеры и синтаксис в зависимости от типа БД
                    placeholder = "?" if use_sqlite else "%s"
                    on_conflict = "INSERT OR REPLACE INTO" if use_sqlite else """INSERT INTO shipments (...) VALUES (...) ON CONFLICT (destination_name) DO UPDATE SET"""

                    if use_sqlite:
                        # Для SQLite используем INSERT OR REPLACE
                        dest_name = shipment.destination_name.encode('utf-8').decode('utf-8')
                        self.logger.debug(f"INSERT OR REPLACE: dest_name={dest_name}, archived={1 if shipment.archived else 0}")
                        
                        cursor.execute(f"""
                            INSERT OR REPLACE INTO shipments (
                                destination_name, font_size, label_font_size, theme,
                                removed_items, parent_group, properties,
                                archived, archived_date, archived_by
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            dest_name,
                            shipment.font_size,
                            shipment.label_font_size,
                            shipment.theme.encode('utf-8').decode('utf-8'),
                            removed_items_json.encode('utf-8').decode('utf-8'),
                            parent_group.encode('utf-8').decode('utf-8') if parent_group else None,
                            properties_json.encode('utf-8').decode('utf-8'),
                            1 if shipment.archived else 0,
                            archived_date.encode('utf-8').decode('utf-8') if archived_date else None,
                            shipment.archived_by.encode('utf-8').decode('utf-8') if shipment.archived_by else None
                        ))
                        
                        self.logger.debug(f"INSERT выполнен, lastrowid={cursor.lastrowid}")

                        # Получаем ID поставки - сначала проверяем, есть ли shipment.shipment_id
                        if hasattr(shipment, 'shipment_id') and shipment.shipment_id:
                            shipment_id = shipment.shipment_id
                        else:
                            # После INSERT OR REPLACE всегда делаем SELECT для получения ID
                            dest_name = shipment.destination_name.encode('utf-8').decode('utf-8')

                            # Делаем SELECT для получения ID
                            cursor.execute(
                                "SELECT id FROM shipments WHERE destination_name = ?",
                                (dest_name,)
                            )
                            result = cursor.fetchone()
                            shipment_id = result[0] if result else None
                            
                            # Если не нашли, пробуем без кодировки
                            if shipment_id is None:
                                cursor.execute(
                                    "SELECT id FROM shipments WHERE destination_name = ?",
                                    (shipment.destination_name,)
                                )
                                result = cursor.fetchone()
                                shipment_id = result[0] if result else None

                            if shipment_id is None:
                                self.logger.error(f"Не удалось получить ID поставки {shipment.destination_name} после INSERT OR REPLACE")
                                self.logger.error(f"Попытка поиска: {dest_name}")
                                # Проверяем, что вообще есть в таблице
                                cursor.execute("SELECT id, destination_name FROM shipments")
                                all_shipments = cursor.fetchall()
                                self.logger.error(f"Все поставки в БД: {all_shipments}")
                                return
                    else:
                        # Для PostgreSQL используем ON CONFLICT
                        cursor.execute("""
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
                            shipment.destination_name.encode('utf-8').decode('utf-8'), 
                            shipment.font_size, 
                            shipment.label_font_size,
                            shipment.theme.encode('utf-8').decode('utf-8'), 
                            removed_items_json.encode('utf-8').decode('utf-8'),
                            parent_group.encode('utf-8').decode('utf-8') if parent_group else None, 
                            properties_json.encode('utf-8').decode('utf-8'),
                            shipment.archived, 
                            archived_date.encode('utf-8').decode('utf-8') if archived_date else None,
                            shipment.archived_by.encode('utf-8').decode('utf-8') if shipment.archived_by else None
                        ))
                        result = cursor.fetchone()
                        shipment_id = result[0] if result else None

                    # Проверяем, что shipment_id не равен None
                    if shipment_id is None:
                        self.logger.error(f"Ошибка: shipment_id равен None для поставки {shipment.destination_name}")
                        return  # Прерываем выполнение функции, чтобы избежать ошибки

                    # Коммитим UPSERT shipments, чтобы execute_many мог видеть строку (FK constraint)
                    conn.commit()

                    # Проверяем, что shipment_id существует в таблице
                    cursor.execute(f"SELECT id FROM shipments WHERE id = {placeholder}", (shipment_id,))
                    check_result = cursor.fetchone()
                    if check_result is None:
                        # shipment_id не найден, пробуем найти по destination_name
                        self.logger.warning(f"shipment_id={shipment_id} не найден, ищем по destination_name={shipment.destination_name}")
                        cursor.execute(f"SELECT id FROM shipments WHERE destination_name = {placeholder}", (shipment.destination_name,))
                        name_result = cursor.fetchone()
                        if name_result:
                            shipment_id = name_result[0]
                            self.logger.info(f"Найдена поставка по имени, новый shipment_id={shipment_id}")
                            # Обновляем shipment.shipment_id для будущих сохранений
                            shipment.shipment_id = shipment_id
                        else:
                            self.logger.error(f"Поставка {shipment.destination_name} не найдена в БД!")
                            cursor.execute("SELECT id, destination_name FROM shipments")
                            all_shipments = cursor.fetchall()
                            # Преобразуем sqlite3.Row в кортежи для логирования
                            self.logger.error(f"Все поставки в БД: {[(int(r[0]), r[1]) for r in all_shipments]}")
                            return

                    # Обновляем сессию пользователя для текущей поставки
                    if hasattr(self.main_window, 'current_user') and self.main_window.current_user:
                        from database import update_user_session
                        update_user_session(shipment.destination_name, self.main_window.current_user)

                    # Используем batch-операции для улучшения производительности
                    queries_with_params = []

                    # Удаляем существующие элементы поставки
                    if use_sqlite:
                        queries_with_params.append((
                            "DELETE FROM shipment_items WHERE shipment_id = ?",
                            (shipment_id,)
                        ))
                    else:
                        queries_with_params.append((
                            "DELETE FROM shipment_items WHERE shipment_id = %s",
                            (shipment_id,)
                        ))

                    # Оптимизация: batch-вставка элементов поставки через execute_many
                    shipment_items_data = []
                    for item in shipment.shipment_items.values():
                        barcode_val = item.barcode.encode('utf-8').decode('utf-8') if isinstance(item.barcode, str) else item.barcode
                        sku_val = item.sku.encode('utf-8').decode('utf-8') if isinstance(item.sku, str) else item.sku
                        shipment_items_data.append((shipment_id, barcode_val, sku_val, item.total_qty, item.allocated_qty))

                    # Удаляем существующие коробки
                    if use_sqlite:
                        queries_with_params.append((
                            "DELETE FROM boxes WHERE shipment_id = ?",
                            (shipment_id,)
                        ))
                    else:
                        queries_with_params.append((
                            "DELETE FROM boxes WHERE shipment_id = %s",
                            (shipment_id,)
                        ))

                    # Подготавливаем вставку для коробок
                    for i, box in enumerate(shipment.boxes):
                        is_current = True if i == shipment.current_box_index else False
                        if use_sqlite:
                            queries_with_params.append((
                                """
                                INSERT OR REPLACE INTO boxes (shipment_id, box_id, is_current)
                                VALUES (?, ?, ?)
                                """,
                                (shipment_id, box.box_id.encode('utf-8').decode('utf-8') if isinstance(box.box_id, str) else box.box_id, is_current)
                            ))
                        else:
                            # Для PostgreSQL используем ON CONFLICT с RETURNING для получения ID
                            queries_with_params.append((
                                """
                                INSERT INTO boxes (shipment_id, box_id, is_current)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (shipment_id, box_id) DO UPDATE SET is_current = EXCLUDED.is_current
                                RETURNING id
                                """,
                                (shipment_id, box.box_id.encode('utf-8').decode('utf-8') if isinstance(box.box_id, str) else box.box_id, is_current)
                            ))

                    # Выполняем все подготовленные запросы в одной транзакции
                    # Для PostgreSQL сначала вставляем коробки и собираем их ID
                    if not use_sqlite:
                        # Оптимизация: batch INSERT shipment_items через execute_many
                        if shipment_items_data:
                            from db_connection import execute_many
                            execute_many(
                                "INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty) VALUES %s ON CONFLICT (shipment_id, barcode) DO UPDATE SET sku = EXCLUDED.sku",
                                shipment_items_data,
                                template="(%s, %s, %s, %s, %s)"
                            )

                        # Вставляем коробки
                        for query, params in queries_with_params:
                            if 'RETURNING id' not in query:
                                cursor.execute(query, params)

                        # Получаем актуальные ID коробок из БД (надёжнее чем RETURNING id)
                        cursor.execute(
                            "SELECT id, box_id FROM boxes WHERE shipment_id = %s",
                            (shipment_id,)
                        )
                        box_id_map = {row[1]: row[0] for row in cursor.fetchall()}

                        # Теперь используем box_id_map для вставки box_items
                        for i, box in enumerate(shipment.boxes):
                            box_db_id = box_id_map.get(box.box_id.encode('utf-8').decode('utf-8') if isinstance(box.box_id, str) else box.box_id)

                            if box_db_id:
                                # Удаляем существующие элементы коробок (если нужно)
                                if not preserve_box_items:
                                    cursor.execute(
                                        "DELETE FROM box_items WHERE box_id = %s",
                                        (box_db_id,)
                                    )

                    # Оптимизация: batch INSERT box_items через execute_many
                    box_items_data = []
                    for i, box in enumerate(shipment.boxes):
                        box_db_id = box_id_map.get(box.box_id.encode('utf-8').decode('utf-8') if isinstance(box.box_id, str) else box.box_id)
                        if box_db_id:
                            for barcode, qty in box.items.items():
                                barcode_val = barcode.encode('utf-8').decode('utf-8') if isinstance(barcode, str) else barcode
                                box_items_data.append((box_db_id, barcode_val, qty))

                    if box_items_data:
                        from db_connection import execute_many
                        execute_many(
                            "INSERT INTO box_items (box_id, barcode, qty) VALUES %s ON CONFLICT (box_id, barcode) DO UPDATE SET qty = EXCLUDED.qty",
                            box_items_data,
                            template="(%s, %s, %s)"
                        )

                    # SQLite path: выполняем все запросы и вставляем shipment_items/box_items
                    if use_sqlite:
                        # batch INSERT shipment_items через executemany
                        if shipment_items_data:
                            cursor.executemany(
                                "INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty) VALUES (?, ?, ?, ?, ?)",
                                shipment_items_data
                            )

                        # Для SQLite выполняем все запросы как обычно
                        for query, params in queries_with_params:
                            cursor.execute(query, params)
                        
                        # Получаем ID коробок и вставляем box_items
                        box_ids = [box.box_id for box in shipment.boxes]
                        if box_ids:
                            placeholders = ','.join(['?'] * len(box_ids))
                            cursor.execute(
                                f"SELECT id, box_id FROM boxes WHERE shipment_id = ? AND box_id IN ({placeholders})",
                                [shipment_id] + [bid.encode('utf-8').decode('utf-8') if isinstance(bid, str) else bid for bid in box_ids]
                            )
                            box_id_map = {row[1]: row[0] for row in cursor.fetchall()}
                        else:
                            box_id_map = {}

                        # Оптимизация: batch INSERT box_items через executemany
                        sqlite_box_items_data = []
                        for i, box in enumerate(shipment.boxes):
                            box_db_id = box_id_map.get(box.box_id)
                            if box_db_id:
                                # Удаляем существующие элементы коробок (если нужно)
                                if not preserve_box_items:
                                    cursor.execute(
                                        "DELETE FROM box_items WHERE box_id = ?",
                                        (box_db_id,)
                                    )
                                for barcode, qty in box.items.items():
                                    barcode_val = barcode.encode('utf-8').decode('utf-8') if isinstance(barcode, str) else barcode
                                    sqlite_box_items_data.append((box_db_id, barcode_val, qty))

                        if sqlite_box_items_data:
                            cursor.executemany(
                                "INSERT OR REPLACE INTO box_items (box_id, barcode, qty) VALUES (?, ?, ?)",
                                sqlite_box_items_data
                            )

                    # Обновляем сессию пользователя для отслеживания активности в этой поставке
                    # Вызываем ПОСЛЕ коммита основной транзакции
                    conn.commit()
                    
                    if hasattr(self.main_window, 'current_user') and self.main_window.current_user:
                        from database import update_user_session
                        update_user_session(shipment.destination_name, self.main_window.current_user)

                    # Update cache after successful save
                    self.update_cache(shipment)
                    self.logger.info(f"Поставка успешно сохранена: {shipment.destination_name}")
                except Exception:
                    # В случае ошибки внутри внутреннего try делаем rollback
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    raise
                finally:
                    # Закрываем курсор
                    if cursor:
                        cursor.close()
            finally:
                # Возвращаем соединение в пул
                _release_connection(conn)

        except Exception as e:
            self.logger.error(f"Ошибка сохранения поставки: {e}", exc_info=True)
            # Делаем rollback в случае ошибки
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    def update_cache(self, shipment):
        """Update the local cache with shipment data"""
        # Update shipment cache
        self.shipment_cache[shipment.destination_name] = {
            'font_size': shipment.font_size,
            'label_font_size': shipment.label_font_size,
            'theme': shipment.theme,
            'removed_items': shipment.removed_items,
            'parent_group': shipment.parent_group.group_name if shipment.parent_group else None,
            'properties': shipment.properties,
            'archived': shipment.archived,
            'archived_date': shipment.archived_date,
            'archived_by': shipment.archived_by
        }
        
        # Update shipment items cache
        self.shipment_items_cache[shipment.destination_name] = shipment.shipment_items.copy()
        
        # Update boxes cache
        self.boxes_cache[shipment.destination_name] = shipment.boxes[:]
        
        # Update box items cache
        box_items = {}
        for i, box in enumerate(shipment.boxes):
            box_items[i] = box.items.copy()
        self.box_items_cache[shipment.destination_name] = box_items

    def clear_cache(self, shipment_name=None):
        """Clear the local cache"""
        if shipment_name:
            # Clear specific shipment from cache
            if shipment_name in self.shipment_cache:
                del self.shipment_cache[shipment_name]
            if shipment_name in self.shipment_items_cache:
                del self.shipment_items_cache[shipment_name]
            if shipment_name in self.boxes_cache:
                del self.boxes_cache[shipment_name]
            if shipment_name in self.box_items_cache:
                del self.box_items_cache[shipment_name]
        else:
            # Clear all cache
            self.shipment_cache.clear()
            self.shipment_items_cache.clear()
            self.boxes_cache.clear()
            self.box_items_cache.clear()

    def new_box(self):
        if not self.main_window.current_shipment:
            QMessageBox.warning(self.main_window, "Ошибка", "Сначала выберите или создайте поставку!")
            return
        next_num = self.main_window.current_shipment.get_next_box_number()
        box_id = f"Коробка-{next_num}"
        box = Box(box_id)
        self.main_window.current_shipment.boxes.append(box)
        self.main_window.current_shipment.current_box_index = len(self.main_window.current_shipment.boxes) - 1
        # Сбрасываем кэши в модели поставки при создании новой коробки
        self.main_window.current_shipment.invalidate_caches()
        # Обновляем интерфейс для немедленного отображения изменений
        self.main_window.ui_updater.update_current_components()
        self.main_window.ui_updater.update_shipments_tree()
        self.main_window.statusBar().showMessage(f"Создана новая коробка: {box_id}", 3000)
        
        # Отложенное полное сохранение (коробка добавлена)
        self.schedule_full_save()
        
        # Update cache
        if self.main_window.current_shipment:
            self.update_cache(self.main_window.current_shipment)

    def handle_scan(self):
        """
        Обработка сканирования штрихкода.
        Использует атомарное обновление allocated_qty и блокировки для предотвращения конфликтов
        при одновременной работе нескольких пользователей.
        """
        # Защита от повторного срабатывания сканера (debouncing)
        if self.is_scanning:
            return
        self.is_scanning = True

        self._process_scan()

    def _reset_scanning_flag(self):
        """Сброс флага сканирования и возврат фокуса"""
        self.is_scanning = False
        # Возвращаем фокус на поле ввода
        self.main_window.scan_input.setFocus()

    def _process_scan(self):
        """Внутренний метод для обработки сканирования (асинхронный)"""
        barcode = self.main_window.scan_input.text().strip()
        if not barcode:
            return
        if not self.main_window.current_shipment:
            QMessageBox.warning(self.main_window, "Ошибка", "Сначала выберите или создайте поставку!")
            self.main_window.scan_input.clear()
            return
        if self.main_window.current_shipment.current_box_index < 0:
            QMessageBox.warning(self.main_window, "Ошибка", "Сначала создайте или выберите коробку!")
            self.main_window.scan_input.clear()
            return

        if barcode in self.main_window.current_shipment.removed_items:
            utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
            QMessageBox.warning(self.main_window, "Ошибка", f"Товар «{barcode}» удален из поставки и не может быть добавлен!")
            self.main_window.scan_input.selectAll()
            self._reset_scanning_flag()
            return

        if barcode not in self.main_window.current_shipment.shipment_items:
            utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
            QMessageBox.warning(self.main_window, "Ошибка", f"Штрихкод «{barcode}» не найден в поставке!")
            self.main_window.scan_input.selectAll()
            self._reset_scanning_flag()
            return

        current_box = self.main_window.current_shipment.boxes[self.main_window.current_shipment.current_box_index]
        shipment_item = self.main_window.current_shipment.shipment_items[barcode]

        # Проверяем оставшееся количество локально (для быстрого отказа)
        if shipment_item.remaining_qty <= 0:
            utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
            QMessageBox.warning(self.main_window, "Ошибка", f"Товар «{barcode}» уже полностью распределен!")
            self.main_window.scan_input.selectAll()
            self._reset_scanning_flag()
            return

        # Запускаем асинхронную обработку сканирования
        self.main_window.async_manager.execute_async(
            self._scan_db_operations,
            callback=self._on_scan_db_operations_finished,
            error_callback=self._on_scan_db_operations_error,
            barcode=barcode,
            shipment_item=shipment_item,
            current_box=current_box,
        )

    def _scan_db_operations(self, barcode, shipment_item, current_box):
        """Выполняет DB-операции сканирования в фоновом потоке"""
        from database import atomic_increment_allocated_qty
        from lock_manager import is_item_locked_by_other

        shipment_id = getattr(self.main_window.current_shipment, 'shipment_id', None)
        current_user = getattr(self.main_window, 'current_user', 'unknown')

        # Проверяем блокировку
        if shipment_id is not None and is_item_locked_by_other(barcode, shipment_id, current_user):
            lock_info = self._get_lock_manager().get_lock_info(barcode, shipment_id)
            return {
                'success': False,
                'error': 'locked',
                'lock_info': lock_info,
                'barcode': barcode,
            }

        # Атомарное обновление
        if shipment_id is None:
            return {
                'success': False,
                'error': 'no_shipment_id',
                'barcode': barcode,
            }

        success, new_qty, message = atomic_increment_allocated_qty(shipment_id, barcode, 1)
        if not success:
            return {
                'success': False,
                'error': 'db_error',
                'message': message,
                'barcode': barcode,
            }

        return {
            'success': True,
            'new_qty': new_qty,
            'barcode': barcode,
            'shipment_id': shipment_id,
        }

    def _on_scan_db_operations_finished(self, result):
        """Обработка результата DB-операций сканирования (главный поток)"""
        barcode = result.get('barcode')
        current_box = self.main_window.current_shipment.boxes[self.main_window.current_shipment.current_box_index]
        shipment_item = self.main_window.current_shipment.shipment_items[barcode]

        if not result['success']:
            error = result.get('error')
            if error == 'locked':
                lock_info = result.get('lock_info')
                if lock_info:
                    utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
                    QMessageBox.warning(
                        self.main_window, "Ошибка",
                        f"Товар «{barcode}» заблокирован пользователем {lock_info.get('username', 'неизвестно')}!\n"
                        f"До окончания блокировки: {self._format_lock_time(lock_info.get('expires_at'))}"
                    )
            elif error == 'no_shipment_id':
                self.logger.warning("shipment_id не найден, используем неатомарное обновление")
                if shipment_item.allocated_qty >= shipment_item.total_qty:
                    utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
                    QMessageBox.warning(self.main_window, "Ошибка", f"Товар «{barcode}» уже полностью распределен!")
                    self.main_window.scan_input.selectAll()
                    self._reset_scanning_flag()
                    return
                current_box.add_item(barcode)
                shipment_item.allocated_qty += 1
                self._finalize_scan(barcode, shipment_item, current_box)
                return
            else:
                utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
                QMessageBox.warning(self.main_window, "Ошибка", f"Не удалось добавить товар: {result.get('message')}")
            self.main_window.scan_input.selectAll()
            self._reset_scanning_flag()
            return

        # Успех: обновляем локальную модель
        current_box.add_item(barcode)
        shipment_item.allocated_qty = result['new_qty']
        self.main_window.current_shipment.invalidate_caches()

        # Инвалидация кэша в фоне
        QTimer.singleShot(0, lambda: self._invalidate_cache_async(result['shipment_id']))

        self._finalize_scan(barcode, shipment_item, current_box)

    def _finalize_scan(self, barcode, shipment_item, current_box):
        """Финализация сканирования: очистка поля, звук, обновление UI"""
        self.main_window.scan_input.clear()
        self.is_scanning = False
        self.main_window.scan_input.setFocus()

        if shipment_item.allocated_qty >= shipment_item.total_qty:
            utils.play_sound("ok_all.wav", False)
            self.main_window.statusBar().showMessage(f"Добавлена последняя штука {barcode}", 2000)
        else:
            utils.play_sound(self.main_window.ok_sound, self.main_window.tone_sound)
            self.main_window.statusBar().showMessage(f"Добавлен {barcode} в коробку {current_box.box_id}", 200)

        self.main_window.ui_updater.update_current_box_table()
        self.schedule_save()

    def _on_scan_db_operations_error(self, error_msg):
        """Обработка ошибки DB-операций сканирования"""
        self.logger.error(f"Ошибка DB-операций сканирования: {error_msg}")
        utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
        QMessageBox.warning(self.main_window, "Ошибка", f"Ошибка при обработке сканирования: {error_msg}")
        self._reset_scanning_flag()

    def _get_lock_manager(self):
        """Получить экземпляр LockManager"""
        from lock_manager import get_lock_manager
        return get_lock_manager()

    def _format_lock_time(self, expires_at_str) -> str:
        """Форматирует оставшееся время блокировки"""
        if not expires_at_str:
            return "неизвестно"
        try:
            from datetime import datetime
            expires_at = datetime.fromisoformat(expires_at_str)
            remaining = (expires_at - datetime.now()).total_seconds()
            if remaining > 0:
                return f"{int(remaining)} сек."
            return "истекает"
        except Exception:
            return "неизвестно"

    def _invalidate_cache_async(self, shipment_id):
        """Асинхронная инвалидация кэша для других клиентов"""
        try:
            from database import invalidate_cache_for_shipment
            invalidate_cache_for_shipment(shipment_id, ['shipment_items', 'box_items'],
                                         getattr(self.main_window, 'current_user', 'unknown'))
            parent_group = self.main_window.current_shipment.parent_group
            if parent_group:
                parent_group.invalidate_caches()
            self.main_window.ui_updater.update_current_components()
            self.main_window.ui_updater._update_shipments_tree_progress()
        except Exception as e:
            self.logger.debug(f"Ошибка async инвалидации: {e}")

    def save_shipment_immediate(self):
        """Немедленное сохранение текущей поставки в БД"""
        if self.main_window.current_shipment:
            self.main_window.data_controller.save_shipment_immediate(
                self.main_window.current_shipment,
                self.main_window.current_shipment.current_box_index
            )

    def schedule_save(self):
        """Отложенное инкрементальное сохранение для уменьшения операций БД"""
        # Переиспользуем один таймер вместо создания нового
        if self.save_timer is None:
            from PyQt6.QtCore import QTimer
            self.save_timer = QTimer()
            self.save_timer.setSingleShot(True)
            self.save_timer.timeout.connect(self.perform_save)
        else:
            self.save_timer.stop()
        
        self.save_timer.start(self.save_delay)
        self.save_pending = True

    def schedule_full_save(self):
        """Отложенное полное сохранение (для структурных изменений)"""
        if self.save_timer is None:
            from PyQt6.QtCore import QTimer
            self.save_timer = QTimer()
            self.save_timer.setSingleShot(True)
            self.save_timer.timeout.connect(self.perform_full_save)
        else:
            self.save_timer.stop()
            # Переподключаем на perform_full_save
            try:
                self.save_timer.timeout.disconnect(self.perform_save)
            except Exception:
                pass
            self.save_timer.timeout.connect(self.perform_full_save)
        
        self.save_timer.start(self.save_delay)
        self.save_pending = True

    def perform_full_save(self):
        """Полное сохранение текущей поставки в БД"""
        if self.main_window.current_shipment:
            self.logger.debug("perform_full_save: полное сохранение поставки")
            self.main_window.data_controller.save_shipment(self.main_window.current_shipment)
            self.save_pending = False
            self.save_timer = None

    def perform_save(self):
        """Actually perform the save operation"""
        if self.save_pending and self.main_window.current_shipment:
            # Минимальное логирование для производительности
            self.logger.debug(f"perform_save: сохранение коробки {self.main_window.current_shipment.boxes[self.main_window.current_shipment.current_box_index].box_id if self.main_window.current_shipment.current_box_index >= 0 else 'N/A'}")

            # ОПТИМИЗАЦИЯ: Сохраняем только текущую коробку инкрементально
            self._save_current_box_incremental()
            
            self.save_pending = False
            # Clear the timer reference after saving
            self.save_timer = None

    def _save_current_box_incremental(self):
        """Инкрементальное сохранение только текущей коробки без полной пересохранения поставки"""
        try:
            shipment = self.main_window.current_shipment
            if not shipment or shipment.current_box_index < 0:
                return
            
            current_box = shipment.boxes[shipment.current_box_index]
            shipment_id = getattr(shipment, 'shipment_id', None)
            
            if not shipment_id:
                # Если нет ID, используем полное сохран
                self.main_window.save_session()
                return
            
            from db_connection import get_db_type, execute_transaction, execute_query
            import json
            
            db_type = get_db_type()
            use_sqlite = db_type == "sqlite"
            placeholder = "?" if use_sqlite else "%s"
            
            queries = []
            
            # 1. Сохраняем основные данные поставки (только измененные поля)
            removed_items_json = json.dumps(shipment.removed_items, ensure_ascii=False)
            properties_json = json.dumps(shipment.properties.to_dict(), ensure_ascii=False)
            archived_date = shipment.archived_date.isoformat() if shipment.archived_date else None
            
            if use_sqlite:
                queries.append((
                    """INSERT OR REPLACE INTO shipments (
                        destination_name, font_size, label_font_size, theme,
                        removed_items, parent_group, properties,
                        archived, archived_date, archived_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (shipment.destination_name, shipment.font_size, shipment.label_font_size,
                     shipment.theme, removed_items_json,
                     shipment.parent_group.group_name if shipment.parent_group else None,
                     properties_json, 1 if shipment.archived else 0,
                     archived_date, shipment.archived_by)
                ))
            else:
                queries.append((
                    """INSERT INTO shipments (destination_name, font_size, label_font_size, theme, removed_items, parent_group, properties, archived, archived_date, archived_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (destination_name) DO UPDATE SET
                        font_size = EXCLUDED.font_size, label_font_size = EXCLUDED.label_font_size,
                        theme = EXCLUDED.theme, removed_items = EXCLUDED.removed_items,
                        parent_group = EXCLUDED.parent_group, properties = EXCLUDED.properties,
                        archived = EXCLUDED.archived, archived_date = EXCLUDED.archived_date,
                        archived_by = EXCLUDED.archived_by
                    RETURNING id""",
                    (shipment.destination_name, shipment.font_size, shipment.label_font_size,
                     shipment.theme, removed_items_json,
                     shipment.parent_group.group_name if shipment.parent_group else None,
                     properties_json, shipment.archived, archived_date, shipment.archived_by)
                ))
            
            # 2. Обновляем статус текущей коробки
            is_current = True if not use_sqlite else 1
            not_current = False if not use_sqlite else 0
            box_id_str = current_box.box_id
            
            queries.append((
                f"UPDATE boxes SET is_current = {placeholder} WHERE shipment_id = {placeholder}",
                (not_current, shipment_id)
            ))
            
            if use_sqlite:
                queries.append((
                    f"INSERT OR REPLACE INTO boxes (shipment_id, box_id, is_current) VALUES ({placeholder}, {placeholder}, {placeholder})",
                    (shipment_id, box_id_str, is_current)
                ))
            else:
                queries.append((
                    f"""INSERT INTO boxes (shipment_id, box_id, is_current) VALUES ({placeholder}, {placeholder}, {placeholder})
                    ON CONFLICT (shipment_id, box_id) DO UPDATE SET is_current = EXCLUDED.is_current""",
                    (shipment_id, box_id_str, is_current)
                ))
            
            execute_transaction(queries)
            
            # 3. Получаем ID коробки
            box_result = execute_query(
                f"SELECT id FROM boxes WHERE shipment_id = {placeholder} AND box_id = {placeholder}",
                (shipment_id, box_id_str),
                fetchone=True
            )
            box_db_id = box_result[0] if box_result else None
            
            if not box_db_id:
                self.logger.error(f"Не удалось получить ID коробки {box_id_str}")
                return
            
            # 4. Сохраняем только товары в текущей коробке через UPSERT
            box_queries = []
            for barcode, qty in current_box.items.items():
                if use_sqlite:
                    box_queries.append((
                        f"INSERT OR REPLACE INTO box_items (box_id, barcode, qty) VALUES ({placeholder}, {placeholder}, {placeholder})",
                        (box_db_id, barcode, qty)
                    ))
                else:
                    box_queries.append((
                        f"""INSERT INTO box_items (box_id, barcode, qty) VALUES ({placeholder}, {placeholder}, {placeholder})
                        ON CONFLICT (box_id, barcode) DO UPDATE SET qty = EXCLUDED.qty""",
                        (box_db_id, barcode, qty)
                    ))
            
            if box_queries:
                execute_transaction(box_queries)
            
            # 5. Обновляем allocated_qty для товаров в текущей коробке
            for barcode, qty_in_box in current_box.items.items():
                item = shipment.shipment_items.get(barcode)
                if item and item.allocated_qty > 0:
                    execute_query(
                        f"UPDATE shipment_items SET allocated_qty = {placeholder}, version = version + 1, updated_at = CURRENT_TIMESTAMP WHERE shipment_id = {placeholder} AND barcode = {placeholder}",
                        (item.allocated_qty, shipment_id, barcode)
                    )
            
            self.logger.debug(f"Коробка {current_box.box_id} инкрементально сохранена ({len(current_box.items)} товаров)")
            
        except Exception as e:
            self.logger.error(f"Ошибка инкрементального сохранения: {e}", exc_info=True)
            # Fallback на полное сохранение
            self.main_window.save_session()

    def add_all_remaining_to_box_by_barcode(self, barcode, qty=None):
        """Добавить указанное количество товара в коробку по штрихкоду
        Использует атомарное обновление для предотвращения конфликтов.

        Args:
            barcode: штрихкод товара
            qty: количество для добавления (по умолчанию = remaining_qty)
        """
        if not self.main_window.current_shipment:
            return
        if self.main_window.current_shipment.current_box_index < 0:
            QMessageBox.warning(self.main_window, "Ошибка", "Сначала создайте или выберите коробку!")
            return

        if barcode in self.main_window.current_shipment.removed_items:
            utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
            QMessageBox.warning(self.main_window, "Ошибка", f"Товар «{barcode}» удален из поставки и не может быть добавлен!")
            return

        current_box = self.main_window.current_shipment.boxes[self.main_window.current_shipment.current_box_index]
        shipment_item = self.main_window.current_shipment.shipment_items[barcode]

        # Используем переданное количество или оставшееся по умолчанию
        if qty is None:
            qty_to_add = shipment_item.remaining_qty
        else:
            qty_to_add = min(qty, shipment_item.remaining_qty)

        if qty_to_add <= 0:
            utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
            QMessageBox.warning(self.main_window, "Ошибка", f"Товар «{barcode}» уже полностью распределен!")
            return

        # Атомарно увеличиваем allocated_qty в БД
        from database import atomic_increment_allocated_qty, invalidate_cache_for_shipment
        
        shipment_id = getattr(self.main_window.current_shipment, 'shipment_id', None)
        if shipment_id is None:
            # Если ID ещё нет, используем старое поведение
            self.logger.warning("shipment_id не найден, используем неатомарное обновление")
            current_box.add_item(barcode, qty_to_add)
            shipment_item.allocated_qty += qty_to_add
        else:
            # Атомарное обновление через БД
            success, new_qty, message = atomic_increment_allocated_qty(shipment_id, barcode, qty_to_add)
            
            if not success:
                utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
                QMessageBox.warning(self.main_window, "Ошибка", f"Не удалось добавить товар: {message}")
                return
            
            # Обновляем локальную модель
            current_box.add_item(barcode, qty_to_add)
            shipment_item.allocated_qty = new_qty

            # Создаём запись об инвалидации кэша для других клиентов
            invalidate_cache_for_shipment(shipment_id, ['shipment_items', 'box_items'],
                                         getattr(self.main_window, 'current_user', 'unknown'))

        # Сбрасываем кэши в модели поставки при изменении распределения товаров
        self.main_window.current_shipment.invalidate_caches()

        # Также инвалидируем кэш родительской групповой поставки, если она есть
        parent_group = self.main_window.current_shipment.parent_group
        if parent_group:
            parent_group.invalidate_caches()

        # Воспроизводим звук ПЕРЕД обновлением UI для мгновенного отклика
        utils.play_sound(self.main_window.ok_sound, self.main_window.tone_sound)

        # Сохраняем текущий фокус перед обновлением UI
        current_row = self.main_window.shipment_table.currentRow()
        current_column = self.main_window.shipment_table.currentColumn()

        # Отключаем сортировку на время обновления, чтобы сохранить позицию строк
        self.main_window.shipment_table.setSortingEnabled(False)

        # Обновляем таблицу поставки и коробки (быстрое обновление)
        self.main_window.ui_updater.update_current_components()

        # Обновляем только прогресс в дереве поставок (без полной перестройки)
        self.main_window.ui_updater._update_shipments_tree_progress()

        # Восстанавливаем фокус на той же ячейке
        if current_row >= 0 and current_column >= 0:
            self.main_window.shipment_table.setCurrentCell(current_row, current_column)

        # Use longer message duration for better UX
        self.main_window.statusBar().showMessage(f"Добавлено {qty_to_add} шт. {barcode} в коробку {current_box.box_id}", 3000)

        # Немедленное сохранение поставки после добавления товара
        self.save_shipment_immediate()

    def add_all_remaining_for_all_items_to_box(self):
        """Добавить весь остаток всех товаров в текущую коробку
        
        Проходит по всем товарам в поставке и добавляет их остаток в текущую коробку.
        """
        if not self.main_window.current_shipment:
            return
        if self.main_window.current_shipment.current_box_index < 0:
            QMessageBox.warning(self.main_window, "Ошибка", "Сначала создайте или выберите коробку!")
            return

        current_box = self.main_window.current_shipment.boxes[self.main_window.current_shipment.current_box_index]
        total_added = 0
        items_added = 0

        # Проходим по всем товарам в поставке
        for barcode, shipment_item in self.main_window.current_shipment.shipment_items.items():
            # Пропускаем удаленные товары
            if barcode in self.main_window.current_shipment.removed_items:
                continue

            # Получаем количество для добавления
            qty_to_add = shipment_item.remaining_qty
            if qty_to_add <= 0:
                continue

            # Добавляем товар в коробку
            current_box.add_item(barcode, qty_to_add)
            shipment_item.allocated_qty += qty_to_add
            total_added += qty_to_add
            items_added += 1

        # Сбрасываем кэши в модели поставки при изменении распределения товаров
        self.main_window.current_shipment.invalidate_caches()

        # Воспроизводим звук
        utils.play_sound(self.main_window.ok_sound, self.main_window.tone_sound)

        # Отключаем сортировку на время обновления
        self.main_window.shipment_table.setSortingEnabled(False)

        # Обновляем таблицу поставки и коробки (быстрое обновление)
        self.main_window.ui_updater.update_current_components()

        # Обновляем только прогресс в дереве поставок (без полной перестройки)
        self.main_window.ui_updater._update_shipments_tree_progress()

        # Показываем сообщение
        if items_added > 0:
            self.main_window.statusBar().showMessage(
                f"Добавлено {total_added} шт. ({items_added} поз.) в коробку {current_box.box_id}",
                3000
            )
        else:
            utils.play_sound(self.main_window.error_sound, self.main_window.tone_sound)
            QMessageBox.information(self.main_window, "Информация", "Все товары уже распределены!")

        # Немедленное сохранение поставки после добавления товаров
        self.save_shipment_immediate()

    def on_shipment_cell_changed(self, row, column):
        if not self.main_window.current_shipment or column != ColumnIndex.NAME:
            return
        item = self.main_window.shipment_table.item(row, column)
        if not item:
            return
        barcode = self.main_window.shipment_table.item(row, ColumnIndex.BARCODE).text()
        if barcode not in self.main_window.current_shipment.shipment_items:
            return
        try:
            new_total = int(item.text())
            if new_total < 0:
                raise ValueError
            
            shipment_item = self.main_window.current_shipment.shipment_items[barcode]
            
            # Проверяем, не превышает ли новое количество уже распределённое
            if new_total < shipment_item.allocated_qty:
                # Новое количество меньше распределённого - показываем предупреждение
                QMessageBox.warning(
                    self.main_window, "Предупреждение",
                    f"Новое количество ({new_total}) меньше уже распределённого по коробкам ({shipment_item.allocated_qty}).\n"
                    f"Сначала уменьшите количество в коробках или удалите товары из коробок."
                )
                # Возвращаем старое значение
                item.setText(str(shipment_item.total_qty))
                return
            
            shipment_item.total_qty = new_total
            # Сбрасываем кэши в модели поставки при изменении количества товара
            self.main_window.current_shipment.invalidate_caches()
            # Update UI immediately for responsiveness, but delay database save
            # Избегаем частых обновлений UI при изменении количества
            # self.main_window.update_ui()  # Убираем обновление UI при изменении количества в поставке
            # Обновляем видимость кнопки "+ Все"
            self.main_window._update_add_all_button_visibility()
            # Структурное изменение — полное сохранение
            self.schedule_full_save()
        except ValueError:
            QMessageBox.warning(self.main_window, "Ошибка", "Количество должно быть неотрицательным целым числом!")
            self.main_window.update_ui()

    def on_box_cell_changed(self, row, column):
        """Обработчик изменения ячейки в таблице коробки"""
        if not self.main_window.current_shipment or self.main_window.current_shipment.current_box_index < 0 or column != BoxColumnIndex.QTY:
            return
            
        try:
            # Получаем текущую коробку
            current_box = self.main_window.current_shipment.boxes[self.main_window.current_shipment.current_box_index]
            
            # Проверяем, что строка в допустимом диапазоне
            if row >= len(current_box.items):
                return
                
            # Получаем ключи элементов коробки
            keys = list(current_box.items.keys())
            if row >= len(keys):
                return
                
            # Получаем штрихкод элемента
            barcode = keys[row]
            item = current_box.items[barcode]
            
            # Разрешаем редактирование только для столбца количества (индекс 2)
            item_widget = self.main_window.current_box_table.item(row, column)
            if not item_widget:
                return
                
            new_qty_text = item_widget.text().strip()
            try:
                new_qty = int(new_qty_text)
                if new_qty < 0:
                    raise ValueError("Количество не может быть отрицательным")
                    
                # Обновляем количество товара в коробке
                shipment_item = self.main_window.current_shipment.shipment_items.get(barcode)
                
                if barcode in self.main_window.current_shipment.removed_items:
                    if new_qty > current_box.items.get(barcode, 0):
                        QMessageBox.warning(
                            self.main_window, "Ошибка",
                            f"Товар «{barcode}» удален из поставки! Можно только уменьшать количество."
                        )
                        self.main_window.update_ui()
                        return
                
                if shipment_item:
                    old_qty = current_box.items.get(barcode, 0)
                    diff = new_qty - old_qty
                    if shipment_item.allocated_qty + diff > shipment_item.total_qty:
                        QMessageBox.warning(
                            self.main_window, "Ошибка",
                            f"Нельзя распределить больше {shipment_item.total_qty} единиц товара {barcode}!"
                        )
                        self.main_window.update_ui()
                        return
                    shipment_item.allocated_qty += diff
                
                current_box.set_item_qty(barcode, new_qty)
                
                # Update removed_items if this item is in the removed list
                if barcode in self.main_window.current_shipment.removed_items:
                    removed_qty = self.main_window.current_shipment.removed_items[barcode]['allocated_qty']
                    new_removed_qty = removed_qty - diff  # When we reduce quantity in box, removed qty increases by the same amount
                    
                    if new_removed_qty <= 0:
                        del self.main_window.current_shipment.removed_items[barcode]
                    else:
                        self.main_window.current_shipment.removed_items[barcode]['allocated_qty'] = new_removed_qty
                elif new_qty == 0 and barcode in self.main_window.current_shipment.removed_items:
                    del self.main_window.current_shipment.removed_items[barcode]
                
                # Check if this item should be added to removed_items due to total quantity exceeded
                # This can happen if the total quantity in shipment was reduced but this box still has more than allowed
                if (shipment_item and
                    shipment_item.allocated_qty > shipment_item.total_qty and
                    barcode not in self.main_window.current_shipment.removed_items):
                    excess_qty = shipment_item.allocated_qty - shipment_item.total_qty
                    self.main_window.current_shipment.removed_items[barcode] = {
                        'sku': shipment_item.sku,
                        'allocated_qty': excess_qty
                    }
                
                # Also check if we need to remove item from removed_items if it's no longer in excess
                if (barcode in self.main_window.current_shipment.removed_items and
                    shipment_item and
                    shipment_item.allocated_qty <= shipment_item.total_qty):
                    del self.main_window.current_shipment.removed_items[barcode]

                # Сбрасываем кэши в модели поставки при изменении распределения товаров
                self.main_window.current_shipment.invalidate_caches()

                # Обновляем интерфейс для немедленного отображения изменений
                self.main_window.ui_updater.update_current_components()
                self.main_window.ui_updater.update_shipments_tree()
                
                # Use longer message duration for better UX
                self.main_window.statusBar().showMessage(f"Количество товара {barcode} изменено на {new_qty}", 3000)
                
                # Структурное изменение — полное сохранение
                self.schedule_full_save()
            except ValueError as e:
                QMessageBox.warning(self.main_window, "Ошибка", f"Некорректное количество: {e}")
                # Восстанавливаем предыдущее значение
                self.main_window.current_box_table.cellChanged.disconnect(self.main_window.on_box_cell_changed)
                self.main_window.current_box_table.item(row, column).setText(str(current_box.items.get(barcode, 0)))
                self.main_window.current_box_table.cellChanged.connect(self.main_window.on_box_cell_changed)
        except Exception as e:
            self.logger.error(f"Ошибка обработки изменения ячейки коробки: {e}")

    def show_shipment_properties(self, shipment_name):
        """Показать свойства поставки"""
        # Ищем поставку в обычных поставках
        if shipment_name in self.main_window.shipments:
            shipment = self.main_window.shipments[shipment_name]
        else:
            # Ищем поставку в групповых поставках
            shipment = None
            for group in self.main_window.group_shipments.values():
                # Обеспечиваем обратную совместимость: сначала проверяем по ключу (старая схема)
                if shipment_name in group.sub_shipments:
                    shipment = group.sub_shipments[shipment_name]
                    break
                else:
                    # Для новых данных ищем по original_destination_name
                    found_shipment = None
                    for key, sub_shipment in group.sub_shipments.items():
                        if (hasattr(sub_shipment, 'original_destination_name') and
                            sub_shipment.original_destination_name == shipment_name):
                            found_shipment = sub_shipment
                            break
                    
                    if found_shipment:
                        shipment = found_shipment
                        break
        
        if not shipment:
            QMessageBox.warning(self.main_window, "Ошибка", "Поставка не найдена!")
            return
        
        dialog = ShipmentPropertiesDialog(shipment, self.main_window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.save_shipment(shipment)
            self.main_window.statusBar().showMessage(f"Свойства поставки '{shipment_name}' сохранены", 3000)

    def show_shipment_context_menu(self, position):
        item = self.main_window.shipments_tree_widget.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self.main_window)
        
        if hasattr(item, 'shipment') and not hasattr(item, 'box'):
            shipment = item.shipment
            update_action = menu.addAction("Обновить состав поставки")
            properties_action = menu.addAction("Свойства")
            export_action = menu.addAction("Экспорт коробок")
            import_action = menu.addAction("Импорт коробок")
            rename_action = menu.addAction("Переименовать поставку")
            delete_action = menu.addAction("Удалить поставку")
            
            action = menu.exec(self.main_window.shipments_tree_widget.mapToGlobal(position))
            if action == update_action:
                self.main_window.shipment_operations.update_shipment_composition()
            elif action == properties_action:
                self.show_shipment_properties(shipment.destination_name)
            elif action == export_action:
                self.export_boxes()
            elif action == import_action:
                self.import_boxes()
            elif action == rename_action:
                self.main_window.shipment_operations.rename_shipment(shipment.destination_name)
            elif action == delete_action:
                self.main_window.shipment_operations.delete_shipment(shipment.destination_name)
                
        elif hasattr(item, 'group_shipment'):
            group_shipment = item.group_shipment
            update_group_action = menu.addAction("Обновить состав групповой поставки")
            export_all_action = menu.addAction("Экспорт всех коробок")
            rename_group_action = menu.addAction("Переименовать группу")
            delete_group_action = menu.addAction("Удалить группу")
            menu.addSeparator()
            properties_group_action = menu.addAction("Свойства")

            action = menu.exec(self.main_window.shipments_tree_widget.mapToGlobal(position))
            if action == update_group_action:
                self.main_window.shipment_operations.update_group_shipment_composition(group_shipment)
            elif action == export_all_action:
                self.export_all_group_boxes(group_shipment)
            elif action == rename_group_action:
                self.main_window.shipment_operations.rename_group_shipment(group_shipment.group_name)
            elif action == delete_group_action:
                self.main_window.shipment_operations.delete_group_shipment(group_shipment.group_name)
            elif action == properties_group_action:
                self.main_window.show_group_shipment_properties(group_shipment)
        
        elif hasattr(item, 'box'):
            box = item.box
            shipment = item.shipment
            if shipment:
                # Находим индекс коробки в её поставке
                index = -1
                for i, b in enumerate(shipment.boxes):
                    if b == box:
                        index = i
                        break

                if index >= 0:
                    delete_action = menu.addAction("Удалить коробку")
                    rename_action = menu.addAction("Переименовать коробку")

                    action = menu.exec(self.main_window.shipments_tree_widget.mapToGlobal(position))
                    if action == delete_action:
                        self.delete_box(index, shipment)
                    elif action == rename_action:
                        self.rename_box(index, shipment)

    def show_box_table_context_menu(self, position):
        if not self.main_window.current_shipment or self.main_window.current_shipment.current_box_index < 0:
            return
        item = self.main_window.current_box_table.itemAt(position)
        if not item:
            return
        row = item.row()
        barcode_item = self.main_window.current_box_table.item(row, BoxColumnIndex.BARCODE)
        if not barcode_item:
            return
        barcode = barcode_item.text()
        menu = QMenu(self.main_window)
        edit_qty_action = menu.addAction("Изменить количество")
        delete_action = menu.addAction("Удалить из коробки")
        
        action = menu.exec(self.main_window.current_box_table.mapToGlobal(position))
        if action == edit_qty_action:
            # Вызов диалога изменения количества
            self.main_window.open_quantity_edit_dialog(row)
        elif action == delete_action:
            self.remove_item_from_box(barcode)

    def delete_box(self, index, shipment=None):
        """
        Удалить коробку по индексу из указанной поставки или текущей.
        
        Args:
            index: Индекс коробки для удаления
            shipment: Поставка, из которой удаляем (если None, используется current_shipment)
        """
        if shipment is None:
            shipment = self.main_window.current_shipment
            
        if not shipment or index < 0 or index >= len(shipment.boxes):
            return
        box = shipment.boxes[index]
        reply = QMessageBox.question(
            self.main_window, "Подтверждение",
            f"Вы уверены, что хотите удалить коробку «{box.box_id}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for barcode, qty in box.items.items():
            if barcode in shipment.shipment_items:
                shipment_item = shipment.shipment_items[barcode]
                
                # Уменьшаем allocated_qty как локально, так и в БД для синхронизации
                shipment_id = getattr(shipment, 'shipment_id', None)
                if shipment_id is not None:
                    # Атомарно уменьшаем в БД
                    from database import atomic_decrement_allocated_qty
                    success, new_qty, message = atomic_decrement_allocated_qty(shipment_id, barcode, qty)
                    if success:
                        shipment_item.allocated_qty = new_qty
                    else:
                        # Если не удалось - уменьшаем локально (fallback)
                        self.logger.warning(f"Не удалось атомарно уменьшить allocated_qty для {barcode}: {message}")
                        shipment_item.allocated_qty -= qty
                else:
                    # Если shipment_id нет, используем старое поведение
                    shipment_item.allocated_qty -= qty

            # Check if this item is in removed_items and if its allocated quantity reaches 0 after removal from box
            if barcode in shipment.removed_items:
                removed_qty = shipment.removed_items[barcode]['allocated_qty']
                new_removed_qty = removed_qty - qty
                if new_removed_qty <= 0:
                    # Remove from removed_items if no more items are allocated
                    del shipment.removed_items[barcode]
                else:
                    # Update the remaining quantity in removed_items
                    shipment.removed_items[barcode]['allocated_qty'] = new_removed_qty
        shipment.boxes.pop(index)
        
        # Корректируем индекс текущей коробки только если удаляем из текущей поставки
        is_current_shipment = (shipment == self.main_window.current_shipment)
        
        if is_current_shipment:
            if shipment.current_box_index >= index:
                if shipment.current_box_index == index:
                    shipment.current_box_index = -1
                else:
                    shipment.current_box_index -= 1
            if not shipment.boxes:
                shipment.current_box_index = -1
            elif shipment.current_box_index == -1 and shipment.boxes:
                shipment.current_box_index = 0
        
        # Сбрасываем кэши в модели поставки при удалении коробки
        shipment.invalidate_caches()

        # Также инвалидируем кэш родительской групповой поставки, если она есть
        parent_group = shipment.parent_group
        if parent_group:
            parent_group.invalidate_caches()

        # Update UI immediately for responsiveness, but delay database save
        # Обновляем интерфейс для немедленного отображения изменений
        if is_current_shipment:
            self.main_window.ui_updater.update_current_components()
        self.main_window.ui_updater.update_shipments_tree()
        self.main_window.statusBar().showMessage(f"Коробка «{box.box_id}» удалена", 3000)

        # Полное сохранение — нужно удалить коробку из БД
        self.main_window.data_controller.save_shipment(shipment)

    def rename_box(self, index, shipment=None):
        if shipment is None:
            shipment = self.main_window.current_shipment
            
        if not shipment or index < 0 or index >= len(shipment.boxes):
            return
        box = shipment.boxes[index]
        
        # Извлекаем текущий номер коробки
        current_number = ""
        if box.box_id.startswith("Коробка-"):
            try:
                current_number = box.box_id.split("-")[1]
            except (IndexError, ValueError):
                current_number = ""
        
        # Получаем существующие номера коробок
        existing_numbers = []
        for b in shipment.boxes:
            if b.box_id.startswith("Коробка-"):
                try:
                    num = b.box_id.split("-")[1]
                    existing_numbers.append(num)
                except (IndexError, ValueError):
                    continue
        
        # Создаем диалог для ввода только номера
        dialog = BoxNumberDialog(current_number, existing_numbers, self.main_window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        new_number = dialog.get_new_number()
        if not new_number or new_number == current_number:
            return
        
        # Формируем новое имя коробки
        new_name = f"Коробка-{new_number}"
        box.box_id = new_name
        # Сбрасываем кэши в модели поставки при п��реименовании коробки
        shipment.invalidate_caches()
        
        # Update UI immediately for responsiveness, but delay database save
        # Обновляем интерфейс таблицы текущей коробки, таблицы постав��и и дерева поставок для немедленного отображения изменений
        if shipment == self.main_window.current_shipment:
            self.main_window.ui_updater.update_current_components()
        self.main_window.ui_updater.update_shipments_tree()
        self.main_window.statusBar().showMessage(f"Коробка переименована в «{new_name}»", 3000)
        
        # Полное сохранение — переименование коробки
        self.main_window.data_controller.save_shipment(shipment)

    def remove_item_from_box(self, barcode):
        """
        Удаляет товар из текущей коробки.
        Использует атомарное уменьшение allocated_qty для предотвращения конфликтов.
        """
        if not self.main_window.current_shipment or self.main_window.current_shipment.current_box_index < 0:
            return
        current_box = self.main_window.current_shipment.boxes[self.main_window.current_shipment.current_box_index]
        if barcode not in current_box.items:
            return
        qty = current_box.items[barcode]
        
        if barcode in self.main_window.current_shipment.shipment_items:
            # Атомарно уменьшаем allocated_qty в БД
            from database import atomic_decrement_allocated_qty, invalidate_cache_for_shipment
            
            shipment_id = getattr(self.main_window.current_shipment, 'shipment_id', None)
            if shipment_id is None:
                # Если ID ещё нет, используем старое поведение
                self.logger.warning("shipment_id не найден, используем неатомарное обновление")
                self.main_window.current_shipment.shipment_items[barcode].allocated_qty -= qty
            else:
                # Атомарное уменьшение через БД
                success, new_qty, message = atomic_decrement_allocated_qty(shipment_id, barcode, qty)
                
                if not success:
                    self.logger.warning(f"Не удалось уменьшить allocated_qty для {barcode}: {message}")
                    # Продолжаем с локальным обновлением, чтобы не блокировать UI
                    self.main_window.current_shipment.shipment_items[barcode].allocated_qty -= qty
                else:
                    # Обновляем локальную модель
                    self.main_window.current_shipment.shipment_items[barcode].allocated_qty = new_qty
                    
                    # Создаём запись об инвалидации кэша для других клиентов
                    invalidate_cache_for_shipment(shipment_id, ['shipment_items', 'box_items'],
                                                 getattr(self.main_window, 'current_user', 'unknown'))

        if barcode in self.main_window.current_shipment.removed_items:
            remaining_qty = self.main_window.current_shipment.removed_items[barcode]['allocated_qty'] - qty
            if remaining_qty <= 0:
                del self.main_window.current_shipment.removed_items[barcode]
            else:
                self.main_window.current_shipment.removed_items[barcode]['allocated_qty'] = remaining_qty

        del current_box.items[barcode]
        # Сбрасываем кэши в модели поставки при удалении товара из коробки
        self.main_window.current_shipment.invalidate_caches()

        # Также инвалидируем кэш родительской групповой поставки, если она есть
        parent_group = self.main_window.current_shipment.parent_group
        if parent_group:
            parent_group.invalidate_caches()

        # Обновляем интерфейс для немедленного отображения изменений
        self.main_window.statusBar().showMessage(f"Товар {barcode} удален из коробки", 200)

        # Обновляем таблицу поставки и коробки (быстрое обновление)
        self.main_window.ui_updater.update_current_components()

        # Обновляем только прогресс в дереве поставок (без полной перестройки)
        self.main_window.ui_updater._update_shipments_tree_progress()

        # Полное сохранение — содержимое коробки изменилось
        self.schedule_full_save()

    def delete_empty_boxes(self, shipment=None):
        """Удалить все пустые коробки из указанной поставки или текущей поставки"""
        if not shipment:
            shipment = self.main_window.current_shipment
            
        if not shipment:
            return
            
        # Находим пустые коробки (с наибольшего индекса к наименьшему, чтобы индексы не сдвигались при удалении)
        empty_box_indices = []
        for i in range(len(shipment.boxes) - 1, -1, -1):  # Идем с конца
            if shipment.boxes[i].total_items_count() == 0:  # Если коробка пуста
                empty_box_indices.append(i)
        
        if not empty_box_indices:
            QMessageBox.information(self.main_window, "Информация", "Нет пустых коробок для удаления.")
            return
            
        reply = QMessageBox.question(
            self.main_window, "Подтверждение",
            f"Найдено {len(empty_box_indices)} пустых коробок. Удалить их?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        # Удаляем пустые коробки
        for index in empty_box_indices:
            box = shipment.boxes[index]
            
            # Удаляем коробку из списка
            shipment.boxes.pop(index)
            
            # Корректируем индекс текущей коробки, если нужно
            if shipment.current_box_index >= index:
                if shipment.current_box_index == index:
                    shipment.current_box_index = -1  # Сбрасываем текущую коробку
                else:
                    shipment.current_box_index -= 1 # Сдвигаем индекс на 1 вниз
                    
        # Если коробок не осталось, сбрасываем индекс текущей коробки
        if not shipment.boxes:
            shipment.current_box_index = -1
        elif shipment.current_box_index == -1 and shipment.boxes:
            # Если текущая коробка была сброшена, но коробки остались, устанавливаем первую
            shipment.current_box_index = 0
            
        # Сбрасываем кэши в модели поставки при удалении пустых коробок
        shipment.invalidate_caches()

        # Также инвалидируем кэш родительской групповой поставки, если она есть
        parent_group = shipment.parent_group
        if parent_group:
            parent_group.invalidate_caches()

        # Update UI immediately for responsiveness, but delay database save
        # Обновляем интерфейс для немедленного отображения изменений
        if shipment == self.main_window.current_shipment:
            self.main_window.ui_updater.update_current_components()
        self.main_window.ui_updater.update_shipments_tree()
        self.main_window.statusBar().showMessage(f"Удалено {len(empty_box_indices)} пустых коробок", 3000)
        
        # Полное сохранение — нужно удалить пустые коробки из БД
        self.main_window.data_controller.save_shipment(shipment)

    def export_boxes(self):
        self.export_boxes_for_shipment(self.main_window.current_shipment)

    def export_boxes_for_shipment(self, shipment):
        if not shipment:
            QMessageBox.warning(self.main_window, "Ошибка", "Сначала выберите поставку!")
            return

        if not shipment.boxes:
            QMessageBox.warning(self.main_window, "Ошибка", "В поставке нет коробок для экспорта!")
            return

        shipment_name = shipment.destination_name

        parent_group = None
        for group_name, group_shipment in self.main_window.group_shipments.items():
            if shipment_name in group_shipment.sub_shipments:
                parent_group = group_name
                break

        if parent_group:
            safe_group_name = "".join(c for c in parent_group if c not in r'<>:"/\|?*')
            safe_shipment_name = "".join(c for c in shipment_name if c not in r'<>:"/\|?*')
            default_filename = f"{safe_group_name}_{safe_shipment_name}_коробки.xlsx"
        else:
            safe_shipment_name = "".join(c for c in shipment_name if c not in r'<>:"/\|?*')
            default_filename = f"{safe_shipment_name}_коробки.xlsx"

        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Экспорт коробок",
            default_filename,
            "Excel (*.xlsx)"
        )

        if not file_path:
            return

        self._export_boxes_to_file(shipment, file_path)

    def _export_boxes_to_file(self, shipment, file_path):
        try:
            box_ids = []
            if shipment.properties.box_ids:
                box_ids_text = shipment.properties.box_ids.strip()
                if box_ids_text:
                    box_ids = [id.strip() for id in box_ids_text.replace('\n', ',').split(',') if id.strip()]

            if not box_ids:
                for i in range(len(shipment.boxes)):
                    box_ids.append(f"Коробка-{i + 1}")

            def get_box_number(box_id):
                try:
                    if box_id.startswith("Коробка-"):
                        number_part = box_id.split("-")[1]
                        return int(''.join(filter(str.isdigit, number_part)))
                    elif box_id.startswith("Коробка "):
                        number_part = box_id.split(" ", 1)[1]
                        return int(''.join(filter(str.isdigit, number_part)))
                    return 0
                except (IndexError, ValueError):
                    return 0

            sorted_boxes = sorted(shipment.boxes, key=lambda box: get_box_number(box.box_id))

            data = []
            for i, box in enumerate(sorted_boxes):
                if i < len(box_ids):
                    box_id = box_ids[i]
                else:
                    box_id = f"Коробка-{i + 1}"

                for barcode, qty in box.items.items():
                    data.append({
                        'Баркод товара': barcode,
                        'Кол-во товаров': qty,
                        'ШК короба': box_id,
                        'Срок годности': ''
                    })

                data.append({
                    'Баркод товара': '',
                    'Кол-во товаров': '',
                    'ШК короба': '',
                    'Срок годности': ''
                })

            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False, columns=['Баркод товара', 'Кол-во товаров', 'ШК короба', 'Срок годности'])

            utils.play_sound(self.main_window.ok_sound, self.main_window.tone_sound)
            self.main_window.statusBar().showMessage(f"Коробки экспортированы в файл: {file_path}", 5000)

        except Exception as e:
            QMessageBox.critical(self.main_window, "Ошибка", f"Не удалось экспортировать коробки:\n{e}")

    def export_all_group_boxes(self, group_shipment):
        if not group_shipment or not group_shipment.sub_shipments:
            QMessageBox.warning(self.main_window, "Ошибка", "В групповой поставке нет подпоставок!")
            return

        folder = QFileDialog.getExistingDirectory(
            self.main_window,
            "Выберите папку для экспорта",
            ""
        )
        if not folder:
            return

        exported = 0
        for shipment in group_shipment.sub_shipments.values():
            if shipment.boxes:
                safe_group_name = "".join(c for c in group_shipment.group_name if c not in r'<>:"/\|?*')
                safe_shipment_name = "".join(c for c in shipment.destination_name if c not in r'<>:"/\|?*')
                filename = f"{safe_group_name}_{safe_shipment_name}_коробки.xlsx"
                file_path = str(Path(folder) / filename)
                self._export_boxes_to_file(shipment, file_path)
                exported += 1

        if exported > 0:
            self.main_window.statusBar().showMessage(f"Экспортировано {exported} файл(ов) в папку: {folder}", 5000)
        else:
            QMessageBox.warning(self.main_window, "Предупреждение", "Ни в одной подпоставке нет коробок для экспорта!")
    
    def import_boxes(self):
        """
        Импорт коробок из Excel файла в формате экспорта (асинхронно)
        """
        if not self.main_window.current_shipment:
            QMessageBox.warning(self.main_window, "Предупреждение", "Выберите поставку для импорта коробок!")
            return
        
        # Открываем диалог выбора файла (должен быть в главном потоке)
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Импорт коробок",
            "",
            "Excel (*.xlsx *.xls)"
        )
        
        if not file_path:
            return
        
        # Проверяем, что в поставке есть товары
        if not self.main_window.current_shipment.shipment_items:
            QMessageBox.critical(self.main_window, "Ошибка", 
                "В текущей поставке нет товаров. Сначала добавьте товары в поставку.")
            return
        
        self.main_window.show_progress("Импорт коробок...")
        
        # Запускаем асинхронную обработку файла
        self.main_window.async_manager.execute_async(
            self._import_boxes_process_file,
            callback=self._on_import_boxes_finished,
            error_callback=self._on_import_boxes_error,
            file_path=file_path
        )

    def _import_boxes_process_file(self, file_path):
        """Обрабатывает файл импорта в фоновом потоке"""
        df = pd.read_excel(file_path)
        
        required_columns = ['Баркод товара', 'Кол-во товаров', 'ШК короба']
        if not all(col in df.columns for col in required_columns):
            missing_cols = [col for col in required_columns if col not in df.columns]
            return {'success': False, 'error': f"Файл не содержит необходимые столбцы: {', '.join(missing_cols)}"}
        
        # Группируем данные по коробкам
        boxes_data = {}
        current_box_id = None
        skipped_barcodes = []
        shipment_items = dict(self.main_window.current_shipment.shipment_items)
        
        for _, row in df.iterrows():
            barcode_raw = row['Баркод товара']
            if pd.notna(barcode_raw):
                barcode = str(int(barcode_raw)) if isinstance(barcode_raw, (int, float)) else str(barcode_raw).strip()
            else:
                barcode = ''
            
            qty = row['Кол-во товаров']
            box_id = str(row['ШК короба']).strip() if pd.notna(row['ШК короба']) else ''
            
            if not barcode and not box_id:
                continue
            
            if box_id and box_id != current_box_id:
                current_box_id = box_id
                if current_box_id not in boxes_data:
                    boxes_data[current_box_id] = {}
            
            if barcode and current_box_id and pd.notna(qty):
                if barcode not in shipment_items:
                    skipped_barcodes.append(barcode)
                    continue
                    
                try:
                    qty_int = int(float(qty))
                    if qty_int > 0:
                        sku = shipment_items[barcode].sku
                        boxes_data[current_box_id][barcode] = {'qty': qty_int, 'sku': sku}
                except (ValueError, TypeError):
                    continue
        
        return {
            'success': True,
            'boxes_data': boxes_data,
            'skipped_barcodes': skipped_barcodes,
            'total_items': sum(len(items) for items in boxes_data.values()),
        }

    def _on_import_boxes_finished(self, result):
        """Обработка успешного импорта коробок"""
        if not result['success']:
            self.main_window.hide_progress("Ошибка импорта", 3000)
            QMessageBox.critical(self.main_window, "Ошибка", result['error'])
            return
        
        # Очищаем существующие коробки
        self.main_window.current_shipment.boxes.clear()
        
        # Создаем коробки
        for box_id, items in result['boxes_data'].items():
            if items:
                box = Box(box_id)
                box.items = {barcode: item_data['qty'] for barcode, item_data in items.items()}
                self.main_window.current_shipment.boxes.append(box)
        
        # Обновляем распределение товаров
        self.main_window.current_shipment.recalculate_allocated_qty_from_boxes()
        self.main_window.current_shipment.invalidate_caches()
        
        # Сохраняем изменения
        self.save_shipment(self.main_window.current_shipment)
        
        # Воспроизводим звук
        utils.play_sound(self.main_window.ok_sound, self.main_window.tone_sound)
        
        # Обновляем интерфейс
        self.main_window.ui_updater.update_ui()
        
        if (hasattr(self.main_window.current_shipment, 'parent_group') and
            self.main_window.current_shipment.parent_group):
            self.main_window.ui_updater.update_shipments_tree()
        
        # Формируем сообщение
        message = f"Успешно импортировано {len(result['boxes_data'])} коробок с {result['total_items']} товарами!"
        if result['skipped_barcodes']:
            unique_skipped = list(set(result['skipped_barcodes']))[:5]
            message += f"\n\nПропущено штрихкодов, не найденных в поставке: {len(unique_skipped)}"
            if unique_skipped:
                message += f"\nПримеры: {', '.join(unique_skipped)}"
            if len(result['skipped_barcodes']) > 5:
                message += f"\n... и ещё {len(result['skipped_barcodes']) - 5} штрихкодов"
        
        self.main_window.hide_progress(message.split('\n')[0], 3000)
        QMessageBox.information(self.main_window, "Успех", message)

    def _on_import_boxes_error(self, error_msg):
        """Обработка ошибки импорта коробок"""
        self.logger.error(f"Ошибка импорта коробок: {error_msg}")
        self.main_window.hide_progress("Ошибка импорта", 3000)
        QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка импорта коробок:\n{error_msg}")
