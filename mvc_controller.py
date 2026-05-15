"""
Контроллер для архитектуры MVC в приложении WB Packer
"""
import logging
from typing import TYPE_CHECKING, Dict, Any, List, Optional

if TYPE_CHECKING:
    from main_window import MainWindow

logger = logging.getLogger(__name__)

class Model:
    """
    Базовый класс для модели данных
    """
    def __init__(self):
        self.observers = []
        self.data = {}

    def add_observer(self, observer):
        """Добавить наблюдателя за изменениями модели"""
        if observer not in self.observers:
            self.observers.append(observer)

    def remove_observer(self, observer):
        """Удалить наблюдателя за изменениями модели"""
        if observer in self.observers:
            self.observers.remove(observer)

    def notify_observers(self):
        """Уведомить всех наблюдателей об изменениях"""
        for observer in self.observers:
            observer.update(self)

    def update_data(self, data: Dict[str, Any]):
        """Обновить данные модели"""
        self.data.update(data)
        self.notify_observers()


class View:
    """
    Базовый класс для представления (UI)
    """
    def __init__(self, controller):
        self.controller = controller

    def update(self, model: Model):
        """Обновить представление на основе модели"""
        raise NotImplementedError("Метод update должен быть реализован в подклассе")

    def bind_events(self):
        """Привязать события UI к контроллеру"""
        raise NotImplementedError("Метод bind_events должен быть реализован в подклассе")


class Controller:
    """
    Базовый класс для контроллера
    """
    def __init__(self, model: Model, view: View):
        self.model = model
        self.view = view
        self.model.add_observer(self.view)


class ShipmentModel(Model):
    """
    Модель данных для поставок
    """
    def __init__(self):
        super().__init__()
        self.shipments = {}
        self.group_shipments = {}
        self.current_shipment = None

    def load_shipments(self, shipment_data: Dict[str, Any]):
        """Загрузить данные поставок"""
        self.shipments = shipment_data.get('shipments', {})
        self.group_shipments = shipment_data.get('group_shipments', {})
        self.notify_observers()

    def add_shipment(self, shipment):
        """Добавить поставку"""
        self.shipments[shipment.destination_name] = shipment
        self.notify_observers()

    def remove_shipment(self, shipment_name: str):
        """Удалить поставку"""
        if shipment_name in self.shipments:
            del self.shipments[shipment_name]
            if self.current_shipment and self.current_shipment.destination_name == shipment_name:
                self.current_shipment = None
            self.notify_observers()

    def set_current_shipment(self, shipment):
        """Установить текущую поставку"""
        self.current_shipment = shipment
        self.notify_observers()


class ShipmentView(View):
    """
    Представление для работы с поставками
    """
    def __init__(self, main_window: 'MainWindow'):
        super().__init__(None)  # Контроллер будет установлен позже
        self.main_window = main_window

    def update(self, model: 'ShipmentModel'):
        """Обновить UI на основе модели поставок"""
        try:
            # Обновляем списки поставок
            self.main_window.shipments = model.shipments
            self.main_window.group_shipments = model.group_shipments
            self.main_window.current_shipment = model.current_shipment
            
            # Обновляем интерфейс
            if not self.main_window.updating_ui:
                self.main_window.update_ui()
        except Exception as e:
            logger.error(f"Ошибка при обновлении представления поставок: {e}", exc_info=True)

    def bind_events(self):
        """Привязать события UI к контроллеру"""
        # Проверяем, не привязаны ли уже события (избегаем дублирования)
        if hasattr(self, '_events_bound') and self._events_bound:
            return
        
        # Привязываем действия к контроллеру
        self.main_window.new_shipment_btn.clicked.connect(self.controller.handle_new_shipment)
        self.main_window.new_box_btn.clicked.connect(self.controller.handle_new_box)
        self.main_window.shipment_check_btn.clicked.connect(self.controller.handle_shipment_check)
        self.main_window.print_labels_btn.clicked.connect(self.controller.handle_print_label)
        # moysklad_sync_btn и check_stock_btn подключены напрямую в main_window.py

        # Подключаем шорткаты
        from PyQt6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence("F1"), self.main_window).activated.connect(self.controller.handle_new_shipment)
        QShortcut(QKeySequence("F3"), self.main_window).activated.connect(self.controller.handle_new_box)
        QShortcut(QKeySequence("F11"), self.main_window).activated.connect(self.controller.handle_theme_shortcut)
        QShortcut(QKeySequence("Ctrl+S"), self.main_window).activated.connect(self.controller.handle_save_session)
        QShortcut(QKeySequence("Ctrl+H"), self.main_window).activated.connect(self.controller.handle_shipment_check)
        QShortcut(QKeySequence("Ctrl+P"), self.main_window).activated.connect(self.controller.handle_print_label)
        
        # Помечаем, что события привязаны
        self._events_bound = True


