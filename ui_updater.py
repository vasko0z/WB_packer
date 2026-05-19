# ui_updater.py
import logging
import time
import traceback
from PyQt6.QtWidgets import QTableWidgetItem, QPushButton, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QTreeWidgetItem, QTableWidget, QHeaderView, QLineEdit, QSpinBox, QApplication, QSizePolicy
from PyQt6.QtCore import Qt, QSize, QItemSelectionModel, QRegularExpression
from PyQt6.QtGui import QColor, QLinearGradient, QPalette, QPixmap, QIcon, QRegularExpressionValidator, QFont
import themes
import utils
import config
import database
from custom_table_widget import CustomTableWidget
from pathlib import Path

# Импорты констант и кэша
from app_constants import (
    TABLE_ROW_HEIGHT_MIN,
    TABLE_ROW_HEIGHT_PADDING,
    ACTION_COLUMN_WIDTH,
    ACTION_BUTTON_SIZE,
    QTY_INPUT_WIDTH,
    SHIPMENT_ITEM_HEIGHT_WITH_PROGRESS,
    SHIPMENT_ITEM_HEIGHT_NO_PROGRESS,
    BOX_ITEM_HEIGHT,
    TREE_ITEM_MARGIN_LEFT,
    TREE_ITEM_MARGIN_RIGHT,
    TREE_ITEM_MARGIN_TOP,
    TREE_ITEM_MARGIN_BOTTOM,
    BOX_ITEM_MARGIN_LEFT,
    BOX_ITEM_MARGIN_RIGHT,
    BOX_ITEM_MARGIN_TOP,
    BOX_ITEM_MARGIN_BOTTOM,
    TREE_ITEM_SPACING,
    BOX_ITEM_SPACING,
    ICON_SIZE_SMALL,
    ICON_SIZE_MEDIUM,
    ICON_SIZE_LARGE,
    COLOR_STOCK_POSITIVE,
    COLOR_STOCK_NEGATIVE,
)
from image_cache import get_cached_pixmap

# Попытаемся импортировать API МойСклад
try:
    from moysklad_api import MoyskladAPI
    MOYSKLAD_API_AVAILABLE = True
except ImportError:
    MOYSKLAD_API_AVAILABLE = False
    MoyskladAPI = None

logger = logging.getLogger(__name__)

