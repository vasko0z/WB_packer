"""
Виджет для отображения информации о текущих поставках с прогрессом выполнения
"""
import json
import time
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QProgressBar, QFrame, QMenu, QSplitter, QSystemTrayIcon
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject, QCoreApplication
from PyQt6.QtGui import QFont, QPalette, QColor, QAction, QIcon
import database
from models import Shipment, GroupShipment
from async_worker import AsyncWorker

# Initialize database when running standalone
try:
    database.init_db()
except Exception as e:
    print(f"Database initialization issue: {e}")
    pass  # Continue anyway since this might be intentional for standalone mode


class ShipmentDataLoader(QObject):
    """
    Асинхронный загрузчик данных о поставках
    """
    data_loaded = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def load_shipments_data(self):
        """
        Загрузка данных о поставках из базы данных
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
                        from models import ShipmentProperties
                        shipment.properties = ShipmentProperties.from_dict(properties_data)
                    except json.JSONDecodeError:
                        from models import ShipmentProperties
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
                
                if parent_group:
                    if parent_group not in group_shipments:
                        group_shipments[parent_group] = GroupShipment(
                            parent_group, font_size, label_font_size, theme
                        )
                    group_shipments[parent_group].add_sub_shipment(destination_name, shipment)
                else:
                    shipments[destination_name] = shipment
            
            result = {
                'shipments': shipments,
                'group_shipments': group_shipments
            }
            
            self.data_loaded.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ShipmentTrackingWidget(QWidget):
    """
    Виджет для отображения информации о текущих поставках с прогрессом выполнения
    """
    shipment_selected = pyqtSignal(str)  # Сигнал выбора поставки

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Отслеживание поставок")
        self.setWindowFlags(Qt.WindowType.Tool)  # Окно без кнопок управления
        
        # Асинхронный загрузчик данных
        self.async_loader = AsyncWorker()
        self.data_loader = ShipmentDataLoader()
        self.data_loader.data_loaded.connect(self._on_data_loaded)
        self.data_loader.error_occurred.connect(self._on_error)
        
        # Таймер для обновления данных
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        
        # Инициализация UI
        self.init_ui()
        
        # Прежде чем загружать данные, попытаемся автоматически обнаружить PostgreSQL сервер
        # в локальной сети. Это позволит работать без фиксированного IP-адреса хоста БД.
        self._ensure_db_host()
        
        # Загружаем начальные данные
        self.load_data()
        
        # Запускаем таймер обновления (каждые 30 секунд)
        self.start_auto_refresh(30000)  # 30 секунд в миллисекундах
        
        # Инициализация системного трея
        self.init_system_tray()
        
        # Показываем виджет
        self.show()

    def _ensure_db_host(self):
        """Попытка найти PostgreSQL сервер в локальной сети и обновить настройки подключения.

        Выполняется повторно с паузой до 5 попыток. При успешном обнаружении обновляется
        POSTGRESQL_HOST в конфигурации и сбрасывается пул соединений, чтобы приложение
        могло заново установить соединение на найденный хост.
        """
        try:
            from db_discovery import PostgreSQLDiscovery
            import config as _config
            max_attempts = 5
            discovery = PostgreSQLDiscovery(
                port=_config.POSTGRESQL_PORT,
                database=_config.POSTGRESQL_DATABASE,
                user=_config.POSTGRESQL_USER,
                password=_config.POSTGRESQL_PASSWORD,
            )
            for _ in range(max_attempts):
                host = discovery.discover()
                if host:
                    try:
                        if discovery.test_connection(host):
                            _config.POSTGRESQL_HOST = host
                            # Reset pool so новый хост будет использован
                            try:
                                import db_connection as _dbc
                                _dbc.db_connection.close_all_connections()
                                _dbc.db_connection.connection_pool = None
                            except Exception:
                                pass
                            # Попытка записать в кэш простым способом
                            try:
                                import database as _db
                                # Проверяем, что модуль полностью инициализирован
                                if (hasattr(_db, 'set_cached_postgresql_host') and 
                                    callable(getattr(_db, 'set_cached_postgresql_host', None))):
                                    _db.set_cached_postgresql_host(host)
                            except AttributeError:
                                # Модуль database еще не полностью инициализирован
                                print("Модуль database еще не полностью инициализирован, пропускаем кэшированный адрес")
                                pass
                            except Exception as e:
                                # Логируем другие ошибки, но не останавливаем выполнение
                                print(f"Ошибка при сохранении кэшированного адреса: {e}")
                                pass
                            return
                    except Exception:
                        pass
                time.sleep(0.5)
        except Exception:
            pass

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Список поставок
        self.shipments_list = QListWidget()
        self.shipments_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.shipments_list.customContextMenuRequested.connect(self.show_context_menu)
        self.shipments_list.itemClicked.connect(self.on_shipment_selected)
        self.shipments_list.setSizeAdjustPolicy(QListWidget.SizeAdjustPolicy.AdjustToContents)
        self.shipments_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.shipments_list, 1)  # Добавляем растяжение по вертикали
        
        # Устанавливаем размеры окна
        self.resize(500, 400)  # Устанавливаем начальный размер
        
        # Убираем рамку у списка
        self.shipments_list.setFrameShape(QFrame.Shape.NoFrame)

    def load_data(self):
        """Загрузка данных о поставках асинхронно"""
        if not self.async_loader.is_running():
            self.async_loader.execute(
                self.data_loader.load_shipments_data,
                error_callback=self._on_error
            )

    def _on_data_loaded(self, data):
        """Обработка загруженных данных"""
        shipments = data.get('shipments', {})
        group_shipments = data.get('group_shipments', {})
        
        # Очищаем текущий список
        self.shipments_list.clear()
        
        # Добавляем обычные поставки
        for shipment in shipments.values():
            self._add_shipment_to_list(shipment)
        
        # Добавляем групповые поставки
        for group_shipment in group_shipments.values():
            # Добавляем саму группу
            self._add_group_shipment_to_list(group_shipment)
            
            # Добавляем подпоставки внутри группы с отступом
            for sub_shipment in group_shipment.sub_shipments.values():
                self._add_shipment_to_list(sub_shipment, is_sub_shipment=True)

    def _add_shipment_to_list(self, shipment, is_sub_shipment=False):
        """Добавление поставки в список"""
        # Создаем виджет элемента
        item_widget = ShipmentItemWidget(shipment, is_sub_shipment=is_sub_shipment)
        
        # Создаем элемент списка
        list_item = QListWidgetItem()
        list_item.setSizeHint(item_widget.sizeHint())
        
        # Добавляем в список
        self.shipments_list.addItem(list_item)
        self.shipments_list.setItemWidget(list_item, item_widget)
        
        # Сохраняем имя поставки в элементе
        list_item.setData(Qt.ItemDataRole.UserRole, shipment.destination_name)

    def _add_group_shipment_to_list(self, group_shipment):
        """Добавление групповой поставки в список"""
        # Создаем виджет элемента для групповой поставки
        item_widget = GroupShipmentItemWidget(group_shipment)
        
        # Создаем элемент списка
        list_item = QListWidgetItem()
        list_item.setSizeHint(item_widget.sizeHint())
        
        # Добавляем в список
        self.shipments_list.addItem(list_item)
        self.shipments_list.setItemWidget(list_item, item_widget)
        
        # Сохраняем имя группы в элементе
        list_item.setData(Qt.ItemDataRole.UserRole, group_shipment.group_name)

    def _on_error(self, error_msg):
        """Обработка ошибки загрузки данных"""
        print(f"Ошибка загрузки данных: {error_msg}")

    def on_shipment_selected(self, item):
        """Обработка выбора поставки"""
        shipment_name = item.data(Qt.ItemDataRole.UserRole)
        if shipment_name:
            self.shipment_selected.emit(shipment_name)

    def show_context_menu(self, position):
        """Показ контекстного меню"""
        item = self.shipments_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        
        refresh_action = QAction("Обновить", self)
        refresh_action.triggered.connect(self.refresh_data)
        menu.addAction(refresh_action)
        
        menu.exec(self.shipments_list.mapToGlobal(position))

    def refresh_data(self):
        """Обновление данных"""
        self.load_data()

    def start_auto_refresh(self, interval_ms):
        """Запуск автоматического обновления данных"""
        self.refresh_timer.start(interval_ms)

    def stop_auto_refresh(self):
        """Остановка автоматического обновления данных"""
        self.refresh_timer.stop()

    def init_system_tray(self):
        """Инициализация системного трея"""
        # Создаем значок в системном трее
        self.tray_icon = QSystemTrayIcon(self)
        
        # Пытаемся получить стандартный значок приложения
        icon = QIcon.fromTheme("application-x-executable")
        if icon.isNull():
            # Если стандартный значок не найден, используем значок по умолчанию
            import sys
            from pathlib import Path
            import config
            icon_path = str(config.get_resource_path(Path("Res") / "icon.png"))
            if Path(icon_path).exists():
                icon = QIcon(icon_path)
            else:
                # Если файла иконки нет, используем стандартный значок
                icon = self.style().standardIcon(17)  # 17 - это QStyle.SP_ComputerIcon
        
        self.tray_icon.setIcon(icon)
        
        # Создаем контекстное меню для трея
        tray_menu = QMenu()
        
        # Действие для развертывания
        show_action = QAction("Показать", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        # Действие для сворачивания
        hide_action = QAction("Скрыть", self)
        hide_action.triggered.connect(self.hide)
        tray_menu.addAction(hide_action)
        
        # Действие для выхода
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(QCoreApplication.quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        
        # Показываем значок в трее
        self.tray_icon.show()
        
    def on_tray_icon_activated(self, reason):
        """Обработка клика по значку в трее"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # При двойном клике показываем/скрываем окно
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()
            
    def toggle_minimize(self, event):
        """Переключение между свернутым и развернутым состоянием - заглушка для удаления"""
        pass
            
    def closeEvent(self, event):
        """Обработка закрытия виджета"""
        # Скрываем окно вместо закрытия
        self.hide()
        
        # Показываем уведомление в трее
        if hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage("Отслеживание поставок", "Приложение свернуто в трей", QSystemTrayIcon.MessageIcon.Information, 2000)
        
        # Принимаем событие закрытия
        event.accept()