class ShipmentController(Controller):
    """
    Контроллер для управления поставками
    """
    def __init__(self, model: ShipmentModel, view: ShipmentView, main_window: 'MainWindow'):
        self.main_window = main_window
        super().__init__(model, view)
        
    def handle_new_shipment(self):
        """Обработка создания новой поставки (обычной или групповой)"""
        # Проверяем, не выполняется ли уже операция создания поставки
        if hasattr(self.main_window.shipment_operations, '_creating_shipment_in_progress') and \
           self.main_window.shipment_operations._creating_shipment_in_progress:
            return  # Операция уже выполняется, выходим
        
        try:
            # Выполняем операцию создания поставки асинхронно, чтобы избежать блокировки UI
            from PyQt6.QtCore import QTimer
            # Используем универсальный метод, который сам определит тип поставки
            QTimer.singleShot(0, lambda: self.main_window.shipment_operations.start_new_shipment())
        except Exception as e:
            logger.error(f"Ошибка при создании новой поставки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при создании поставки:\n{e}")

    def handle_new_box(self):
        """Обработка создания новой коробки"""
        try:
            if self.main_window.current_shipment:
                self.main_window.shipment_manager.new_box()
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self.main_window, "Ошибка", "Сначала выберите поставку!")
        except Exception as e:
            logger.error(f"Ошибка при создании новой коробки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при создании коробки:\n{e}")

    def handle_export_boxes(self):
        """Обработка экспорта коробок"""
        try:
            if self.main_window.current_shipment:
                self.main_window.shipment_manager.export_boxes()
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self.main_window, "Ошибка", "Сначала выберите поставку!")
        except Exception as e:
            logger.error(f"Ошибка при экспорте коробок: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при экспорте коробок:\n{e}")

    def handle_print_label(self):
        """Обработка печати этикетки"""
        try:
            self.main_window.open_label_print_dialog()
        except Exception as e:
            logger.error(f"Ошибка при открытии диалога печати этикеток: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при открытии диалога печати этикеток:\n{e}")

    def handle_print_product_label(self):
        """Обработка печати этикетки на товар"""
        try:
            self.main_window.open_label_print_dialog()
        except Exception as e:
            logger.error(f"Ошибка при открытии диалога печати этикетки на товар: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при открытии диалога печати этикетки на товар:\n{e}")

    def handle_print_box_label(self):
        """Обработка печати этикетки на коробку"""
        try:
            self.main_window.open_label_print_dialog()
        except Exception as e:
            logger.error(f"Ошибка при открытии диалога печати этикетки на коробку: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при открытии диалога печати этикетки на коробку:\n{e}")

    def handle_packing_list(self):
        """Обработка создания листа на паллет"""
        try:
            self.main_window.generate_packing_list()
        except Exception as e:
            logger.error(f"Ошибка при создании листа на паллет: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при создании листа на паллет:\n{e}")

    def handle_shipment_check(self):
        """Обработка проверки поставки"""
        try:
            self.main_window.start_shipment_check()
        except Exception as e:
            logger.error(f"Ошибка при проверке поставки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при проверке поставки:\n{e}")

    def handle_refresh(self):
        """Обработка обновления данных"""
        try:
            logger.info("Начало обработки обновления данных через MVC контроллер")
            # Загружаем данные через основной метод
            self.main_window.load_all_data()
            # Обновляем модель с новыми данными
            shipment_data = {
                'shipments': self.main_window.shipments,
                'group_shipments': self.main_window.group_shipments
            }
            self.model.load_shipments(shipment_data)
            logger.info("Завершение обработки обновления данных через MVC контроллер")
            
            # Обновляем сессию пользователя для текущей поставки
            if (hasattr(self.main_window, 'current_shipment') and
                self.main_window.current_shipment and
                hasattr(self.main_window, 'current_user') and
                self.main_window.current_user):
                from database import update_user_session
                update_user_session(self.main_window.current_shipment.destination_name, self.main_window.current_user)
            
            # Принудительно обновляем интерфейс для гарантии отображения изменений
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()
        except Exception as e:
            logger.error(f"Ошибка при обновлении данных: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при обновлении данных:\n{e}")
    
    def handle_theme_shortcut(self):
        """Обработка сочетания клавиш для темы"""
        try:
            self.main_window.toggle_theme_shortcut()
        except Exception as e:
            logger.error(f"Ошибка при переключении темы через сочетание клавиш: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при переключении темы:\n{e}")
    
    def handle_save_session(self):
        """Обработка сохранения сессии"""
        try:
            self.main_window.save_session()
        except Exception as e:
            logger.error(f"Ошибка при сохранении сессии: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при сохранении сессии:\n{e}")


class MainController:
    """
    Главный контроллер приложения
    """
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)
        self.logger.info("Инициализация MainController")
        
        # Создаем модель, представление и контроллер для поставок
        self.shipment_model = ShipmentModel()
        self.shipment_view = ShipmentView(main_window)
        self.shipment_controller = ShipmentController(self.shipment_model, self.shipment_view, main_window)
        
        # Устанавливаем контроллер для представления
        self.shipment_view.controller = self.shipment_controller
        
        logger.info("MainController инициализирован успешно")
    
    def bind_events(self):
        """Привязать события UI к контроллеру"""
        self.shipment_view.bind_events()
        logger.info("События UI привязаны контроллеру")

    def update_shipments(self, shipments_data: Dict[str, Any]):
        """Обновить данные поставок через модель"""
        self.shipment_model.load_shipments(shipments_data)

    def add_shipment(self, shipment):
        """Добавить поставку через модель"""
        self.shipment_model.add_shipment(shipment)

    def remove_shipment(self, shipment_name: str):
        """Удалить поставку через модель"""
        self.shipment_model.remove_shipment(shipment_name)

    def set_current_shipment(self, shipment):
        """Установить текущую поставку через модель"""
        self.shipment_model.set_current_shipment(shipment)