class UIUpdater:
    def __init__(self, main_window):
        self.main_window = main_window
        self._allocated_qty_cache = {}  # Кэш для get_total_allocated_qty

    def _clear_allocated_qty_cache(self):
        """Очищает кэш собранных товаров"""
        self._allocated_qty_cache.clear()

    def get_total_allocated_qty(self, barcode: str) -> int:
        """
        Подсчитывает общее количество товара, уже собранного во всех активных поставках.
        Учитывает товары из всех коробок всех активных поставок.
        Использует кэширование для повышения производительности.
        """
        # Проверяем кэш
        if barcode in self._allocated_qty_cache:
            return self._allocated_qty_cache[barcode]

        total_allocated = 0

        # Проверяем все обычные поставки
        for shipment in self.main_window.shipments.values():
            for box in shipment.boxes:
                qty = box.items.get(barcode, 0)
                if qty > 0:
                    total_allocated += qty

        # Проверяем все групповые поставки и их под-поставки
        for group_name, group_shipment in self.main_window.group_shipments.items():
            for sub_name, sub_shipment in group_shipment.sub_shipments.items():
                for box in sub_shipment.boxes:
                    qty = box.items.get(barcode, 0)
                    if qty > 0:
                        total_allocated += qty
                        # debug_info.append(f"group/{group_name}/{sub_name}/{box.box_id}: {qty}")

        # Сохраняем в кэш
        self._allocated_qty_cache[barcode] = total_allocated

        return total_allocated

    def update_fonts(self):
        # Создаем новый шрифт с нужным размером вместо использования текущего шрифта окна
        font = QFont()
        font.setPointSize(self.main_window.font_size)

        # Устанавливаем шрифт приложения
        QApplication.instance().setFont(font)

        # Устанавливаем шрифт для дерева поставок
        self.main_window.shipments_tree_widget.setFont(font)
        # Обновляем шрифт для всех элементов дерева
        self._update_tree_widget_fonts()

        self.main_window.current_box_label.setFont(font)
        self.main_window.shipment_table.setFont(font)
        self.main_window.current_box_table.setFont(font)
        self.main_window.removed_items_label.setFont(font)
        self.main_window.removed_items_table.setFont(font)
        self.main_window.scan_input.setFont(font)
        self.main_window.menuBar().setFont(font)

        header_font = QFont()
        header_font.setPointSize(self.main_window.font_size)

        if hasattr(self.main_window, 'shipment_table') and self.main_window.shipment_table:
            self.main_window.shipment_table.horizontalHeader().setFont(header_font)
            self.main_window.shipment_table.verticalHeader().setFont(header_font)

        if hasattr(self.main_window, 'current_box_table') and self.main_window.current_box_table:
            self.main_window.current_box_table.horizontalHeader().setFont(header_font)
            self.main_window.current_box_table.verticalHeader().setFont(header_font)

        if hasattr(self.main_window, 'removed_items_table') and self.main_window.removed_items_table:
            self.main_window.removed_items_table.horizontalHeader().setFont(header_font)
            self.main_window.removed_items_table.verticalHeader().setFont(header_font)
    
    def _update_tree_widget_fonts(self):
        """Обновляет шрифты для всех элементов дерева поставок"""
        # Обновляем шрифт для всех элементов дерева
        # Проходим по всем элементам дерева и обновляем шрифт для их виджетов
        def update_item_font(item):
            widget = self.main_window.shipments_tree_widget.itemWidget(item, 0)
            if widget:
                # Обновляем шрифт для виджета элемента
                widget.setFont(self.main_window.font())
                # Обновляем шрифт для всех дочерних виджетов
                for child in widget.findChildren(QWidget):
                    child.setFont(self.main_window.font())
            
            # Рекурсивно обновляем шрифты для дочерних элементов
            for i in range(item.childCount()):
                child_item = item.child(i)
                update_item_font(child_item)
        
        # Обновляем шрифты для всех корневых элементов
        for i in range(self.main_window.shipments_tree_widget.topLevelItemCount()):
            item = self.main_window.shipments_tree_widget.topLevelItem(i)
            update_item_font(item)

    def update_ui(self):
        # Обновляем UI без проверки флага при явном вызове (например, при выборе поставки/коробки)
        # Устанавливаем флаг обновления, чтобы избежать рекурсивных вызовов
        if self.main_window.updating_ui:
            return  # Избегаем рекурсивных вызовов

        self.main_window.updating_ui = True
        try:
            # Очищаем кэш собранных товаров перед обновлением UI
            self._clear_allocated_qty_cache()
            # Обновляем дерево поставок
            self.update_shipments_tree()
            # Обновляем метку текущей коробки
            self.update_current_box_label()
            # Обновляем таблицу поставки
            self.update_shipment_table()
            # Обновляем таблицу текущей коробки
            self.update_current_box_table()
            # Обновляем таблицу удаленных товаров
            self.update_removed_items_table()
            # Обновляем стили кнопок
            self.update_buttons_style()
            # Проверяем статус завершения
            self.check_completion()

        except Exception as e:
            logger.error(f"Ошибка при обновлении UI: {e}", exc_info=True)
        finally:
            self.main_window.updating_ui = False
    
    def update_current_components(self, full_update=True):
        """Обновляет только текущие компоненты интерфейса - метку коробки, таблицу коробки и таблицу поставки"""
        if full_update:
            self._clear_allocated_qty_cache()

        self.update_current_box_label()
        if full_update:
            self.update_shipment_table()
        self.update_current_box_table()
        self.update_removed_items_table()

        self._refresh_action_buttons_styles()
        self.main_window._update_add_all_button_visibility()

        self._update_shipments_tree_progress()

    def _update_shipments_tree_progress(self):
        """Обновляет только прогресс в элементах дерева поставок без полной перестройки"""
        if not self.main_window.current_shipment:
            return
        
        # Обновляем прогресс для текущей поставки
        for i in range(self.main_window.shipments_tree_widget.topLevelItemCount()):
            top_item = self.main_window.shipments_tree_widget.topLevelItem(i)
            if not top_item:
                continue
            
            # Проверяем, это обычная поставка или групповая
            shipment = top_item.data(0, Qt.ItemDataRole.UserRole)
            group_shipment = top_item.data(0, Qt.ItemDataRole.UserRole + 2)
            
            if shipment and shipment == self.main_window.current_shipment:
                # Нашли текущую поставку - обновляем её виджет
                widget = self.main_window.shipments_tree_widget.itemWidget(top_item, 0)
                if widget:
                    self._update_progress_in_widget(widget, shipment)
                
                # Обновляем прогресс в дочерних элементах (коробках)
                for j in range(top_item.childCount()):
                    child_item = top_item.child(j)
                    box = child_item.data(0, Qt.ItemDataRole.UserRole + 1)
                    if box:
                        box_widget = self.main_window.shipments_tree_widget.itemWidget(child_item, 0)
                        if box_widget:
                            self._update_box_progress_in_widget(box_widget, box, shipment)
            
            elif group_shipment:
                # Это групповая поставка - ищем вложенные поставки
                for k in range(top_item.childCount()):
                    child_item = top_item.child(k)
                    sub_shipment = child_item.data(0, Qt.ItemDataRole.UserRole)
                    if sub_shipment and sub_shipment == self.main_window.current_shipment:
                        # Нашли текущую поставку в группе - обновляем её виджет
                        child_widget = self.main_window.shipments_tree_widget.itemWidget(child_item, 0)
                        if child_widget:
                            self._update_progress_in_widget(child_widget, sub_shipment)

                        # Обновляем прогресс в коробках
                        for m in range(child_item.childCount()):
                            box_item = child_item.child(m)
                            box = box_item.data(0, Qt.ItemDataRole.UserRole + 1)
                            if box:
                                box_widget = self.main_window.shipments_tree_widget.itemWidget(box_item, 0)
                                if box_widget:
                                    self._update_box_progress_in_widget(box_widget, box, sub_shipment)

                        # Обновляем также прогресс родительской групповой поставки
                        group_widget = self.main_window.shipments_tree_widget.itemWidget(top_item, 0)
                        if group_widget:
                            self._update_group_progress_in_widget(group_widget, group_shipment)

    def _update_progress_in_widget(self, widget, shipment):
        """Обновляет только прогресс в виджете поставки"""
        allocated, total = shipment.get_progress_info()
        remaining = total - allocated

        # Находим label с прогрессом по objectName
        progress_label = widget.findChild(QLabel, "shipment_progress_label")
        
        # Если не нашли по objectName, ищем по позиции (второй элемент в top_layout)
        if not progress_label:
            layout = widget.layout()
            if layout and isinstance(layout, QVBoxLayout):
                if layout.count() > 0:
                    top_layout_item = layout.itemAt(0)
                    if top_layout_item and isinstance(top_layout_item, QHBoxLayout):
                        if top_layout_item.count() > 1:
                            progress_item = top_layout_item.itemAt(1)
                            if progress_item and progress_item.widget() and isinstance(progress_item.widget(), QLabel):
                                progress_label = progress_item.widget()

        progress_bar = None
        for child in widget.findChildren(QProgressBar):
            progress_bar = child
            break

        # Обновляем найденные виджеты
        if progress_label:
            # Формат: "собрано/всего" (например, "134/200")
            if total > 0:
                progress_label.setText(f"{allocated}/{total}")
            else:
                progress_label.setText("0/0")
            progress_label.setToolTip(f"Собрано: {allocated} из {total}")
            
            # Цвет зависит от прогресса
            theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])
            if total == 0:
                text_color = theme["window_text"].name()
            elif remaining == 0:
                text_color = "#28a745"  # Зеленый - все собрано
            elif remaining < total:
                text_color = "#ffc107"  # Желтый - частично собрано
            else:
                text_color = theme["window_text"].name()  # Обычный цвет
            
            progress_label.setStyleSheet(f"color: {text_color}; font-weight: bold;")

        if progress_bar and total > 0:
            max_value = min(total, 2147483647)
            progress_bar.setValue(min(allocated, max_value))

    def _update_group_progress_in_widget(self, widget, group_shipment):
        """Обновляет прогресс в виджете групповой поставки"""
        allocated, total = group_shipment.get_progress_info()
        remaining = total - allocated

        # Находим label с прогрессом по objectName
        progress_label = widget.findChild(QLabel, "shipment_progress_label")

        # Если не нашли по objectName, ищем по позиции
        if not progress_label:
            layout = widget.layout()
            if layout and isinstance(layout, QVBoxLayout):
                if layout.count() > 0:
                    top_layout_item = layout.itemAt(0)
                    if top_layout_item and isinstance(top_layout_item, QHBoxLayout):
                        # В групповой поставке: 0=иконка, 1=название, 2=прогресс
                        if top_layout_item.count() > 2:
                            progress_item = top_layout_item.itemAt(2)
                            if progress_item and progress_item.widget() and isinstance(progress_item.widget(), QLabel):
                                progress_label = progress_item.widget()

        progress_bar = None
        for child in widget.findChildren(QProgressBar):
            progress_bar = child
            break

        # Обновляем найденные виджеты
        if progress_label:
            if total > 0:
                progress_label.setText(f"{allocated}/{total}")
            else:
                progress_label.setText("0/0")

            # Цвет в зависимости от прогресса
            if total > 0 and allocated >= total:
                text_color = "#27ae60"  # Зеленый - завершено
            elif allocated > 0:
                text_color = "#3498db"  # Синий - в процессе
            else:
                text_color = "#7f8c8d"  # Серый - не начато

            progress_label.setStyleSheet(f"color: {text_color}; font-weight: bold;")

        if progress_bar and total > 0:
            max_value = min(total, 2147483647)
            progress_bar.setValue(min(allocated, max_value))

        widget.update()
        widget.repaint()

    def _update_box_progress_in_widget(self, widget, box, shipment):
        """Обновляет только прогресс в виджете коробки"""
        # Обновляем количество товаров в коробке
        total_items = box.total_items_count()
        
        # Находим label с названием коробки
        for child in widget.findChildren(QLabel):
            text = child.text()
            # Проверяем, это название коробки с количеством (например, "Коробка-1 (5 шт.)")
            if '(' in text and 'шт.)' in text:
                # Обновляем текст с новым количеством
                box_name = text.split(' (')[0]
                child.setText(f"{box_name} ({total_items} шт.)")
                child.update()
                child.repaint()
                break

        widget.update()
        widget.repaint()

    def _update_tree_styles_fast(self):
        """Быстро обновляет стили всех элементов дерева на основе current_shipment"""
        # Выделение цветом убрано - все элементы остаются с прозрачным фоном
        pass

    def update_shipment_tree_selection(self):
        """Обновляет выделение в дереве поставок для текущей поставки/коробки"""
        # Сохраняем текущий выделенный элемент (коробку)
        current_selected = self.main_window.shipments_tree_widget.currentItem()

        # Разворачиваем текущую поставку для отображения коробок
        # (expand_current_shipment_collapse_others уже вызван и обновил is_expanded флаги)
        self._apply_expansion_flags()

        # Восстанавливаем выделение на коробке
        if current_selected:
            self.main_window.shipments_tree_widget.setCurrentItem(current_selected)

        # Визуально подсвечиваем родительскую поставку
        self._highlight_parent_shipment()

    def _apply_expansion_flags(self):
        """Применяет флаги is_expanded к элементам дерева"""
        if not self.main_window.current_shipment:
            return

        tree_widget = self.main_window.shipments_tree_widget
        
        for i in range(tree_widget.topLevelItemCount()):
            item = tree_widget.topLevelItem(i)
            group_shipment = item.data(0, Qt.ItemDataRole.UserRole + 2)

            if group_shipment:
                # Это групповая поставка - применяем флаг is_expanded
                item.setExpanded(group_shipment.is_expanded)
                # Применяем флаги к вложенным поставкам
                for j in range(item.childCount()):
                    child_item = item.child(j)
                    child_shipment = child_item.data(0, Qt.ItemDataRole.UserRole)
                    if child_shipment:
                        child_item.setExpanded(child_shipment.is_expanded)
            else:
                # Это обычная поставка - применяем флаг is_expanded
                shipment = item.data(0, Qt.ItemDataRole.UserRole)
                if shipment:
                    item.setExpanded(shipment.is_expanded)

    def _highlight_parent_shipment(self):
        """Визуально подсвечивает поставку, которой принадлежит текущая коробка"""
        if not self.main_window.current_shipment:
            return

        # Сначала удаляем маркеры со всех поставок
        self._clear_all_shipment_highlights()

        # Находим текущую поставку в дереве и добавляем визуальную подсветку
        for i in range(self.main_window.shipments_tree_widget.topLevelItemCount()):
            item = self.main_window.shipments_tree_widget.topLevelItem(i)
            shipment = item.data(0, Qt.ItemDataRole.UserRole)
            group_shipment = item.data(0, Qt.ItemDataRole.UserRole + 2)

            if group_shipment:
                # Это групповая поставка - ищем вложенную поставку
                if self.main_window.current_shipment.parent_group == group_shipment:
                    for j in range(item.childCount()):
                        child_item = item.child(j)
                        child_shipment = child_item.data(0, Qt.ItemDataRole.UserRole)
                        if child_shipment == self.main_window.current_shipment:
                            # Подсвечиваем вложенную поставку
                            self._add_shipment_highlight(child_item)
                            return
            elif shipment == self.main_window.current_shipment:
                # Это обычная поставка - подсвечиваем её
                self._add_shipment_highlight(item)
                return

    def _clear_all_shipment_highlights(self):
        """Удаляет все маркеры выделения с поставок"""
        tree_widget = self.main_window.shipments_tree_widget
        for i in range(tree_widget.topLevelItemCount()):
            item = tree_widget.topLevelItem(i)
            self._remove_shipment_highlight(item)
            # Очищаем маркеры у вложенных элементов
            for j in range(item.childCount()):
                child_item = item.child(j)
                self._remove_shipment_highlight(child_item)

    def _remove_shipment_highlight(self, item):
        """Удаляет маркер выделения с элемента поставки"""
        widget = self.main_window.shipments_tree_widget.itemWidget(item, 0)
        if not widget:
            return

        if hasattr(widget, 'highlight_dot') and widget.highlight_dot:
            # Удаляем маркер из layout
            layout = widget.layout()
            if isinstance(layout, QHBoxLayout):
                layout.removeWidget(widget.highlight_dot)
            elif isinstance(layout, QVBoxLayout):
                for child_layout_item in layout.children():
                    child_layout = child_layout_item.layout()
                    if child_layout and isinstance(child_layout, QHBoxLayout):
                        child_layout.removeWidget(widget.highlight_dot)
                        break

            widget.highlight_dot.deleteLater()
            widget.highlight_dot = None
            widget.update()

    def _add_shipment_highlight(self, item):
        """Добавляет визуальную подсветку к элементу поставки в виде голубой точки"""
        # Получаем текущую тему для выбора цвета точки
        current_theme = self.main_window.current_theme
        theme_colors = {
            'Светлая': '#2196F3',    # Голубой для светлой темы
            'Тёмная': '#64B5F6',     # Светло-голубой для тёмной темы
            'Контрастная': '#90CAF9',  # Голубой для контрастной
            'Light': '#2196F3',
            'Dark': '#64B5F6',
            'Contrast': '#90CAF9',
        }
        dot_color = theme_colors.get(current_theme, '#64B5F6')
        
        # Получаем существующий виджет
        widget = self.main_window.shipments_tree_widget.itemWidget(item, 0)
        if not widget:
            return
        
        # Проверяем, есть ли уже точка
        if hasattr(widget, 'highlight_dot') and widget.highlight_dot:
            # Точка уже есть - проверяем, нужно ли обновить цвет
            current_style = widget.highlight_dot.styleSheet()
            if f"color: {dot_color};" not in current_style:
                # Обновляем цвет существующей точки
                widget.highlight_dot.setStyleSheet(
                    f"color: {dot_color}; "
                    "font-size: 16px; "
                    "font-weight: bold; "
                    "padding-right: 4px;"
                )
                widget.highlight_dot.update()
            # Выходим - не пересоздаём точку
            return
        
        # Точки нет - создаём новую
        # Создаём метку с точкой
        dot_label = QLabel("●")
        dot_label.setStyleSheet(
            f"color: {dot_color}; "
            "font-size: 16px; "
            "font-weight: bold; "
            "padding-right: 4px;"
        )
        dot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Сохраняем ссылку на точку в виджете
        widget.highlight_dot = dot_label
        
        # Вставляем точку в начало layout
        layout = widget.layout()
        if isinstance(layout, QHBoxLayout):
            layout.insertWidget(0, dot_label)
        elif isinstance(layout, QVBoxLayout):
            # Для QVBoxLayout ищем top_layout и добавляем туда
            for i in range(layout.count()):
                child_layout = layout.itemAt(i).layout()
                if child_layout and isinstance(child_layout, QHBoxLayout):
                    child_layout.insertWidget(0, dot_label)
                    break
        
        widget.update()

    def update_shipment_tree_expansion(self):
        """Обновляет состояние развернутости элементов дерева поставок"""
        # Сохраняем текущее состояние развернутых элементов
        expanded_items = set()
        for i in range(self.main_window.shipments_tree_widget.topLevelItemCount()):
            item = self.main_window.shipments_tree_widget.topLevelItem(i)
            if item and item.isExpanded():
                shipment = item.data(0, Qt.ItemDataRole.UserRole)
                if shipment:
                    # Используем destination_name для отображения
                    name_to_store = shipment.destination_name
                    expanded_items.add(name_to_store)
      
        # Восстанавливаем состояние развернутых элементов
        for i in range(self.main_window.shipments_tree_widget.topLevelItemCount()):
            item = self.main_window.shipments_tree_widget.topLevelItem(i)
            shipment = item.data(0, Qt.ItemDataRole.UserRole)
            group_shipment = item.data(0, Qt.ItemDataRole.UserRole + 2)
            
            if shipment and not group_shipment:
                # Это обычная поставка
                # Используем display_name если доступен, иначе destination_name
                name_to_check = getattr(shipment, 'display_name', shipment.destination_name)
                item.setExpanded(name_to_check in expanded_items or getattr(shipment, 'is_expanded', False))
            elif group_shipment:
                # Это групповая поставка
                item.setExpanded(group_shipment.group_name in expanded_items or group_shipment.is_expanded)

    def update_buttons_style(self):
        # Не переопределяем стили кнопок, чтобы не сбрасывать пользовательский цвет
        # Вместо этого просто применяем пользовательский цвет, если он есть
        if hasattr(self.main_window, 'button_primary_color') and self.main_window.button_primary_color:
            self.main_window.apply_button_colors()

    def update_shipments_tree(self):
        # Сохраняем текущее состояние развернутых элементов
        expanded_items = set()
        for i in range(self.main_window.shipments_tree_widget.topLevelItemCount()):
            item = self.main_window.shipments_tree_widget.topLevelItem(i)
            if item and item.isExpanded():
                shipment = item.data(0, Qt.ItemDataRole.UserRole)
                if shipment:
                    name_to_store = shipment.destination_name
                    expanded_items.add(name_to_store)

        # Сохраняем текущий выбранный элемент
        current_selected_item = self.main_window.shipments_tree_widget.currentItem()

        # Получаем текущую поставку и индекс коробки до очистки дерева
        current_shipment = self.main_window.current_shipment
        current_box_index = current_shipment.current_box_index if current_shipment else -1

        # Сохраняем текущий размер шрифта
        font_size = self.main_window.font_size

        self.main_window.shipments_tree_widget.clear()

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

        for shipment_name, shipment in sorted(self.main_window.shipments.items()):
            item = QTreeWidgetItem(self.main_window.shipments_tree_widget)
            item.setData(0, Qt.ItemDataRole.UserRole, shipment)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, None)
            self.create_shipment_tree_item(item, shipment_name, shipment)
            item.setExpanded(shipment_name in expanded_items or getattr(shipment, 'is_expanded', False))

            sorted_boxes = sorted(shipment.boxes, key=lambda box: get_box_number(box.box_id))
            for box in sorted_boxes:
                box_item = QTreeWidgetItem(item)
                box_item.setData(0, Qt.ItemDataRole.UserRole, shipment)
                box_item.setData(0, Qt.ItemDataRole.UserRole + 1, box)
                self.create_box_tree_item(box_item, box, shipment)

                is_current_box = (current_shipment == shipment and
                               current_box_index >= 0 and
                               shipment.boxes[current_box_index] == box)

                if is_current_box:
                    self.main_window.shipments_tree_widget.setCurrentItem(box_item)

        for group_name, group_shipment in sorted(self.main_window.group_shipments.items()):
            group_item = QTreeWidgetItem(self.main_window.shipments_tree_widget)
            group_item.setData(0, Qt.ItemDataRole.UserRole + 2, group_shipment)
            group_item.setData(0, Qt.ItemDataRole.UserRole, None)
            group_item.setData(0, Qt.ItemDataRole.UserRole + 1, None)
            self.create_group_tree_item(group_item, group_name, group_shipment)
            group_item.setExpanded(group_name in expanded_items or group_shipment.is_expanded)

            for shipment_name, shipment in sorted(group_shipment.sub_shipments.items()):
                child_item = QTreeWidgetItem(group_item)
                child_item.setData(0, Qt.ItemDataRole.UserRole, shipment)
                child_item.setData(0, Qt.ItemDataRole.UserRole + 1, None)
                self.create_shipment_tree_item(child_item, shipment_name, shipment, is_child=True)
                name_to_check = getattr(shipment, 'display_name', shipment.destination_name)
                child_item.setExpanded(name_to_check in expanded_items or getattr(shipment, 'is_expanded', False))

                sorted_boxes = sorted(shipment.boxes, key=lambda box: get_box_number(box.box_id))
                for box in sorted_boxes:
                    box_item = QTreeWidgetItem(child_item)
                    box_item.setData(0, Qt.ItemDataRole.UserRole, shipment)
                    box_item.setData(0, Qt.ItemDataRole.UserRole + 1, box)
                    self.create_box_tree_item(box_item, box, shipment)

                    is_current_box = (current_shipment == shipment and
                                   current_box_index >= 0 and
                                   shipment.boxes[current_box_index] == box)

                    if is_current_box:
                        self.main_window.shipments_tree_widget.setCurrentItem(box_item)

        if not self.main_window.shipments_tree_widget.currentItem() and current_selected_item:
            self.main_window.shipments_tree_widget.clearSelection()

        self.update_shipment_tree_selection()

    def _refresh_tree_widgets(self):
        """Обновляет все виджеты в дереве поставок"""
        def refresh_items(parent_item=None):
            if parent_item is None:
                # Обрабатываем корневые элементы
                for i in range(self.main_window.shipments_tree_widget.topLevelItemCount()):
                    item = self.main_window.shipments_tree_widget.topLevelItem(i)
                    widget = self.main_window.shipments_tree_widget.itemWidget(item, 0)
                    if widget:
                        widget.update()
                        # Обновляем все дочерние элементы
                        refresh_items(item)
            else:
                # Обрабатываем дочерние элементы
                for i in range(parent_item.childCount()):
                    child_item = parent_item.child(i)
                    widget = self.main_window.shipments_tree_widget.itemWidget(child_item, 0)
                    if widget:
                        widget.update()
                    # Рекурсивно обрабатываем вложенные элементы
                    refresh_items(child_item)
        
        refresh_items()
        
        # Обновляем геометрию дерева
        self.main_window.shipments_tree_widget.updateGeometry()
        
    def create_shipment_tree_item(self, item, shipment_name, shipment, is_child=False):
        widget = QWidget()

        theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])

        # Всегда применяем прозрачный фон - выделение делается в update_shipment_tree_selection()
        widget_style = """
 background: transparent;
 border: none;
 margin: 1px;
 """

        widget.setStyleSheet(widget_style)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(
            TREE_ITEM_MARGIN_LEFT if not is_child else TREE_ITEM_MARGIN_LEFT + 2,
            TREE_ITEM_MARGIN_TOP,
            TREE_ITEM_MARGIN_RIGHT,
            TREE_ITEM_MARGIN_BOTTOM
        )
        layout.setSpacing(TREE_ITEM_SPACING)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)

        # Используем display_name для красивого отображения, если доступен
        display_name = getattr(shipment, 'display_name', shipment_name)
        name_text = display_name
        
        # Сохраняем текст для последующего использования в highlight (UserRole + 3)
        item.setData(0, Qt.ItemDataRole.UserRole + 3, name_text)
        
        name_label = QLabel(name_text)
        text_color = theme["window_text"].name()

        # Устанавливаем шрифт с явным размером из настроек
        name_font = QFont()
        name_font.setPointSize(self.main_window.font_size)
        if not is_child:
            name_font.setBold(True)
        name_label.setFont(name_font)
        name_style = f"color: {text_color};"
        name_label.setStyleSheet(name_style)
        name_label.setWordWrap(True)
        name_label.setMinimumWidth(10)  # Минимальная ширина для имени
        top_layout.addWidget(name_label, 1)  # Растягиваем имя
      
        # Отображаем активных пользователей и индикатор блокировки
        # Система блокировки поставок удалена, поэтому всегда 0
        active_users_count = 0
        current_user = getattr(self.main_window, 'current_user', None)
        
        # Система блокировки поставок удалена, поэтому всегда False
        is_locked = False
        other_users = []
        
        # Система блокировки поставок удалена, поэтому не отображаем иконки блокировки и активных пользователей
        # if is_locked:
        #     # Показываем иконку блокировки если поставка заблокирована другими
        #     lock_text = f"🔒 {len(other_users)}"
        #     lock_label = QLabel(lock_text)
        #     lock_label.setFixedWidth(60)
        #     lock_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        #     lock_label.setStyleSheet(f"color: #dc3545; font-weight: bold;")  # Красный цвет для блокировки
        #     lock_label.setToolTip(f"Заблокировано: {', '.join(other_users)}")
        #     top_layout.addWidget(lock_label)
        # elif active_users_count > 0:
        #     # Показываем количество активных пользователей если есть текущий пользователь
        #     active_users_text = f"👤 {active_users_count}"
        #     active_users_label = QLabel(active_users_text)
        #     active_users_label.setFixedWidth(50)
        #     active_users_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        #     active_users_label.setStyleSheet(f"color: #28a745; font-weight: bold;")  # Зеленый цвет для текущего пользователя
        #     top_layout.addWidget(active_users_label)

        allocated, total = shipment.get_progress_info()
        remaining = total - allocated

        # Форматируем отображение: "собрано/всего" (например, "134/200")
        if total > 0:
            progress_text = QLabel(f"{allocated}/{total}")
        else:
            progress_text = QLabel("0/0")

        # Устанавливаем objectName для поиска при обновлении
        progress_text.setObjectName("shipment_progress_label")

        # Разрешаем метке расширяться по горизонтали
        progress_text.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        # Устанавливаем минимальную ширину для "9999/9999"
        progress_text.setMinimumWidth(80)
        progress_text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # Устанавливаем шрифт с явным размером из настроек
        progress_font = QFont()
        progress_font.setPointSize(self.main_window.font_size)
        progress_text.setFont(progress_font)

        # Цвет зависит от прогресса
        if total == 0:
            text_color = theme["window_text"].name()
        elif remaining == 0:
            text_color = "#28a745"  # Зеленый - все собрано
        elif remaining < total:
            text_color = "#ffc107"  # Желтый - частично собрано
        else:
            text_color = theme["window_text"].name()  # Обычный цвет
        
        progress_text.setStyleSheet(f"color: {text_color}; font-weight: bold;")
        progress_text.setToolTip(f"Собрано: {allocated} из {total}")
        progress_text.updateGeometry()  # Принудительно обновляем геометрию
        top_layout.addWidget(progress_text)

        # Добавляем количество коробок
        boxes_count = len(shipment.boxes)
        boxes_label = QLabel(f"📦 {boxes_count}")
        boxes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        boxes_font = QFont()
        boxes_font.setPointSize(self.main_window.font_size)
        boxes_label.setFont(boxes_font)
        boxes_label.setStyleSheet(f"color: {text_color};")
        boxes_label.setToolTip(f"Коробок в поставке: {boxes_count}")
        top_layout.addWidget(boxes_label)

        layout.addLayout(top_layout)

        if total > 0:
            progress_bar = QProgressBar()
            max_value = min(total, 2147483647)
            progress_bar.setMaximum(max_value)
            progress_bar.setValue(min(allocated, max_value))
            progress_bar.setTextVisible(False)
            progress_bar.setFixedHeight(6)
            
            progress_bar.setStyleSheet(f"""
 QProgressBar {{
     border: 1px solid {theme["button_border"].name()};
     border-radius: 4px;
     background-color: {theme["button_bg"].name()};
 }}
 QProgressBar::chunk {{
     background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
         stop: 0 {theme["accent_success"].darker(120).name()},
         stop: 1 {theme["accent_success"].name()});
     border-radius: 3px;
 }}
 """)
            layout.addWidget(progress_bar)

        self.main_window.shipments_tree_widget.setItemWidget(item, 0, widget)
        item.setSizeHint(0, QSize(100, SHIPMENT_ITEM_HEIGHT_WITH_PROGRESS if total > 0 else SHIPMENT_ITEM_HEIGHT_NO_PROGRESS))

        # Ensure the widget is properly updated after theme change
        widget.update()

    def create_box_tree_item(self, item, box, shipment):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(
            BOX_ITEM_MARGIN_LEFT,
            BOX_ITEM_MARGIN_TOP,
            BOX_ITEM_MARGIN_RIGHT,
            BOX_ITEM_MARGIN_BOTTOM
        )
        layout.setSpacing(BOX_ITEM_SPACING)

        theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])

        # Всегда применяем прозрачный фон - выделение делается в update_shipment_tree_selection()
        widget_style = """
     background: transparent;
     border: none;
     margin: 1px;
     padding: 3px;
     """

        widget.setStyleSheet(widget_style)

        # Проверяем, есть ли в коробке товары, которые нарушают правила:
        # 1. Количество товара в коробке превышает общее количество в поставке
        # 2. Товар помечен как удаленный из поставки
        has_removed_items = False
        for barcode in box.items.keys():
            # Проверяем, является ли товар удаленным из поставки
            if barcode in shipment.removed_items:
                has_removed_items = True
                break

            # Проверяем, превышает ли количество в коробке общее количество в поставке
            shipment_item = shipment.shipment_items.get(barcode)
            if shipment_item:
                # Если товар в поставке был уменьшен, и в коробке его осталось больше, чем теперь положено иметь всего
                if box.items[barcode] > shipment_item.total_qty:
                    has_removed_items = True
                    break

        # Проверяем, если коробка содержит товары, которые были частично удалены из поставки
        # Это может произойти, если allocated_qty > total_qty для товара в поставке
        if not has_removed_items:
            for barcode in box.items.keys():
                shipment_item = shipment.shipment_items.get(barcode)
                if shipment_item and shipment_item.allocated_qty > shipment_item.total_qty:
                    # Если общий allocated_qty для этого товара превышает total_qty,
                    # и товар находится в этой коробке, он может быть лишним в контексте общего распределения
                    has_removed_items = True
                    break

        # Загружаем иконку коробки (используем кэш)
        icon_path = config.get_resource_path(Path("Res") / "box.png")
        pixmap = get_cached_pixmap(icon_path, (ICON_SIZE_SMALL, ICON_SIZE_SMALL))
        icon_label = QLabel()
        icon_label.setPixmap(pixmap)
        icon_label.setFixedSize(24, 24)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Если коробка содержит удаленные/проблемные товары, показываем дополнительный индикатор
        if has_removed_items:
            warning_label = QLabel("🔴")
            warning_label.setFixedSize(16, 16)
            warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(warning_label)

            # Устанавливаем красный фон для коробки с лишними товарами
            widget.setStyleSheet(f"""
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #ef5350,
                    stop: 1 #c62828);
                border: none;
                margin: 1px;
                padding: 3px;
            """)

        total_items = box.total_items_count()
        box_text = f"{box.box_id} ({total_items} шт.)"
        
        # Сохраняем текст для последующего использования в highlight (UserRole + 3)
        item.setData(0, Qt.ItemDataRole.UserRole + 3, box_text)
        
        name_label = QLabel(box_text)
        text_color = theme["window_text"].name()
        # Устанавливаем шрифт с явным размером из настроек
        name_font = QFont()
        name_font.setPointSize(self.main_window.font_size)
        name_label.setFont(name_font)
        name_style = f"color: {text_color};"
        name_label.setStyleSheet(name_style)
        name_label.setMinimumWidth(120)
        layout.addWidget(name_label, 1)

        layout.addStretch()

        self.main_window.shipments_tree_widget.setItemWidget(item, 0, widget)
        item.setSizeHint(0, QSize(100, BOX_ITEM_HEIGHT))  # Оптимальная высота для коробок

        # Ensure the widget is properly updated after theme change
        widget.update()
    
    def create_group_tree_item(self, item, group_name, group_shipment):
        widget = QWidget()

        theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])

        # Всегда применяем прозрачный фон - выделение делается в update_shipment_tree_selection()
        widget_style = """
 background: transparent;
 border: none;
 margin: 1px;
 """

        widget.setStyleSheet(widget_style)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        status_icon_svg = group_shipment.get_status_icon()
        status_pixmap = QPixmap()
        status_pixmap.loadFromData(status_icon_svg.encode('utf-8'))
        status_label = QLabel()
        status_label.setPixmap(status_pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        status_label.setFixedSize(24, 24)
        # Устанавливаем шрифт с явным размером из настроек
        status_font = QFont()
        status_font.setPointSize(self.main_window.font_size)
        status_label.setFont(status_font)
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(status_label)

        name_label = QLabel(group_name)
        
        # Сохраняем текст для последующего использования в highlight (UserRole + 3)
        item.setData(0, Qt.ItemDataRole.UserRole + 3, group_name)
        
        text_color = theme["window_text"].name()
        # Устанавливаем шрифт с явным размером из настроек
        name_font = QFont()
        name_font.setPointSize(self.main_window.font_size)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: {text_color};")
        name_label.setWordWrap(True)
        name_label.setMinimumWidth(100)  # Минимальная ширина
        top_layout.addWidget(name_label, 1)

        allocated, total = group_shipment.get_progress_info()
        progress_text = QLabel(f"{allocated}/{total}")
        # Устанавливаем objectName для поиска при обновлении
        progress_text.setObjectName("shipment_progress_label")
        # Разрешаем метке расширяться по горизонтали
        progress_text.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        # Устанавливаем минимальную ширину для "9999/9999"
        progress_text.setMinimumWidth(100)
        progress_text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # Устанавливаем шрифт с явным размером из настроек
        progress_font = QFont()
        progress_font.setPointSize(self.main_window.font_size)
        progress_text.setFont(progress_font)
        progress_text.setStyleSheet(f"font-weight: bold; color: {text_color};")
        progress_text.setToolTip(f"Собрано: {allocated} из {total}")
        progress_text.updateGeometry()  # Принудительно обновляем геометрию
        top_layout.addWidget(progress_text)

        layout.addLayout(top_layout)

        if total > 0:
            progress_bar = QProgressBar()
            max_value = min(total, 2147483647)
            progress_bar.setMaximum(max_value)
            progress_bar.setValue(min(allocated, max_value))
            progress_bar.setTextVisible(False)
            progress_bar.setFixedHeight(6)
            
            progress_bar.setStyleSheet(f"""
 QProgressBar {{
     border: 1px solid {theme["button_border"].name()};
     border-radius: 4px;
     background-color: {theme["button_bg"].name()};
 }}
 QProgressBar::chunk {{
     background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
         stop: 0 {theme["accent_primary"].darker(120).name()},
         stop: 1 {theme["accent_primary"].name()});
     border-radius: 3px;
 }}
 """)
            layout.addWidget(progress_bar)

        sub_shipments_info = QLabel(f"Направления: {len(group_shipment.sub_shipments)}")
        # Устанавливаем шрифт с размером на 1 меньше основного
        sub_font = QFont()
        sub_font.setPointSize(max(8, self.main_window.font_size - 1))  # Уменьшаем на 1, но не меньше 8
        sub_shipments_info.setFont(sub_font)
        sub_shipments_info.setStyleSheet(f"color: {text_color};")
        layout.addWidget(sub_shipments_info)

        self.main_window.shipments_tree_widget.setItemWidget(item, 0, widget)
        item.setSizeHint(0, QSize(100, 65))
        
        # Ensure the widget is properly updated after theme change
        widget.update()


    def update_shipment_table(self):
        """Обновление таблицы поставки"""
        if self.main_window.updating_ui:
            return
        # Защита от рекурсии - если уже обновляем таблицу, пропускаем
        if getattr(self, '_updating_shipment_table', False):
            logger.debug("update_shipment_table: пропуск - уже выполняется")
            return
        
        # Защита от частых вызовов - не чаще 1 раза в 100ms
        current_time = time.time()
        last_update = getattr(self, '_last_shipment_table_update', 0)
        if current_time - last_update < 0.1:
            return
        self._last_shipment_table_update = current_time
        self._updating_shipment_table = True
        
        try:
            current_item = self.main_window.shipments_tree_widget.currentItem()
            if current_item:
                group_shipment = current_item.data(0, Qt.ItemDataRole.UserRole + 2)
                if group_shipment:
                    self.update_group_shipment_items_table(group_shipment)
                    return

            try:
                self.main_window.shipment_table.cellChanged.disconnect(self.main_window.on_shipment_cell_changed)
            except (TypeError, RuntimeError):
                pass
            self.main_window.shipment_table.setSortingEnabled(False)
            
            # Явно очищаем все виджеты кнопок перед сбросом строк
            for row in range(self.main_window.shipment_table.rowCount()):
                for col in range(self.main_window.shipment_table.columnCount()):
                    widget = self.main_window.shipment_table.cellWidget(row, col)
                    if widget:
                        widget.deleteLater()
            
            # Очищаем кэш собранных товаров перед обновлением таблицы
            self._clear_allocated_qty_cache()
            
            # Проверка на существование текущей поставки
            if not self.main_window.current_shipment:
                current_item = self.main_window.shipments_tree_widget.currentItem()
                if current_item:
                    group_shipment = current_item.data(0, Qt.ItemDataRole.UserRole + 2)
                    if group_shipment:
                        self.update_group_shipment_items_table(group_shipment)
                        return
                self.main_window.shipment_table.setRowCount(0)
                # Также очищаем заголовок таблицы поставки
                self.main_window.shipment_table_label.setText("Состав поставки:")
                return


            # Проверяем, включена ли интеграция с МойСклад (ГЛОБАЛЬНАЯ настройка)
            moysklad_enabled = database.get_moysklad_enabled()
            
            # Читаем видимость столбца из ТЕКУЩЕГО состояния чекбокса, а не из БД
            stock_column_visible = getattr(self.main_window, 'stock_column_visible', True)

            shipment_items = list(self.main_window.current_shipment.shipment_items.values())
            self.main_window.shipment_table.setRowCount(len(shipment_items))
            

            # Получаем тему с проверкой
            current_theme = getattr(self.main_window, 'current_theme', None)
            if current_theme is None or current_theme not in themes.THEMES:
                logger.warning(f"Тема не установлена или некорректна: {current_theme}, используем Светлая")
                current_theme = "Светлая"
            theme = themes.THEMES.get(current_theme, themes.THEMES["Светлая"])

            logger.debug(f"update_shipment_table: тема={current_theme}, table_bg={theme['table_bg'].name()}, text={theme['text'].name()}, highlight={theme['highlight'].name()}")

            # Отключаем обновления таблицы во время заполнения для повышения производительности
            self.main_window.shipment_table.setUpdatesEnabled(False)

            # Обновляем заголовки таблицы с переданными настройками
            self.update_shipment_table_headers(moysklad_enabled, stock_column_visible)

            # Получаем кэшированные остатки, не обновляя их автоматически при переключении поставок
            stock_quantities = {}
            # Инициализируем product_names для второго блока
            product_names = {}

            # Получаем наименования товаров из базы
            try:
                barcodes = [item.barcode for item in shipment_items]
                from database import get_product_names_by_barcodes
                product_names = get_product_names_by_barcodes(barcodes)
            except Exception as e:
                logger.error(f"Ошибка при получении наименований: {e}")
                product_names = {}
            if MOYSKLAD_API_AVAILABLE and moysklad_enabled:
                try:
                    # Используем кэшированные остатки из базы данных без автоматического обновления при переключении поставок
                    for item in shipment_items:
                        # Сначала пробуем получить из локального кэша
                        from get_stock_quantity_for_item import stock_cache
                        cached_qty = stock_cache.get_cached_quantity(item.barcode)
                        if cached_qty is not None:
                            stock_quantities[item.barcode] = cached_qty
                        else:
                            # Если в локальном кэше нет, пробуем получить из базы данных
                            db_qty = database.get_stock_cache(item.barcode)
                            if db_qty is not None:
                                stock_quantities[item.barcode] = db_qty
                                # Также сохраняем в локальный кэш для ускорения последующих обращений
                                stock_cache.set_cached_quantity(item.barcode, db_qty)
                            else:
                                # Если остаток не закэширован нигде, устанавливаем 0
                                stock_quantities[item.barcode] = 0
                except Exception as e:
                    logger.error(f"Ошибка при получении кэшированных остатков: {e}")
                    # В случае ошибки, устанавливаем 0 для всех товаров
                    for item in shipment_items:
                        stock_quantities[item.barcode] = 0

            logger.info(f"Начало цикла заполнения таблицы: {len(shipment_items)} товаров, stock_quantities keys={len(stock_quantities) if stock_quantities else 0}, moysklad_enabled={moysklad_enabled}, stock_column_visible={stock_column_visible}")
            
            # Оптимизация: предварительно рассчитываем все allocated_qty перед циклом
            # Это избегает многократных переборов всех поставок и коробок для каждого товара
            allocated_qty_cache = {}
            for item in shipment_items:
                allocated_qty_cache[item.barcode] = self.get_total_allocated_qty(item.barcode)
            
            for row, item in enumerate(shipment_items):
                remaining_qty = item.remaining_qty
                barcode_item = QTableWidgetItem(item.barcode)
                sku_item = QTableWidgetItem(item.sku)
                total_qty_item = QTableWidgetItem(str(item.total_qty))
                remaining_item = QTableWidgetItem(str(remaining_qty))

                # Получаем остаток из заранее загруженных данных
                stock_qty = stock_quantities.get(item.barcode, 0) if stock_quantities else 0
                # Вычитаем количество уже собранных товаров (используем предварительно рассчитанный кэш)
                total_allocated = allocated_qty_cache.get(item.barcode, 0)
                stock_qty -= total_allocated
                stock_item = QTableWidgetItem(str(stock_qty))
                stock_item.setFlags(stock_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Раскрашиваем число в столбце "На складе": синий если > 0, красный если <= 0
                if stock_qty > 0:
                    stock_item.setForeground(COLOR_STOCK_POSITIVE)  # Синий
                else:
                    stock_item.setForeground(COLOR_STOCK_NEGATIVE)  # Красный

                # Получаем наименование товара
                product_name = product_names.get(item.barcode, "")
                # Если наименование не найдено, используем артикул как резервный вариант
                if not product_name:
                    product_name = item.sku
                    # Если и артикул пустой, используем штрихкод
                    if not product_name:
                        product_name = item.barcode
                name_item = QTableWidgetItem(product_name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                barcode_item.setFlags(barcode_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                sku_item.setFlags(sku_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                total_qty_item.setFlags(total_qty_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                remaining_item.setFlags(remaining_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                stock_item.setFlags(stock_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                # Устанавливаем высоту строк в таблице поставки (не менее 28px для кнопок)
                font_height = self.main_window.shipment_table.fontMetrics().height()
                self.main_window.shipment_table.setRowHeight(row, max(TABLE_ROW_HEIGHT_MIN, font_height + TABLE_ROW_HEIGHT_PADDING))

                # Устанавливаем цвета только для текста - фон будет чередоваться автоматически
                for table_item in [barcode_item, sku_item, name_item, total_qty_item, remaining_item, stock_item]:
                    table_item.setForeground(theme["text"])

                # Устанавливаем специальный фон ТОЛЬКО для строк с особыми состояниями
                if item.barcode in self.main_window.current_shipment.removed_items:
                    removed_color = theme["removed_from_shipment"]
                    removed_text = theme["removed_text"]
                    for table_item in [barcode_item, sku_item, name_item, total_qty_item, remaining_item, stock_item]:
                        table_item.setBackground(removed_color)
                        table_item.setForeground(removed_text)

                elif item.remaining_qty < 0:
                    conflict_color = theme["conflict_exceed"]
                    conflict_text = theme["conflict_text"]
                    for table_item in [barcode_item, sku_item, name_item, total_qty_item, remaining_item, stock_item]:
                        table_item.setBackground(conflict_color)
                        table_item.setForeground(conflict_text)

                elif item.remaining_qty == 0:
                    completed_bg = theme["shipment_remaining_ok"]
                    completed_text = theme["shipment_text_ok"]

                    for table_item in [barcode_item, sku_item, name_item, total_qty_item, remaining_item, stock_item]:
                        table_item.setBackground(completed_bg)
                        table_item.setForeground(completed_text)

                elif item.remaining_qty > 0 and item.remaining_qty < item.total_qty:
                    partial_bg = theme["shipment_remaining_partial"]
                    partial_text = theme["shipment_text_partial"]

                    for table_item in [barcode_item, sku_item, name_item, remaining_item, stock_item]:
                        table_item.setBackground(partial_bg)
                        table_item.setForeground(partial_text)
                # Для остальных строк фон не устанавливаем - будет работать чередование

                # Размещение данных в таблице поставки
                # Порядок столбцов: 0=Штрихкод | 1=Артикул | 2=Наименование | 3=Всего | 4=Осталось | 5=На складе
                self.main_window.shipment_table.setItem(row, 0, barcode_item)      # Штрихкод
                self.main_window.shipment_table.setItem(row, 1, sku_item)          # Артикул
                self.main_window.shipment_table.setItem(row, 2, name_item)         # Наименование
                self.main_window.shipment_table.setItem(row, 3, total_qty_item)    # Всего
                self.main_window.shipment_table.setItem(row, 4, remaining_item)    # Осталось

                # Всегда устанавливаем stock_item в таблицу (даже если МойСклад отключен)
                self.main_window.shipment_table.setItem(row, 5, stock_item)    # На складе

                barcode = item.barcode

                # Создаем виджет с кнопкой "+" и полем ввода количества
                action_widget = QWidget(self.main_window.shipment_table)
                action_widget.setAutoFillBackground(False)
                action_widget.setStyleSheet("background-color: transparent; border: none;")
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(4, 2, 4, 2)
                action_layout.setSpacing(3)
                action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

                # Кнопка "+"
                add_btn = QPushButton("+", action_widget)
                add_btn.setFixedSize(16, 16)
                add_btn.setMinimumHeight(16)
                add_btn.setMaximumHeight(16)

                add_btn.setStyleSheet(f"""
QPushButton {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["accent_success"].lighter(120).name()},
        stop: 0.5 {theme["accent_success"].name()},
        stop: 1 {theme["accent_success"].darker(120).name()});
    color: white;
    border: 1px solid {theme["accent_success"].darker(150).name()};
    padding: 0px;
    margin: 0px;
    border-radius: 3px;
    font-weight: bold;
    font-size: 11px;
    min-height: 16px;
    max-height: 16px;
    min-width: 16px;
    max-width: 16px;
    height: 16px;
}}
QPushButton:disabled {{
    background: {theme["button_bg"].name()};
    color: {theme["button_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    min-height: 16px;
    max-height: 16px;
    height: 16px;
}}
QPushButton:hover {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["accent_success"].lighter(140).name()},
        stop: 0.5 {theme["accent_success"].lighter(120).name()},
        stop: 1 {theme["accent_success"].name()});
    min-height: 16px;
    max-height: 16px;
    height: 16px;
}}
""")
                add_btn.setToolTip("Добавить указанное количество в коробку")

                # Поле ввода количества
                qty_lineedit = QLineEdit(action_widget)
                qty_lineedit.setFixedWidth(QTY_INPUT_WIDTH)
                qty_lineedit.setText(str(max(1, int(item.remaining_qty))))
                qty_lineedit.setAlignment(Qt.AlignmentFlag.AlignCenter)
                qty_lineedit.setToolTip("Количество для добавления")
                qty_lineedit.setStyleSheet(f"""
QLineEdit {{
    border: 1px solid {theme["button_border"].name()};
    padding: 1px;
    border-radius: 3px;
    font-size: 11px;
    background-color: {theme["input_bg"].name()};
    color: {theme["input_text"].name()};
}}
QLineEdit:focus {{
    border: 1px solid {theme["accent_primary"].name()};
}}
""")

                # Валидатор только для чисел
                validator = QRegularExpressionValidator(QRegularExpression("\\d+"))
                qty_lineedit.setValidator(validator)
                qty_lineedit.setFixedWidth(35)  # Увеличиваем ширину для чисел

                # Обработчик кнопки - используем lambda с явными аргументами для избежания проблем с замыканием
                add_btn.clicked.connect(lambda checked, bc=barcode, le=qty_lineedit: self.main_window.add_all_remaining_to_box_by_barcode(bc, int(le.text()) if le.text().isdigit() else 1))

                action_layout.addWidget(add_btn)
                action_layout.addWidget(qty_lineedit)

                # Показываем виджет с кнопкой "+" всегда
                self.main_window.shipment_table.setCellWidget(row, 6, action_widget)
                
                # Устанавливаем фиксированную ширину столбца 6
                self.main_window.shipment_table.setColumnWidth(6, 80)
                
                # Устанавливаем стиль кнопок в зависимости от состояния
                is_disabled = item.remaining_qty <= 0 or barcode in self.main_window.current_shipment.removed_items
                if is_disabled:
                    add_btn.setEnabled(False)
                    qty_lineedit.setEnabled(False)
                else:
                    add_btn.setEnabled(True)
                    qty_lineedit.setEnabled(True)

            # Настройка видимости столбцов - один раз после цикла
            if moysklad_enabled:
                self.main_window.shipment_table.setColumnHidden(5, not stock_column_visible)
            else:
                self.main_window.shipment_table.setColumnHidden(5, True)
            # Столбец с кнопками всегда видим
            self.main_window.shipment_table.setColumnHidden(6, False)
            # Устанавливаем ширину столбца с кнопками
            self.main_window.shipment_table.setColumnWidth(6, ACTION_COLUMN_WIDTH)

            self.main_window.shipment_table.setUpdatesEnabled(True)

            # Применяем скрытие строк ДО включения сортировки, чтобы индексы строк совпадали
            self.update_shipment_table_rows_visibility()

            # Включаем сортировку после всех обновлений для возможности сортировки по столбцам
            # Но сбрасываем индикатор сортировки, чтобы сохранить исходный порядок строк
            self.main_window.shipment_table.setSortingEnabled(True)
            self.main_window.shipment_table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            self.main_window.shipment_table.cellChanged.connect(self.main_window.on_shipment_cell_changed)

            # Восстанавливаем сохраненные пользовательские настройки ширины столбцов
            if (hasattr(self.main_window, 'shipment_columns_width') and
                self.main_window.shipment_columns_width):
                try:
                    widths = self.main_window.shipment_columns_width.split(",")
                    for i, width_str in enumerate(widths):
                        if i < self.main_window.shipment_table.columnCount():
                            width = int(width_str)
                            # Устанавливаем ширину столбца только если она отличается от текущей
                            if self.main_window.shipment_table.columnWidth(i) != width:
                                self.main_window.shipment_table.setColumnWidth(i, width)
                except (ValueError, IndexError):
                    # Если не удалось восстановить сохраненные ширины, используем авто-размер
                    self.main_window.shipment_table.resizeColumnsToContents()
            else:
                # Если нет сохраненных настроек, используем авто-размер
                self.main_window.shipment_table.resizeColumnsToContents()
            
                # Принудительно устанавливаем ширину столбца 6 с кнопками, т.к. resizeColumnsToContents не учитывает виджеты
                self.main_window.shipment_table.setColumnWidth(6, ACTION_COLUMN_WIDTH)
                # Не скрываем и не показываем столбец 6 здесь - видимость уже установлена выше

                # Устанавливаем фиксированный режим для вертикального заголовка, чтобы сохранить нашу высоту строк
                self.main_window.shipment_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        except Exception as e:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА в update_shipment_table: {e}")
            logger.error(traceback.format_exc())
        finally:
            # Сбрасываем флаг рекурсии
            self._updating_shipment_table = False

    def update_shipment_table_rows_visibility(self):
        """Обновляет видимость строк в таблице поставки в зависимости от настройки скрытия полностью собранных строк"""
        if not self.main_window.current_shipment:
            return

        hide_completed_items = getattr(self.main_window.current_shipment, 'hide_completed_items', False)
        shipment_items = list(self.main_window.current_shipment.shipment_items.values())

        # Создаём словарь для быстрого поиска товара по штрихкоду
        items_by_barcode = {item.barcode: item for item in shipment_items}

        # Отключаем обновления таблицы на время изменения видимости строк для повышения производительности
        self.main_window.shipment_table.setUpdatesEnabled(False)

        try:
            # Проходим по всем строкам таблицы (визуальный порядок)
            for row in range(self.main_window.shipment_table.rowCount()):
                # Получаем штрихкод из первой колонки таблицы
                barcode_item = self.main_window.shipment_table.item(row, 0)
                if not barcode_item:
                    continue
                    
                barcode = barcode_item.text()
                
                # Находим товар по штрихкоду
                item = items_by_barcode.get(barcode)
                if not item:
                    continue
                
                # Скрываем строки, где remaining_qty == 0 (товар полностью собран, ничего не осталось)
                should_hide = (hide_completed_items and item.remaining_qty == 0)
                self.main_window.shipment_table.setRowHidden(row, should_hide)

        finally:
            self.main_window.shipment_table.setUpdatesEnabled(True)
            # updateGeometry() убран - может вызывать каскадное обновление в exe

    def update_current_box_table(self):
        try:
            self.main_window.current_box_table.cellChanged.disconnect(self.main_window.on_box_cell_changed)
        except (TypeError, RuntimeError):
            pass
        try:
            if not self.main_window.current_shipment or self.main_window.current_shipment.current_box_index < 0:
                self.main_window.current_box_table.setRowCount(0)
                # Также очищаем метку текущей коробки
                self.update_current_box_label()
                return
            current_box = self.main_window.current_shipment.boxes[self.main_window.current_shipment.current_box_index]
            self.main_window.current_box_table.setRowCount(len(current_box.items))
            theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])
            # Отключаем обновления таблицы во время заполнения для повышения производительности
            self.main_window.current_box_table.setUpdatesEnabled(False)
            for row, (barcode, qty) in enumerate(current_box.items.items()):
                # Создаем ячейки для штрихкода и артикула с запретом редактирования
                barcode_item = QTableWidgetItem(barcode)
                barcode_item.setFlags(barcode_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.main_window.current_box_table.setItem(row, 0, barcode_item)
                
                if barcode in self.main_window.current_shipment.removed_items:
                    sku = self.main_window.current_shipment.removed_items[barcode]['sku']
                else:
                    shipment_item = self.main_window.current_shipment.shipment_items.get(barcode)
                    sku = shipment_item.sku if shipment_item else "?"
                sku_item = QTableWidgetItem(sku)
                sku_item.setFlags(sku_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.main_window.current_box_table.setItem(row, 1, sku_item)
                
                # Создаем ячейку для количества с разрешением редактирования
                qty_item = QTableWidgetItem(str(qty))
                qty_item.setFlags(qty_item.flags() | Qt.ItemFlag.ItemIsEditable)
                
                # Проверяем, нужно ли выделить товар (товар для удаления или уменьшения)
                needs_highlight = False
                is_full_removal = False  # Полное удаление или частичное уменьшение
                excess_qty_in_current_box = 0  # Количество, которое превышает норму в текущей коробке
                
                if barcode in self.main_window.current_shipment.removed_items:
                    # Товар помечен как удаленный из поставки
                    needs_highlight = True
                    # Проверяем, полностью ли товар исчез из поставки или его количество уменьшилось
                    if barcode in getattr(self.main_window.current_shipment, 'partial_decrease_items', set()):
                        # Количество товара уменьшилось, но не до нуля - оранжевый цвет
                        is_full_removal = False
                    else:
                        # Товар полностью удален из поставки - красный цвет
                        is_full_removal = True
                    # Определяем, сколько товара нужно убрать из текущей коробки
                    removed_data = self.main_window.current_shipment.removed_items[barcode]
                    excess_qty_in_current_box = min(qty, removed_data['allocated_qty'])
                elif shipment_item and qty > shipment_item.total_qty:
                    # Количество в коробке превышает общее количество в поставке
                    needs_highlight = True
                    is_full_removal = True
                    excess_qty_in_current_box = qty - shipment_item.total_qty
                else:
                    # Проверяем, является ли товар "лишним" - т.е. общее распределенное количество
                    # для этого товара превышает новое общее количество в поставке
                    total_allocated_in_boxes = 0
                    for box in self.main_window.current_shipment.boxes:
                        if barcode in box.items:
                            total_allocated_in_boxes += box.items[barcode]
                    
                    if shipment_item and total_allocated_in_boxes > shipment_item.total_qty:
                        # Общее количество этого товара в коробках превышает новое общее количество в поставке
                        # Рассчитываем, сколько лишнего товара должно быть убрано из текущей коробки
                        excess_total = total_allocated_in_boxes - shipment_item.total_qty
                        excess_qty_in_current_box = min(qty, excess_total)
                        needs_highlight = True
                        is_full_removal = True
                
                if needs_highlight:
                    if is_full_removal:
                        # Полное удаление или превышение - красный цвет
                        bg_color = theme["conflict_exceed"]
                        text_color = theme["conflict_text"]
                    else:
                        # Частичное уменьшение - оранжевый цвет
                        bg_color = theme["partial_decrease"]
                        text_color = theme["partial_decrease_text"]
                    
                    qty_item.setBackground(bg_color)
                    qty_item.setForeground(text_color)
                    barcode_item.setBackground(bg_color)
                    barcode_item.setForeground(text_color)
                    sku_item.setBackground(bg_color)
                    sku_item.setForeground(text_color)
                self.main_window.current_box_table.setItem(row, 2, qty_item)
                
                # Устанавливаем высоту строк в таблице текущей коробки, подстраиваясь под размер шрифта
                font_height = self.main_window.current_box_table.fontMetrics().height()
                self.main_window.current_box_table.setRowHeight(row, max(1, font_height // 2))  # Уменьшаем высоту в два раза для компактности
        finally:
            self.main_window.current_box_table.setUpdatesEnabled(True)
            self.main_window.current_box_table.cellChanged.connect(self.main_window.on_box_cell_changed)
            
        # Восстанавливаем сохраненные пользовательские настройки ширины столбцов
        if (hasattr(self.main_window, 'box_columns_width') and 
            self.main_window.box_columns_width):
            try:
                widths = self.main_window.box_columns_width.split(",")
                for i, width_str in enumerate(widths):
                    if i < self.main_window.current_box_table.columnCount():
                        width = int(width_str)
                        # Устанавливаем ширину столбца только если она отличается от текущей
                        if self.main_window.current_box_table.columnWidth(i) != width:
                            self.main_window.current_box_table.setColumnWidth(i, width)
            except (ValueError, IndexError):
                # Если не удалось восстановить сохраненные ширины, используем авто-размер
                self.main_window.current_box_table.resizeColumnsToContents()
        else:
            # Если нет сохраненных настроек, используем авто-размер
            self.main_window.current_box_table.resizeColumnsToContents()
        # Устанавливаем фиксированный режим для вертикального заголовка, чтобы сохранить нашу высоту строк
        self.main_window.current_box_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

    def update_removed_items_table(self):
        if not self.main_window.current_shipment:
            self.main_window.removed_items_label.setVisible(False)
            self.main_window.removed_items_table.setVisible(False)
            return
        removed_items_count = len(self.main_window.current_shipment.removed_items)
        if removed_items_count > 0:
            self.main_window.removed_items_label.setVisible(True)
            self.main_window.removed_items_table.setVisible(True)
            self.main_window.removed_items_table.setRowCount(removed_items_count)
            theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])
            # Отключаем обновления таблицы во время заполнения для повышения производительности
            self.main_window.removed_items_table.setUpdatesEnabled(False)
            for row, (barcode, item_data) in enumerate(self.main_window.current_shipment.removed_items.items()):
                self.main_window.removed_items_table.setItem(row, 0, QTableWidgetItem(barcode))
                self.main_window.removed_items_table.setItem(row, 1, QTableWidgetItem(item_data['sku']))
                self.main_window.removed_items_table.setItem(row, 2, QTableWidgetItem(str(item_data['allocated_qty'])))
                for col in range(3):
                    item_widget = self.main_window.removed_items_table.item(row, col)
                    if item_widget:
                        item_widget.setBackground(theme["removed_from_shipment"])
                        item_widget.setForeground(theme["removed_text"])
                
                # Устанавливаем высоту строк в таблице удаленных товаров, подстраиваясь под размер шрифта
                font_height = self.main_window.removed_items_table.fontMetrics().height()
                self.main_window.removed_items_table.setRowHeight(row, max(1, font_height // 2))  # Уменьшаем высоту в два раза для компактности
        else:
            self.main_window.removed_items_label.setVisible(False)
            self.main_window.removed_items_table.setVisible(False)
            
        # Включаем обновления и обновляем размеры столбцов
        if hasattr(self.main_window, 'removed_items_table'):
            self.main_window.removed_items_table.setUpdatesEnabled(True)
            # Восстанавливаем сохраненные пользовательские настройки ширины столбцов
            # Для таблицы удаленных товаров используем те же настройки, что и для основной таблицы поставки
            if (hasattr(self.main_window, 'shipment_columns_width') and 
                self.main_window.shipment_columns_width):
                try:
                    widths = self.main_window.shipment_columns_width.split(",")
                    for i, width_str in enumerate(widths):
                        if i < self.main_window.removed_items_table.columnCount():
                            width = int(width_str)
                            # Устанавливаем ширину столбца только если она отличается от текущей
                            if self.main_window.removed_items_table.columnWidth(i) != width:
                                self.main_window.removed_items_table.setColumnWidth(i, width)
                except (ValueError, IndexError):
                    # Если не удалось восстановить сохраненные ширины, используем авто-размер
                    self.main_window.removed_items_table.resizeColumnsToContents()
            else:
                # Если нет сохраненных настроек, используем авто-размер
                self.main_window.removed_items_table.resizeColumnsToContents()
            # Устанавливаем фиксированный режим для вертикального заголовка, чтобы сохранить нашу высоту строк
            self.main_window.removed_items_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

    def update_group_shipment_summary(self, group_shipment):
        """Обновление сводки по групповой поставке"""
        total_items = 0
        allocated_items = 0
        article_count = 0

        for shipment in group_shipment.sub_shipments.values():
            for item in shipment.shipment_items.values():
                total_items += item.total_qty
                allocated_items += item.allocated_qty
                article_count += 1

        unique_articles = set()
        for shipment in group_shipment.sub_shipments.values():
            unique_articles.update(shipment.shipment_items.keys())

        self.main_window.shipment_table_label.setText(
            f"Группа '{group_shipment.group_name}': {len(group_shipment.sub_shipments)} поставок, "
            f"{len(unique_articles)} артикулов, {total_items} ед. (собрано {allocated_items})"
        )

    def reset_group_shipment_view(self):
        """Сброс таблиц при выходе из режима групповой поставки"""
        name_visible = getattr(self.main_window, 'name_column_visible', False)
        self.main_window.shipment_table.setColumnHidden(2, not name_visible)
        # Восстанавливаем стандартное количество колонок (7)
        if self.main_window.shipment_table.columnCount() != 7:
            self.main_window.shipment_table.setColumnCount(7)
            self.main_window.shipment_table.setHorizontalHeaderLabels(["Штрихкод", "Артикул", "Имя", "Всего", "Осталось", "Склад", ""])
        
        # Очищаем все виджеты кнопок из таблицы
        self.main_window.shipment_table.setRowCount(0)

    def update_group_shipment_boxes_table(self, group_shipment):
        """Обновление таблицы коробок для групповой поставки"""
        self.main_window.current_box_label.setText(f"Группа: {group_shipment.group_name}")
        self.main_window.current_box_table.setRowCount(0)

        theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])
        header_bg = theme.get("header_bg", QColor(245, 245, 247))
        header_text = theme.get("header_text", QColor(40, 40, 40))

        self.main_window.current_box_label.setStyleSheet(f"""
            color: {header_text.name()};
            font-weight: bold;
            font-size: {self.main_window.font_size}px;
            padding: 8px;
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 {header_bg.name()},
                stop: 1 {header_bg.lighter(105).name()});
            border: 1px solid {theme["button_border"].name()};
            border-radius: 6px;
        """)

    def update_group_shipment_items_table(self, group_shipment):
        """Обновление таблицы товаров для групповой поставки в формате Google Sheets"""
        try:
            self.main_window.shipment_table.cellChanged.disconnect(self.main_window.on_shipment_cell_changed)
        except (TypeError, RuntimeError):
            pass
        self.main_window.shipment_table.setSortingEnabled(False)
        
        # Явно очищаем все виджеты кнопок перед сбросом строк
        for row in range(self.main_window.shipment_table.rowCount()):
            for col in range(self.main_window.shipment_table.columnCount()):
                widget = self.main_window.shipment_table.cellWidget(row, col)
                if widget:
                    widget.deleteLater()
        
        self.main_window.shipment_table.setRowCount(0)
        self.main_window.shipment_table.setUpdatesEnabled(False)

        self.main_window.shipment_table.setColumnHidden(2, False)

        theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])

        # Собираем все уникальные штрихкоды и направления
        all_barcodes = set()
        directions = set()
        shipment_data = {}
        
        for sub_name, shipment in group_shipment.sub_shipments.items():
            display_name = getattr(shipment, 'display_name', sub_name.split('::')[-1] if '::' in sub_name else sub_name)
            directions.add((display_name, shipment))
            
            for barcode, item in shipment.shipment_items.items():
                all_barcodes.add(barcode)
                if barcode not in shipment_data:
                    shipment_data[barcode] = {
                        'sku': item.sku,
                        'total_qty': 0,
                        'allocated_qty': 0,
                        'by_direction': {}
                    }
                shipment_data[barcode]['by_direction'][display_name] = item.total_qty
                shipment_data[barcode]['total_qty'] += item.total_qty
                shipment_data[barcode]['allocated_qty'] += item.allocated_qty

        # Сортируем направления
        sorted_directions = sorted(directions, key=lambda x: x[0])
        
        # Создаём заголовки: Штрихкод, Артикул, Имя, Направления..., Всего, Собрало, Осталось
        num_direction_cols = len(sorted_directions)
        num_total_cols = 3 + num_direction_cols + 3  # штрихкод + артикул + имя + направления + всего + собрано + осталось
        
        self.main_window.shipment_table.setColumnCount(num_total_cols)
        
        # Разбиваем длинные названия на строки для компактности
        def split_header(text):
            if len(text) > 10:
                # Разбиваем по пробелам или дефисам
                parts = text.replace('-', ' ').split()
                if len(parts) > 1:
                    return '\n'.join(parts)
                # Или просто каждые 5 символов
                return '\n'.join([text[i:i+5] for i in range(0, len(text), 5)])
            return text
        
        headers = ["Штрихкод", "Артикул", "Имя"] + [split_header(d[0]) for d in sorted_directions] + ["Всего", "Собрано", "Осталось"]
        self.main_window.shipment_table.setHorizontalHeaderLabels(headers)
        
        # Устанавливаем минимальную ширину для колонок направлений (только цифры)
        header = self.main_window.shipment_table.horizontalHeader()
        for col_idx in range(3, 3 + num_direction_cols):
            header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Interactive)
            self.main_window.shipment_table.setColumnWidth(col_idx, 70)
        
        # Включаем перенос текста в заголовках
        header.setStyleSheet("QHeaderView::section { padding: 4px; }")

        # Заполняем данные
        row = 0
        for barcode in sorted(all_barcodes):
            data = shipment_data[barcode]
            self.main_window.shipment_table.insertRow(row)

            # Штрихкод
            barcode_item = QTableWidgetItem(barcode)
            self.main_window.shipment_table.setItem(row, 0, barcode_item)

            # Артикул
            sku_item = QTableWidgetItem(data['sku'])
            self.main_window.shipment_table.setItem(row, 1, sku_item)

            # Имя товара (из БД)
            try:
                from database import get_product_names_by_barcodes
                product_names = get_product_names_by_barcodes([barcode])
                name = product_names.get(barcode, "")
            except:
                name = ""
            name_item = QTableWidgetItem(name)
            self.main_window.shipment_table.setItem(row, 2, name_item)

            # Направления
            for col_idx, (dir_name, _) in enumerate(sorted_directions):
                qty = data['by_direction'].get(dir_name, 0)
                dir_item = QTableWidgetItem(str(qty) if qty > 0 else "")
                dir_item.setData(Qt.ItemDataRole.DisplayRole, qty)
                dir_item.setData(Qt.ItemDataRole.EditRole, qty)
                self.main_window.shipment_table.setItem(row, 3 + col_idx, dir_item)

            # Всего
            total_col = 3 + num_direction_cols
            total_item = QTableWidgetItem()
            total_item.setData(Qt.ItemDataRole.DisplayRole, data['total_qty'])
            total_item.setData(Qt.ItemDataRole.EditRole, data['total_qty'])
            self.main_window.shipment_table.setItem(row, total_col, total_item)

            # Собрало
            allocated_col = total_col + 1
            allocated_item = QTableWidgetItem()
            allocated_item.setData(Qt.ItemDataRole.DisplayRole, data['allocated_qty'])
            allocated_item.setData(Qt.ItemDataRole.EditRole, data['allocated_qty'])
            self.main_window.shipment_table.setItem(row, allocated_col, allocated_item)

            # Осталось
            remaining_col = allocated_col + 1
            remaining = data['total_qty'] - data['allocated_qty']
            remaining_item = QTableWidgetItem()
            remaining_item.setData(Qt.ItemDataRole.DisplayRole, remaining)
            remaining_item.setData(Qt.ItemDataRole.EditRole, remaining)
            self.main_window.shipment_table.setItem(row, remaining_col, remaining_item)

            # Применяем тему
            for col in range(num_total_cols):
                item_widget = self.main_window.shipment_table.item(row, col)
                if item_widget:
                    item_widget.setForeground(QColor(theme["text"].name()))

            row += 1

        self.main_window.shipment_table.setUpdatesEnabled(True)
        self.main_window.shipment_table.setSortingEnabled(True)

    def update_current_box_label(self):
        if not self.main_window.current_shipment or self.main_window.current_shipment.current_box_index < 0:
            self.main_window.current_box_label.setText("Коробка не выбрана")
            # Устанавливаем стиль, аналогичный заголовку таблицы поставки
            theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])
            # Используем правильные ключи для стиля заголовка таблицы
            header_bg = theme.get("header_bg", theme.get("table_bg", QColor(245, 245, 247)))
            header_text = theme.get("header_text", theme.get("text", QColor(40, 40, 40)))  # Исправлено: добавлен третий параметр
            
            self.main_window.current_box_label.setStyleSheet(f"""
 color: {header_text.name()};
 font-weight: bold;
 font-size: {self.main_window.font_size}px;
 padding: 8px;
 background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
     stop: 0 {header_bg.name()},
     stop: 1 {header_bg.lighter(105).name()});
 border: 1px solid {theme["button_border"].name()};
 border-radius: 6px;
 """)
        else:
            current_box = self.main_window.current_shipment.boxes[self.main_window.current_shipment.current_box_index]
            theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])
            self.main_window.current_box_label.setText(f"{current_box.box_id}")
            
            # Используем тот же стиль, что и для случая, когда коробка не выбрана
            header_bg = theme.get("header_bg", theme.get("table_bg", QColor(245, 245, 247)))
            header_text = theme.get("header_text", theme.get("text", QColor(40, 40, 40)))  # Исправлено: добавлен третий параметр
            
            self.main_window.current_box_label.setStyleSheet(f"""
 color: {header_text.name()};
 font-weight: bold;
 font-size: {self.main_window.font_size}px;
 padding: 8px;
 background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
     stop: 0 {header_bg.name()},
     stop: 1 {header_bg.lighter(105).name()});
 border: 1px solid {theme["button_border"].name()};
 border-radius: 6px;
 """)

        # Обновляем заголовок таблицы состава поставки
        if self.main_window.current_shipment:
            shipment_name = self.main_window.current_shipment.destination_name
            self.main_window.shipment_table_label.setText(f"Состав поставки: {shipment_name}")
        else:
            self.main_window.shipment_table_label.setText("Состав поставки:")
            
        # Устанавливаем стиль для заголовка таблицы поставки, чтобы он был одинаковым с меткой текущей коробки
        theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])
        # Используем правильные ключи для стиля заголовка таблицы
        header_bg = theme.get("header_bg", theme.get("table_bg", QColor(245, 245, 247)))
        header_text = theme.get("header_text", theme.get("text", QColor(40, 40, 40)))  # Исправлено: добавлен третий параметр
        
        self.main_window.shipment_table_label.setStyleSheet(f"""
 color: {header_text.name()};
 font-weight: bold;
 font-size: {self.main_window.font_size}px;
 padding: 8px;
 background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
     stop: 0 {header_bg.name()},
     stop: 1 {header_bg.lighter(105).name()});
 border: 1px solid {theme["button_border"].name()};
 border-radius: 6px;
 """)
            
        # Обновляем размер шрифта меток для лучшего отображения
        font = self.main_window.current_box_label.font()
        font.setPointSize(self.main_window.label_font_size)
        self.main_window.current_box_label.setFont(font)

        table_label_font = self.main_window.shipment_table_label.font()
        table_label_font.setPointSize(self.main_window.label_font_size)
        self.main_window.shipment_table_label.setFont(table_label_font)

    def _refresh_action_buttons_styles(self):
        """Обновляет стили кнопок '+' в таблице поставки"""
        if not hasattr(self.main_window, 'current_shipment') or not self.main_window.current_shipment:
            return

        theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])

        # Создаем словарь для быстрого поиска по barcode
        shipment_items_dict = {item.barcode: item for item in self.main_window.current_shipment.shipment_items.values()}

        # Отключаем обновления таблицы для повышения производительности
        self.main_window.shipment_table.setUpdatesEnabled(False)

        for row in range(self.main_window.shipment_table.rowCount()):
            item = self.main_window.shipment_table.item(row, 0)  # barcode item
            if item:
                barcode = item.text()

                # Получаем виджет с кнопкой из ячейки (столбец 5)
                action_widget = self.main_window.shipment_table.cellWidget(row, 5)

                # Получаем оставшееся количество
                shipment_item = shipment_items_dict.get(barcode)
                if shipment_item:
                    remaining_qty = shipment_item.remaining_qty
                    is_disabled = remaining_qty <= 0 or barcode in self.main_window.current_shipment.removed_items

                    # Если виджет существует, обновляем стиль кнопки
                    if action_widget and isinstance(action_widget, QWidget):
                        # Находим кнопку в виджете
                        add_btn = action_widget.findChild(QPushButton)
                        qty_edit = action_widget.findChild(QLineEdit)
                        if add_btn:
                            if is_disabled and add_btn.isEnabled():
                                add_btn.setEnabled(False)
                                if qty_edit:
                                    qty_edit.setEnabled(False)
                            elif not is_disabled and not add_btn.isEnabled():
                                add_btn.setEnabled(True)
                                if qty_edit:
                                    qty_edit.setEnabled(True)

                # Столбец с кнопками всегда видим
                self.main_window.shipment_table.setColumnHidden(6, False)

        # Включаем обновления таблицы
        self.main_window.shipment_table.setUpdatesEnabled(True)
                    
    def _recreate_action_buttons(self):
        """Создает кнопки 'Добавить всё' в таблице поставки"""
        if not hasattr(self.main_window, 'current_shipment') or not self.main_window.current_shipment:
            return
            
        theme = themes.THEMES.get(self.main_window.current_theme, themes.THEMES["Светлая"])
            
        # Получаем список элементов поставки
        shipment_items = list(self.main_window.current_shipment.shipment_items.values())
        
        # Отключаем обновления таблицы для повышения производительности
        self.main_window.shipment_table.setUpdatesEnabled(False)
            
        for row, item in enumerate(shipment_items):
            # Проверяем, есть ли уже кнопка в этой ячейке
            existing_widget = self.main_window.shipment_table.cellWidget(row, 5)
            
            # Если виджета нет или это не кнопка, создаем новую кнопку
            if not existing_widget or not isinstance(existing_widget, QPushButton):
                barcode = item.barcode
                remaining_qty = item.remaining_qty
                
                action_btn = QPushButton("+ Все")
                
                if remaining_qty <= 0 or barcode in self.main_window.current_shipment.removed_items:
                    action_btn.setEnabled(False)
                    action_btn.setStyleSheet(f"""
 QPushButton {{
     background: {theme["button_bg"].name()};
     color: {theme["button_text"].name()};
     border: 1px solid {theme["button_border"].name()};
     padding: 2px 6px;
     border-radius: 3px;
     font-weight: normal;
     font-size: {max(9, self.main_window.font_size - 1)}px;
     min-height: 8px;
     max-height: 18px;
 }}
 """)
                else:
                    action_btn.setEnabled(True)
                    action_btn.setStyleSheet(f"""
 QPushButton {{
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
         stop: 0 {theme["accent_success"].lighter(120).name()},
         stop: 0.5 {theme["accent_success"].name()},
         stop: 1 {theme["accent_success"].darker(120).name()});
     color: white;
     border: 1px solid {theme["accent_success"].darker(150).name()};
     padding: 2px 6px;
     border-radius: 3px;
     font-weight: bold;
     font-size: {max(9, self.main_window.font_size - 1)}px;
     min-height: 8px;
     max-height: 18px;
 }}
 QPushButton:hover {{
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
         stop: 0 {theme["accent_success"].lighter(140).name()},
         stop: 0.5 {theme["accent_success"].lighter(120).name()},
         stop: 1 {theme["accent_success"].name()});
 }}
 QPushButton:pressed {{
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
         stop: 0 {theme["accent_success"].darker(110).name()},
         stop: 0.5 {theme["accent_success"].darker(130).name()},
         stop: 1 {theme["accent_success"].darker(150).name()});
 }}
 """)
                
                action_btn.clicked.connect(lambda checked, bc=barcode: self.main_window.add_all_remaining_to_box_by_barcode(bc))
                self.main_window.shipment_table.setCellWidget(row, 5, action_btn)
                
                # Убедимся, что ячейка не редактируема (это важно)
                item_widget = self.main_window.shipment_table.item(row, 5)
                if item_widget:
                    item_widget.setFlags(item_widget.flags() & ~Qt.ItemFlag.ItemIsEditable)
            else:
                # Если кнопка уже существует, обновляем только её состояние и стиль
                barcode = item.barcode
                remaining_qty = item.remaining_qty
                
                is_disabled = remaining_qty <= 0 or barcode in self.main_window.current_shipment.removed_items
                is_enabled = not is_disabled
                
                if is_disabled and existing_widget.isEnabled():
                    existing_widget.setEnabled(False)
                    disabled_style = f"""
 QPushButton {{
     background: {theme["button_bg"].name()};
     color: {theme["button_text"].name()};
     border: 1px solid {theme["button_border"].name()};
     padding: 2px 6px;
     border-radius: 3px;
     font-weight: normal;
     font-size: {max(9, self.main_window.font_size - 1)}px;
     min-height: 8px;
     max-height: 18px;
 }}
 """
                    existing_widget.setStyleSheet(disabled_style)
                elif is_enabled and not existing_widget.isEnabled():
                    existing_widget.setEnabled(True)
                    enabled_style = f"""
 QPushButton {{
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
         stop: 0 {theme["accent_success"].lighter(120).name()},
         stop: 0.5 {theme["accent_success"].name()},
         stop: 1 {theme["accent_success"].darker(120).name()});
     color: white;
     border: 1px solid {theme["accent_success"].darker(150).name()};
     padding: 2px 6px;
     border-radius: 3px;
     font-weight: bold;
     font-size: {max(9, self.main_window.font_size - 1)}px;
     min-height: 8px;
     max-height: 18px;
 }}
 QPushButton:hover {{
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
         stop: 0 {theme["accent_success"].lighter(140).name()},
         stop: 0.5 {theme["accent_success"].lighter(120).name()},
         stop: 1 {theme["accent_success"].name()});
 }}
 QPushButton:pressed {{
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
         stop: 0 {theme["accent_success"].darker(110).name()},
         stop: 0.5 {theme["accent_success"].darker(130).name()},
         stop: 1 {theme["accent_success"].darker(150).name()});
 }}
 """
                    existing_widget.setStyleSheet(enabled_style)
        
        # Включаем обновления таблицы
        self.main_window.shipment_table.setUpdatesEnabled(True)
                    
    def update_shipment_table_headers(self, moysklad_enabled=True, stock_column_visible=True):
        """Обновляет заголовки таблицы в зависимости от состояния интеграции МойСклад
        
        Args:
            moysklad_enabled: Включена ли интеграция с МойСклад
            stock_column_visible: Должен ли быть виден столбец "На складе"
        """
        # Устанавливаем видимость столбца "Наименование" в соответствии с настройками пользователя
        if hasattr(self.main_window, 'name_display_checkbox') and self.main_window.name_display_checkbox:
            name_visible = self.main_window.name_display_checkbox.isChecked()
        else:
            # Если чекбокс не инициализирован, используем сохраненную настройку
            if self.main_window.current_user:
                user_settings = database.get_user_settings(self.main_window.current_user)
                name_visible = user_settings.get('name_column_visible', False) if user_settings else False
            else:
                name_visible = False

        if moysklad_enabled:
            # Устанавливаем полные заголовки с текстовыми названиями
            # Порядок: Штрихкод | Артикул | Имя | Всего | Осталось | Склад | (пусто)
            self.main_window.shipment_table.setHorizontalHeaderLabels(["Штрихкод", "Артикул", "Имя", "Всего", "Осталось", "Склад", ""])

            # Устанавливаем видимость столбца "Наименование"
            self.main_window.shipment_table.setColumnHidden(2, not name_visible)
            # Показываем/скрываем столбец "На складе" в соответствии с настройкой пользователя
            self.main_window.shipment_table.setColumnHidden(5, not stock_column_visible)
            # Показываем столбец с кнопками - ВСЕГДА
            self.main_window.shipment_table.setColumnHidden(6, False)
            self.main_window.shipment_table.setColumnWidth(6, 85)
        else:
            # Устанавливаем заголовки без столбца "Склад"
            # Порядок: Штрихкод | Артикул | Имя | Всего | Осталось | (пусто) | (пусто)
            self.main_window.shipment_table.setHorizontalHeaderLabels(["Штрихкод", "Артикул", "Имя", "Всего", "Осталось", "", ""])

            # Устанавливаем видимость столбца "Наименование"
            self.main_window.shipment_table.setColumnHidden(2, not name_visible)
            # Скрываем столбец "На складе" (интеграция выключена)
            self.main_window.shipment_table.setColumnHidden(5, True)
            # Показываем столбец с кнопками - ВСЕГДА
            self.main_window.shipment_table.setColumnHidden(6, False)
            self.main_window.shipment_table.setColumnWidth(6, 85)

    def check_completion(self):
        if not self.main_window.current_shipment:
            return
        current_name = self.main_window.current_shipment.destination_name
        is_completed = self.main_window.current_shipment.is_completed() and not self.main_window.current_shipment.has_discrepancies()
        was_completed = self.main_window.last_completed_state.get(current_name, False)
        if not was_completed and is_completed:
            self.main_window.statusBar().showMessage("🎉 Поставка завершена!", 5000)
        self.main_window.last_completed_state[current_name] = is_completed
