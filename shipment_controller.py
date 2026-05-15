"""
Модуль для управления логикой поставок в приложении WB Packer
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main_window import MainWindow

logger = logging.getLogger(__name__)

class ShipmentController:
    """
    Контроллер для управления логикой поставок
    """
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        logger.info("Инициализация ShipmentController")

    def handle_shipment_operations(self):
        """
        Обработка операций с поставками
        """
        # Проверяем, не выполняется ли уже операция с поставками (используем единый флаг)
        if hasattr(self.main_window.shipment_operations, '_creating_shipment_in_progress') and \
           self.main_window.shipment_operations._creating_shipment_in_progress:
            return  # Операция уже выполняется, выходим
        
        try:
            # Логика обработки операций с поставками
            self.main_window.shipment_operations.start_new_shipment()
        except Exception as e:
            logger.error(f"Ошибка при обработке операций с поставками: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при обработке поставок:\n{e}")

    def handle_group_shipment_operations(self):
        """
        Обработка операций с групповыми поставками
        """
        # Проверяем, не выполняется ли уже операция с поставками (используем единый флаг)
        if hasattr(self.main_window.shipment_operations, '_creating_shipment_in_progress') and \
           self.main_window.shipment_operations._creating_shipment_in_progress:
            return  # Операция уже выполняется, выходим
        
        try:
            # Логика обработки операций с групповыми поставками
            self.main_window.shipment_operations.start_new_shipment()
        except Exception as e:
            logger.error(f"Ошибка при обработке операций с групповыми поставками: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при обработке групповых поставок:\n{e}")

    def handle_shipment_properties(self, shipment_name: str):
        """
        Обработка свойств поставки
        """
        try:
            self.main_window.shipment_manager.show_shipment_properties(shipment_name)
        except Exception as e:
            logger.error(f"Ошибка при отображении свойств поставки {shipment_name}: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при отображении свойств поставки:\n{e}")

    def handle_shipment_context_menu(self, position):
        """
        Обработка контекстного меню поставки
        """
        try:
            self.main_window.shipment_manager.show_shipment_context_menu(position)
        except Exception as e:
            logger.error(f"Ошибка при отображении контекстного меню поставки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при отображении контекстного меню:\n{e}")

    def handle_box_context_menu(self, position):
        """
        Обработка контекстного меню коробки
        """
        try:
            self.main_window.shipment_manager.show_box_table_context_menu(position)
        except Exception as e:
            logger.error(f"Ошибка при отображении контекстного меню коробки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при отображении контекстного меню коробки:\n{e}")

    def handle_shipment_double_click(self, item):
        """
        Обработка двойного клика по поставке
        """
        try:
            self.main_window.on_shipment_double_clicked(item)
        except Exception as e:
            logger.error(f"Ошибка при обработке двойного клика поставке: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при обработке двойного клика:\n{e}")

    def handle_shipment_cell_change(self, row, column):
        """
        Обработка изменения ячейки в таблице поставки
        """
        try:
            self.main_window.shipment_manager.on_shipment_cell_changed(row, column)
        except Exception as e:
            logger.error(f"Ошибка при обработке изменения ячейки поставки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при обработке изменения ячейки:\n{e}")

    def handle_box_cell_change(self, row, column):
        """
        Обработка изменения ячейки в таблице коробки
        """
        try:
            self.main_window.shipment_manager.on_box_cell_changed(row, column)
        except Exception as e:
            logger.error(f"Ошибка при обработке изменения ячейки коробки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при обработке изменения ячейки коробки:\n{e}")

    def handle_new_box(self):
        """
        Обработка создания новой коробки
        """
        try:
            self.main_window.shipment_manager.new_box()
        except Exception as e:
            logger.error(f"Ошибка при создании новой коробки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при создании новой коробки:\n{e}")

    def handle_shipment_update(self):
        """
        Обработка обновления состава поставки
        """
        try:
            self.main_window.shipment_operations.update_shipment_composition()
        except Exception as e:
            logger.error(f"Ошибка при обновлении состава поставки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при обновлении состава поставки:\n{e}")

    def handle_group_shipment_update(self, group_shipment):
        """
        Обработка обновления состава групповой поставки
        """
        try:
            self.main_window.shipment_operations.update_group_shipment_composition(group_shipment)
        except Exception as e:
            logger.error(f"Ошибка при обработке обновления групповой поставки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при обновлении групповой поставки:\n{e}")

    def handle_shipment_rename(self, old_name: str):
        """
        Обработка переименования поставки
        """
        try:
            self.main_window.shipment_operations.rename_shipment(old_name)
        except Exception as e:
            logger.error(f"Ошибка при переименовании поставки {old_name}: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при переименовании поставки:\n{e}")

    def handle_group_shipment_rename(self, old_name: str):
        """
        Обработка переименования групповой поставки
        """
        try:
            self.main_window.shipment_operations.rename_group_shipment(old_name)
        except Exception as e:
            logger.error(f"Ошибка при переименовании групповой поставки {old_name}: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при переименовании групповой поставки:\n{e}")

    def handle_shipment_delete(self, shipment_name: str):
        """
        Обработка удаления поставки
        """
        try:
            self.main_window.shipment_operations.delete_shipment(shipment_name)
        except Exception as e:
            logger.error(f"Ошибка при удалении поставки {shipment_name}: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при удалении поставки:\n{e}")

    def handle_group_shipment_delete(self, group_name: str):
        """
        Обработка удаления групповой поставки
        """
        try:
            self.main_window.shipment_operations.delete_group_shipment(group_name)
        except Exception as e:
            logger.error(f"Ошибка при удалении групповой поставки {group_name}: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при удалении групповой поставки:\n{e}")

    def handle_box_delete(self, index: int):
        """
        Обработка удаления коробки
        """
        try:
            self.main_window.shipment_manager.delete_box(index)
        except Exception as e:
            logger.error(f"Ошибка при удалении коробки с индексом {index}: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при удалении коробки:\n{e}")

    def handle_box_rename(self, index: int):
        """
        Обработка переименования коробки
        """
        try:
            self.main_window.shipment_manager.rename_box(index)
        except Exception as e:
            logger.error(f"Ошибка при переименовании коробки с индексом {index}: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при переименовании коробки:\n{e}")

    def handle_item_remove_from_box(self, barcode: str):
        """
        Обработка удаления товара из коробки
        """
        try:
            self.main_window.shipment_manager.remove_item_from_box(barcode)
        except Exception as e:
            logger.error(f"Ошибка при удалении товара {barcode} из коробки: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при удалении товара из коробки:\n{e}")

    def handle_boxes_export(self):
        """
        Обработка экспорта коробок
        """
        try:
            self.main_window.shipment_manager.export_boxes()
        except Exception as e:
            logger.error(f"Ошибка при экспорте коробок: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при экспорте коробок:\n{e}")

    def handle_shipment_archive(self, shipment_name: str):
        """
        Обработка архивации поставки
        """
        try:
            self.main_window.archive_shipment(shipment_name)
        except Exception as e:
            logger.error(f"Ошибка при архивации поставки {shipment_name}: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при архивации поставки:\n{e}")

    def handle_group_shipment_archive(self, group_name: str):
        """
        Обработка архивации групповой поставки
        """
        try:
            self.main_window.archive_group_shipment(group_name)
        except Exception as e:
            logger.error(f"Ошибка при архивации групповой поставки {group_name}: {e}", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self.main_window, "Ошибка", f"Ошибка при архивации групповой поставки:\n{e}")