class ShipmentItemWidget(QWidget):
    """
    Виджет элемента списка для отображения информации о поставке
    """
    def __init__(self, shipment, parent=None, is_sub_shipment=False):
        super().__init__(parent)
        self.shipment = shipment
        self.is_sub_shipment = is_sub_shipment
        self.init_ui()

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Добавляем отступ для подпоставок
        if self.is_sub_shipment:
            # Используем изображение паллеты как отступ
            from pathlib import Path
            import config
            pallet_icon_path = str(config.get_resource_path(Path("Res") / "pallet.png"))
            if Path(pallet_icon_path).exists():
                from PyQt6.QtGui import QPixmap
                pallet_icon = QLabel()
                pixmap = QPixmap(pallet_icon_path)
                if not pixmap.isNull():
                    # Масштабируем изображение до нужного размера
                    scaled_pixmap = pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    pallet_icon.setPixmap(scaled_pixmap)
                else:
                    # Если изображение не загрузилось, используем текстовый отступ
                    pallet_icon = QLabel("    ")
            else:
                # Если файла нет, используем текстовый отступ
                pallet_icon = QLabel("    ")
            layout.addWidget(pallet_icon)
        
        # Информация о поставке
        info_layout = QVBoxLayout()
        
        # Название поставки
        self.name_label = QLabel(self.shipment.destination_name)
        self.name_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        
        info_layout.addWidget(self.name_label)
        
        # Прогресс выполнения
        progress_layout = QHBoxLayout()
        
        # Текст прогресса
        self.progress_text_label = QLabel()
        progress_layout.addWidget(self.progress_text_label)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(15)
        progress_layout.addWidget(self.progress_bar, 1)
        
        info_layout.addLayout(progress_layout)
        
        layout.addLayout(info_layout, 1)
        
        # Обновляем отображение
        self.update_display()

    def update_display(self):
        """Обновление отображения информации о поставке"""
        # Вычисляем прогресс
        allocated, total = self.shipment.get_progress_info()
        remaining = total - allocated
        progress_percent = (allocated / total * 100) if total > 0 else 0

        # Обновляем текст прогресса - показываем только оставшееся количество
        self.progress_text_label.setText(f"{remaining}")
        self.progress_text_label.setToolTip(f"Собрано: {allocated} из {total}")

        # Обновляем прогресс-бар
        self.progress_bar.setValue(int(progress_percent))

        # Обновляем стили в зависимости от темы
        self.apply_theme_styles()
        
        # Принудительно обновляем UI для немедленного отображения прогресса
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

    def apply_theme_styles(self):
        """Применение стилей в зависимости от темы"""
        # Получаем текущую тему из настроек
        from themes import THEMES
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        current_theme_name = app.property("current_theme") if app and app.property("current_theme") else "Тёмная"
        current_theme = THEMES.get(current_theme_name, THEMES.get("Тёмная", THEMES.get("Светлая")))
        
        # Применяем стили
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {current_theme["window_bg"].name()};
                color: {current_theme["window_text"].name()};
            }}
            QLabel {{
                background-color: transparent;
                color: {current_theme["window_text"].name()};
            }}
            QProgressBar {{
                border: none;
                border-radius: 4px;
                text-align: center;
                background-color: {current_theme["button_bg"].name()};
                color: {current_theme["button_text"].name()};
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 {current_theme["accent_success"].darker(120).name()},
                    stop: 1 {current_theme["accent_success"].name()});
                border-radius: 3px;
            }}
        """)


class GroupShipmentItemWidget(QWidget):
    """
    Виджет элемента списка для отображения информации о групповой поставке
    """
    def __init__(self, group_shipment, parent=None):
        super().__init__(parent)
        self.group_shipment = group_shipment
        self.init_ui()

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Информация о групповой поставке
        info_layout = QVBoxLayout()
        
        # Название группы
        self.name_label = QLabel(f"Группа: {self.group_shipment.group_name}")
        self.name_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        info_layout.addWidget(self.name_label)
        
        # Прогресс выполнения
        progress_layout = QHBoxLayout()
        
        # Текст прогресса
        self.progress_text_label = QLabel()
        progress_layout.addWidget(self.progress_text_label)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(15)
        progress_layout.addWidget(self.progress_bar, 1)
        
        info_layout.addLayout(progress_layout)
        
        layout.addLayout(info_layout, 1)
        
        # Обновляем отображение
        self.update_display()

    def update_display(self):
        """Обновление отображения информации о групповой поставке"""
        # Вычисляем прогресс
        allocated, total = self.group_shipment.get_progress_info()
        remaining = total - allocated
        progress_percent = (allocated / total * 100) if total > 0 else 0

        # Обновляем текст прогресса - показываем только оставшееся количество
        self.progress_text_label.setText(f"{remaining}")
        self.progress_text_label.setToolTip(f"Собрано: {allocated} из {total}")

        # Обновляем прогресс-бар
        self.progress_bar.setValue(int(progress_percent))

        # Обновляем стили в зависимости от темы
        self.apply_theme_styles()
        
        # Принудительно обновляем UI для немедленного отображения прогресса
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

    def apply_theme_styles(self):
        """Применение стилей в зависимости от темы"""
        # Получаем текущую тему из настроек
        from themes import THEMES
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        current_theme_name = app.property("current_theme") if app and app.property("current_theme") else "Тёмная"
        current_theme = THEMES.get(current_theme_name, THEMES.get("Тёмная", THEMES.get("Светлая")))
        
        # Применяем стили
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {current_theme["window_bg"].name()};
                color: {current_theme["window_text"].name()};
            }}
            QLabel {{
                background-color: transparent;
                color: {current_theme["window_text"].name()};
            }}
            QProgressBar {{
                border: none;
                border-radius: 4px;
                text-align: center;
                background-color: {current_theme["button_bg"].name()};
                color: {current_theme["button_text"].name()};
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 {current_theme["accent_warning"].darker(120).name()},
                    stop: 1 {current_theme["accent_warning"].name()});
                border-radius: 3px;
            }}
        """)


class DraggableShipmentTrackingWidget(ShipmentTrackingWidget):
    """
    Перетаскиваемый виджет отслеживания поставок
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self._drag_start_pos = None
        self._is_dragging = False
        
        # Устанавливаем флаги для возможности перетаскивания
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowSystemMenuHint)
        
        # Устанавливаем стиль для возможности перетаскивания
        self.setStyleSheet(self.styleSheet() + """
            QWidget {
                border: none;
                border-radius: 5px;
            }
        """)

    def mousePressEvent(self, event):
        """Обработка нажатия мыши для начала перетаскивания"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            self._is_dragging = True
            event.accept()

    def mouseMoveEvent(self, event):
        """Обработка движения мыши во время перетаскивания"""
        if self._is_dragging and self._drag_start_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(self.pos() + delta)
            self._drag_start_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseReleaseEvent(self, event):
        """Обработка отпускания мыши в конце перетаскивания"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self._drag_start_pos = None
            event.accept()
            
    def resizeEvent(self, event):
        """Обработка изменения размера виджета"""
        super().resizeEvent(event)
