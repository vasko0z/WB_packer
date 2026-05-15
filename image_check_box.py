# image_check_box.py
"""Кастомный чекбокс с изображениями check_on.png и check_off.png"""
import logging
from pathlib import Path
from PyQt6.QtCore import QSize, Qt, QRect
from PyQt6.QtGui import QIcon, QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QCheckBox, QApplication
from PyQt6.QtGui import QPalette
import config


class ImageCheckBox(QCheckBox):
    """Кастомный чекбокс с изображениями check_on.png и check_off.png"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.check_on_pixmap = None
        self.check_off_pixmap = None
        self._text_color = None  # Сохраняем цвет текста как атрибут
        self._load_images()

        # Устанавливаем атрибут для корректного отображения цвета текста
        self.setAttribute(Qt.WidgetAttribute.WA_SetPalette, True)

        # Полностью скрываем стандартный индикатор через размер иконки
        self.setIconSize(QSize(0, 0))
        self.setIcon(QIcon())

        # Отключаем стилизацию индикатора через CSS для кастомных чекбоксов
        # Это предотвращает конфликт между CSS стилями и кастомной отрисовкой
        self.setStyleSheet("""
            QCheckBox::indicator {
                image: none;
                width: 0px;
                height: 0px;
            }
        """)

    def _load_images(self):
        """Загрузка изображений для состояний вкл/выкл"""
        try:
            check_on_path = config.get_resource_path(Path("Res") / "check_on.png")
            check_off_path = config.get_resource_path(Path("Res") / "check_off.png")

            # Логирование для отладки путей в скомпилированном приложении
            logging.debug(f"Пути к изображениям чекбокса: check_on={check_on_path}, check_off={check_off_path}")
            logging.debug(f"Файлы существуют: check_on={check_on_path.exists()}, check_off={check_off_path.exists()}")

            # Проверяем существование файлов перед загрузкой
            if not check_on_path.exists():
                logging.error(f"Файл check_on.png не найден по пути: {check_on_path}")
            if not check_off_path.exists():
                logging.error(f"Файл check_off.png не найден по пути: {check_off_path}")

            # Загружаем изображения без масштабирования для сохранения качества
            self.check_on_pixmap = QPixmap(str(check_on_path))
            self.check_off_pixmap = QPixmap(str(check_off_path))

            # Проверяем успешность загрузки
            if self.check_on_pixmap.isNull():
                logging.error("Не удалось загрузить check_on.png - пустой QPixmap")
            if self.check_off_pixmap.isNull():
                logging.error("Не удалось загрузить check_off.png - пустой QPixmap")

        except Exception as e:
            logging.error(f"Ошибка загрузки изображений чекбокса: {e}", exc_info=True)

    def paintEvent(self, event):
        """Переопределяем отрисовку для отображения кастомной иконки"""
        # Создаем painter для кастомной отрисовки
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Рисуем кастомную иконку
        if self.check_on_pixmap and self.check_off_pixmap:
            pixmap = self.check_on_pixmap if self.isChecked() else self.check_off_pixmap

            # Вычисляем позицию для иконки (слева, центрируем по вертикали)
            icon_size = 28  # Желаемый размер иконки
            scale = min(icon_size / pixmap.width(), icon_size / pixmap.height()) if pixmap.width() > 0 and pixmap.height() > 0 else 1
            scaled_width = int(pixmap.width() * scale)
            scaled_height = int(pixmap.height() * scale)
            
            scaled_pixmap = pixmap.scaled(scaled_width, scaled_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            # Вычисляем позицию для иконки (слева, центрируем по вертикали)
            icon_x = 2
            # Учитываем базовую линию шрифта для лучшего выравнивания
            text_height = self.fontMetrics().height()
            # Центрируем иконку относительно текста
            icon_y = (self.height() - text_height) // 2 + (text_height - scaled_height) // 2
            icon_y = max(0, icon_y)

            painter.drawPixmap(icon_x, icon_y, scaled_pixmap)

        # Рисуем текст со смещением для иконки
        if self.text():
            # Отступ справа от иконки (2 + 28 + 6)
            text_x = 36
            # Используем базовую линию шрифта для правильного позиционирования текста
            text_y = (self.height() + self.fontMetrics().ascent()) // 2

            # Получаем цвет текста - используем сохранённый цвет или из палитры
            if self._text_color is not None:
                text_color = self._text_color
            else:
                text_color = self.palette().color(QPalette.ColorRole.WindowText)
            painter.setPen(text_color)

            # Рисуем текст с правильным позиционированием
            painter.drawText(text_x, text_y, self.text())

        painter.end()

    def sizeHint(self):
        """Возвращает рекомендуемый размер виджета"""
        if self.text():
            # Ширина иконки (30) + отступ (6) + ширина текста + запас (10)
            text_width = self.fontMetrics().horizontalAdvance(self.text())
            return QSize(46 + text_width, max(32, self.fontMetrics().height() + 8))
        return QSize(32, 32)

    def setTextColor(self, color):
        """Установить цвет текста"""
        from PyQt6.QtGui import QPalette

        if isinstance(color, str):
            color = QColor(color)
        
        # Сохраняем цвет как атрибут для использования в paintEvent
        self._text_color = color
        
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, color)
        palette.setColor(QPalette.ColorRole.Text, color)
        palette.setColor(QPalette.ColorRole.ButtonText, color)
        self.setPalette(palette)
        self.update()
