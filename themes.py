# themes.py
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import Qt

THEMES = {
    "Светлая": {
        "app": "light",
        "table_bg": QColor(255, 255, 255),
        "text": QColor(40, 40, 40),
        "highlight": QColor(245, 245, 245),  # Серый цвет для чередования строк
        "shipment_remaining_ok": QColor(220, 245, 220),
        "shipment_remaining_partial": QColor(255, 250, 200),
        "shipment_text_ok": QColor(0, 100, 0),
        "shipment_text_partial": QColor(102, 102, 0),
        "conflict_exceed": QColor(255, 220, 220),
        "conflict_missing": QColor(255, 200, 200),
        "conflict_text": QColor(180, 0, 0),
        "partial_decrease": QColor(255, 215, 170),  # Оранжевый оттенок для частичного уменьшения
        "partial_decrease_text": QColor(160, 100, 0),  # Темно-оранжевый текст
        "removed_from_shipment": QColor(255, 230, 230),
        "removed_text": QColor(150, 0, 0),
        "current_shipment_bg": QColor(235, 245, 255),
        "current_box_bg": QColor(235, 245, 255),
        "current_indicator": QColor(65, 105, 225),
        "window_bg": QColor(245, 245, 247),
        "window_text": QColor(40, 40, 40),
        "base_bg": QColor(255, 255, 255),
        "base_text": QColor(40, 40, 40),
        "button_bg": QColor(240, 240, 245),
        "button_text": QColor(40, 40, 40),
        "button_border": QColor(200, 200, 210),
        "input_bg": QColor(255, 255, 255),
        "input_text": QColor(40, 40, 40),
        "input_border": QColor(200, 200, 210),
        "header_bg": QColor(230, 235, 245),
        "header_text": QColor(50, 50, 50),
        "accent_primary": QColor(50, 180, 80),
        "accent_success": QColor(50, 180, 80),
        "accent_warning": QColor(255, 165, 0),
        "accent_danger": QColor(220, 80, 80),
    },
    "Тёмная": {
        "app": "dark",
        "table_bg": QColor(45, 45, 55),
        "text": QColor(230, 230, 235),
        "highlight": QColor(55, 55, 65),  # Более светлый серый для чередования строк
        "shipment_remaining_ok": QColor(40, 80, 50),
        "shipment_remaining_partial": QColor(80, 80, 40),
        "shipment_text_ok": QColor(160, 255, 160),
        "shipment_text_partial": QColor(255, 255, 160),
        "conflict_exceed": QColor(80, 40, 40),
        "conflict_missing": QColor(70, 35, 35),
        "conflict_text": QColor(255, 160, 160),
        "partial_decrease": QColor(120, 80, 40),  # Темно-оранжевый для темной темы
        "partial_decrease_text": QColor(255, 200, 120),  # Светло-оранжевый текст
        "removed_from_shipment": QColor(70, 30, 30),
        "removed_text": QColor(255, 140, 140),
        "current_shipment_bg": QColor(50, 70, 100),
        "current_box_bg": QColor(50, 70, 100),
        "current_indicator": QColor(80, 120, 220),
        "window_bg": QColor(35, 35, 45),
        "window_text": QColor(230, 230, 235),
        "base_bg": QColor(40, 40, 50),
        "base_text": QColor(230, 230, 235),
        "button_bg": QColor(60, 60, 75),
        "button_text": QColor(230, 230, 235),
        "button_border": QColor(80, 80, 100),
        "input_bg": QColor(50, 50, 65),
        "input_text": QColor(230, 230, 235),
        "input_border": QColor(80, 80, 100),
        "header_bg": QColor(70, 75, 90),
        "header_text": QColor(240, 240, 245),
        "accent_primary": QColor(40, 160, 70),
        "accent_success": QColor(60, 180, 100),  # Более темный зеленый для темной темы
        "accent_warning": QColor(255, 185, 60),
        "accent_danger": QColor(255, 100, 100),
        "current_shipment_bg": QColor(25, 100, 50),  # Более темный зеленый для текущей поставки в темной теме
    },
    "macOS": {
        "app": "light",
        "table_bg": QColor(255, 255, 255),
        "text": QColor(30, 30, 30),
        "highlight": QColor(200, 220, 255),
        "shipment_remaining_ok": QColor(220, 245, 220),
        "shipment_remaining_partial": QColor(255, 250, 200),
        "shipment_text_ok": QColor(0, 100, 0),
        "shipment_text_partial": QColor(102, 102, 0),
        "conflict_exceed": QColor(255, 220, 220),
        "conflict_missing": QColor(255, 200, 200),
        "conflict_text": QColor(180, 0, 0),
        "partial_decrease": QColor(255, 215, 170),
        "partial_decrease_text": QColor(160, 100, 0),
        "removed_from_shipment": QColor(255, 230, 230),
        "removed_text": QColor(150, 0, 0),
        "current_shipment_bg": QColor(235, 245, 255),
        "current_box_bg": QColor(235, 245, 255),
        "current_indicator": QColor(0, 122, 255),
        "window_bg": QColor(236, 236, 240),
        "window_text": QColor(30, 30, 30),
        "base_bg": QColor(255, 255, 255),
        "base_text": QColor(30, 30, 30),
        "button_bg": QColor(255, 255, 255),
        "button_text": QColor(30, 30, 30),
        "button_border": QColor(200, 200, 205),
        "input_bg": QColor(255, 255, 255),
        "input_text": QColor(30, 30, 30),
        "input_border": QColor(200, 200, 205),
        "header_bg": QColor(245, 245, 247),
        "header_text": QColor(30, 30, 30),
        "accent_primary": QColor(0, 122, 255),
        "accent_success": QColor(52, 199, 89),
        "accent_warning": QColor(255, 149, 0),
        "accent_danger": QColor(255, 59, 48),
    }
}

def apply_theme(app, theme_name):
    theme = THEMES.get(theme_name, THEMES["Светлая"])
    palette = QPalette()
    
    if theme["app"] == "dark":
        palette.setColor(QPalette.ColorRole.Window, theme["window_bg"])
        palette.setColor(QPalette.ColorRole.WindowText, theme["window_text"])
        palette.setColor(QPalette.ColorRole.Base, theme["base_bg"])
        palette.setColor(QPalette.ColorRole.AlternateBase, theme["window_bg"])
        palette.setColor(QPalette.ColorRole.ToolTipBase, theme["base_bg"])
        palette.setColor(QPalette.ColorRole.ToolTipText, theme["window_text"])
        palette.setColor(QPalette.ColorRole.Text, theme["base_text"])
        palette.setColor(QPalette.ColorRole.Button, theme["button_bg"])
        palette.setColor(QPalette.ColorRole.ButtonText, theme["button_text"])
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, theme["accent_primary"])
        palette.setColor(QPalette.ColorRole.Highlight, theme["accent_primary"])
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        
        app.setPalette(palette)
        app.setStyleSheet(f"""
 QMainWindow, QWidget, QDialog {{
    background-color: {theme["window_bg"].name()};
    color: {theme["window_text"].name()};
    font-family: "Segoe UI", "Arial", sans-serif;
}}

/* Явное указание цвета текста для чекбоксов */
QCheckBox {{
    color: {theme["window_text"].name()};
    background-color: {theme["window_bg"].name()};
}}

/* Стили для стрелок разворачивания в дереве (темная тема) */
QTreeView::indicator:closed,
QTreeWidget::indicator:closed {{
    width: 16px;
    height: 16px;
    image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M6 4 L10 8 L6 12 Z" fill="{theme["window_text"].name()}"/></svg>');
}}

QTreeView::indicator:open,
QTreeWidget::indicator:open {{
    width: 16px;
    height: 16px;
    image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M4 6 L8 10 L12 6 Z" fill="{theme["window_text"].name()}"/></svg>');
}}

QTreeView::indicator:closed:hover,
QTreeWidget::indicator:closed:hover,
QTreeView::indicator:open:hover,
QTreeWidget::indicator:open:hover {{
    image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M6 4 L10 8 L6 12 Z" fill="{theme["accent_primary"].name()}"/></svg>');
}}

QPushButton {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["button_bg"].lighter(115).name()},
        stop: 0.5 {theme["button_bg"].name()},
        stop: 1 {theme["button_bg"].darker(110).name()});
    color: {theme["button_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    min-height: 24px;
}}
QPushButton:hover {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["button_bg"].lighter(125).name()},
        stop: 0.5 {theme["button_bg"].lighter(115).name()},
        stop: 1 {theme["button_bg"].name()});
    border: 1px solid {theme["accent_primary"].name()};
}}
QPushButton:pressed {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["button_bg"].darker(110).name()},
        stop: 0.5 {theme["button_bg"].darker(120).name()},
        stop: 1 {theme["button_bg"].darker(130).name()});
    padding: 9px 15px 7px 17px;
}}
QPushButton:disabled {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["button_bg"].darker(150).name()},
        stop: 1 {theme["button_bg"].darker(160).name()});
    color: {theme["button_text"].darker(150).name()};
    border: 1px solid {theme["button_border"].darker(130).name()};
}}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {theme["input_bg"].name()};
    color: {theme["input_text"].name()};
    border: 1px solid {theme["input_border"].name()};
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 14px;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {theme["accent_primary"].name()};
    background-color: {theme["input_bg"].lighter(105).name()};
}}
QTableWidget {{
    background-color: {theme["table_bg"].name()};
    color: {theme["text"].name()};
    gridline-color: transparent;
    border: none;
    border-radius: 0px;
    alternate-background-color: {theme["highlight"].name()};
}}
QTableWidget::item {{
    border: none;
    padding: 4px;
}}
QTableWidget::item:selected {{
    background-color: {theme["highlight"].name()};
    color: {theme["text"].name()};
}}
/* Стили для уголка таблицы (левая верхняя ячейка) */
QTableCornerButton::section {{
    background-color: {theme["header_bg"].name()};
    border: none;
}}
QHeaderView::section {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["header_bg"].lighter(110).name()},
        stop: 1 {theme["header_bg"].name()});
    color: {theme["header_text"].name()};
    padding: 8px;
    border: none;
    font-weight: 600;
    font-size: 13px;
}}
QTreeWidget {{
    background-color: {theme["base_bg"].name()};
    color: {theme["base_text"].name()};
    border: none;
    border-radius: 0px;
    outline: 0;
}}
QTreeWidget::item {{
    border: 1px solid transparent;
    border-radius: 4px;
    margin: 2px;
    padding: 2px;
}}
QTreeWidget::item:hover {{
    background-color: {theme["highlight"].name()};
}}
QTreeWidget::item:selected {{
    background-color: {theme["accent_primary"].name()};
    color: white;
}}
QProgressBar {{
    border: 1px solid {theme["button_border"].name()};
    border-radius: 4px;
    text-align: center;
    background-color: {theme["button_bg"].name()};
    color: {theme["button_text"].name()};
}}
QProgressBar::chunk {{
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 {theme["accent_success"].darker(120).name()},
        stop: 1 {theme["accent_success"].name()});
    border-radius: 3px;
}}
QMenu {{
    background-color: {theme["base_bg"].name()};
    color: {theme["base_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    border-radius: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 24px;
    border-radius: 2px;
}}
QMenu::item:selected {{
    background-color: {theme["accent_primary"].name()};
    color: white;
}}
QMenuBar {{
    background-color: {theme["window_bg"].name()};
    color: {theme["window_text"].name()};
}}
QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {theme["accent_primary"].name()};
    color: white;
}}
QLabel {{
    color: {theme["window_text"].name()};
}}
QGroupBox {{
    color: {theme["window_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    border-radius: 6px;
    margin-top: 1ex;
    padding-top: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px 0 8px;
    background-color: {theme["window_bg"].name()};
}}
QSpinBox, QComboBox {{
    background-color: {theme["input_bg"].name()};
    color: {theme["input_text"].name()};
    border: 1px solid {theme["input_border"].name()};
    padding: 4px 6px;
    border-radius: 4px;
}}
QSpinBox:focus, QComboBox:focus {{
    border: 2px solid {theme["accent_primary"].name()};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 1px solid {theme["input_border"].name()};
    background-color: {theme["button_bg"].name()};
    width: 16px;
    height: 16px;
}}
QComboBox QAbstractItemView {{
    background-color: {theme["base_bg"].name()};
    color: {theme["base_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    selection-background-color: {theme["accent_primary"].name()};
}}
QCheckBox {{
    spacing: 8px;
    color: {theme["window_text"].name()};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {theme["input_border"].name()};
    border-radius: 4px;
    background: {theme["input_bg"].name()};
}}
QCheckBox::indicator:hover {{
    border: 2px solid {theme["accent_primary"].name()};
}}
QCheckBox::indicator:checked {{
    background: {theme["accent_primary"].name()};
    border: 2px solid {theme["accent_primary"].name()};
    image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="white" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>');
}}
QCheckBox::indicator:disabled {{
    background: {theme["button_bg"].darker(120).name()};
    border-color: {theme["button_border"].name()};
}}
QSplitter::handle {{
    background-color: transparent;
    margin: 0px;
}}
QSplitter::handle:horizontal {{
    width: 10px;  /* Увеличенный отступ между блоками */
}}
QSplitter::handle:vertical {{
    height: 10px;  /* Увеличенный отступ между блоками */
}}
QSplitter::handle:hover {{
    background-color: transparent;
}}
QStatusBar {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["header_bg"].name()},
        stop: 1 {theme["button_bg"].name()});
    color: {theme["header_text"].name()};
    border-top: none;
}}
""")
    elif theme_name == "macOS":
        palette.setColor(QPalette.ColorRole.Window, theme["window_bg"])
        palette.setColor(QPalette.ColorRole.WindowText, theme["window_text"])
        palette.setColor(QPalette.ColorRole.Base, theme["base_bg"])
        palette.setColor(QPalette.ColorRole.AlternateBase, theme["window_bg"])
        palette.setColor(QPalette.ColorRole.ToolTipBase, theme["base_bg"])
        palette.setColor(QPalette.ColorRole.ToolTipText, theme["window_text"])
        palette.setColor(QPalette.ColorRole.Text, theme["base_text"])
        palette.setColor(QPalette.ColorRole.Button, theme["button_bg"])
        palette.setColor(QPalette.ColorRole.ButtonText, theme["button_text"])
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, theme["accent_primary"])
        palette.setColor(QPalette.ColorRole.Highlight, theme["accent_primary"])
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        
        app.setPalette(palette)
        app.setStyleSheet(f"""
QMainWindow, QWidget, QDialog {{
    background-color: {theme["window_bg"].name()};
    color: {theme["window_text"].name()};
    font-family: "SF Pro Display", "San Francisco", "Segoe UI", "Arial", sans-serif;
}}

/* macOS-style rounded corners for various widgets */
QPushButton {{
    background-color: {theme["button_bg"].name()};
    color: {theme["button_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 500;
    min-height: 24px;
    font-family: "SF Pro Text", "San Francisco", "Segoe UI", sans-serif;
}}
QPushButton:hover {{
    background-color: {theme["button_bg"].lighter(102).name()};
    border: 1px solid {theme["accent_primary"].name()};
}}
QPushButton:pressed {{
    background-color: {theme["button_bg"].darker(105).name()};
    border: 1px solid {theme["accent_primary"].darker(120).name()};
}}
QPushButton:disabled {{
    background-color: {theme["button_bg"].darker(110).name()};
    color: {theme["button_text"].darker(150).name()};
    border: 1px solid {theme["button_border"].darker(120).name()};
}}

/* macOS-style vibrant buttons */
QPushButton[vibrant="true"] {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["accent_primary"].lighter(120).name()},
        stop: 1 {theme["accent_primary"].name()});
    color: white;
    border: 1px solid {theme["accent_primary"].darker(130).name()};
    font-weight: 600;
}}
QPushButton[vibrant="true"]:hover {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["accent_primary"].lighter(130).name()},
        stop: 1 {theme["accent_primary"].lighter(110).name()});
}}
QPushButton[vibrant="true"]:pressed {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["accent_primary"].darker(110).name()},
        stop: 1 {theme["accent_primary"].darker(120).name()});
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {theme["input_bg"].name()};
    color: {theme["input_text"].name()};
    border: 1px solid {theme["input_border"].name()};
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 14px;
    font-family: "SF Pro Text", "San Francisco", "Segoe UI", sans-serif;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {theme["accent_primary"].name()};
    background-color: {theme["input_bg"].name()};
}}

QTableWidget {{
    background-color: {theme["table_bg"].name()};
    color: {theme["text"].name()};
    gridline-color: transparent;
    border: none;
    border-radius: 8px;
    alternate-background-color: {theme["highlight"].name()};
}}
QTableWidget::item {{
    border: none;
    padding: 6px;
}}
QTableWidget::item:selected {{
    background-color: {theme["highlight"].name()};
    color: {theme["text"].name()};
    border-radius: 4px;
}}

QHeaderView::section {{
    background-color: {theme["header_bg"].name()};
    color: {theme["header_text"].name()};
    padding: 10px 8px;
    border: none;
    font-weight: 600;
    font-size: 13px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}

QTreeWidget {{
    background-color: {theme["base_bg"].name()};
    color: {theme["base_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    border-radius: 8px;
    outline: 0;
}}
QTreeWidget::item {{
    border: 1px solid transparent;
    border-radius: 6px;
    margin: 2px;
    padding: 4px;
}}
QTreeWidget::item:hover {{
    background-color: {theme["highlight"].name()};
}}
QTreeWidget::item:selected {{
    background-color: {theme["accent_primary"].name()};
    color: white;
}}

QProgressBar {{
    border: 1px solid {theme["button_border"].name()};
    border-radius: 6px;
    text-align: center;
    background-color: {theme["button_bg"].name()};
    color: {theme["button_text"].name()};
}}
QProgressBar::chunk {{
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 {theme["accent_success"].darker(110).name()},
        stop: 1 {theme["accent_success"].name()});
    border-radius: 5px;
}}

QMenu {{
    background-color: {theme["base_bg"].name()};
    color: {theme["base_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 8px 24px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {theme["accent_primary"].name()};
    color: white;
}}

QMenuBar {{
    background-color: {theme["window_bg"].name()};
    color: {theme["window_text"].name()};
    border-bottom: 1px solid {theme["button_border"].name()};
}}
QMenuBar::item {{
    padding: 8px 16px;
    border-radius: 6px;
}}
QMenuBar::item:selected {{
    background-color: {theme["accent_primary"].name()};
    color: white;
}}

QLabel {{
    color: {theme["window_text"].name()};
    font-family: "SF Pro Text", "San Francisco", "Segoe UI", sans-serif;
}}

QGroupBox {{
    color: {theme["window_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    border-radius: 8px;
    margin-top: 1ex;
    padding-top: 16px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 12px 0 12px;
    background-color: {theme["window_bg"].name()};
}}

QSpinBox, QComboBox {{
    background-color: {theme["input_bg"].name()};
    color: {theme["input_text"].name()};
    border: 1px solid {theme["input_border"].name()};
    padding: 6px 8px;
    border-radius: 6px;
}}
QSpinBox:focus, QComboBox:focus {{
    border: 2px solid {theme["accent_primary"].name()};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
    border-left: 1px solid {theme["input_border"].name()};
}}
QComboBox QAbstractItemView {{
    background-color: {theme["base_bg"].name()};
    color: {theme["base_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    border-radius: 6px;
    selection-background-color: {theme["accent_primary"].name()};
}}

QCheckBox {{
    spacing: 10px;
    color: {theme["window_text"].name()};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {theme["input_border"].name()};
    border-radius: 4px;
    background: {theme["input_bg"].name()};
}}
QCheckBox::indicator:hover {{
    border: 2px solid {theme["accent_primary"].name()};
}}
QCheckBox::indicator:checked {{
    background: {theme["accent_primary"].name()};
    border: 2px solid {theme["accent_primary"].name()};
    image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="white" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>');
}}

QSplitter::handle {{
    background-color: transparent;
    margin: 0px;
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

QStatusBar {{
    background-color: {theme["window_bg"].name()};
    color: {theme["window_text"].name()};
    border-top: 1px solid {theme["button_border"].name()};
}}
""")
    else:
        palette.setColor(QPalette.ColorRole.Window, theme["window_bg"])
        palette.setColor(QPalette.ColorRole.WindowText, theme["window_text"])
        palette.setColor(QPalette.ColorRole.Base, theme["base_bg"])
        palette.setColor(QPalette.ColorRole.AlternateBase, theme["window_bg"])
        palette.setColor(QPalette.ColorRole.ToolTipBase, theme["base_bg"])
        palette.setColor(QPalette.ColorRole.ToolTipText, theme["window_text"])
        palette.setColor(QPalette.ColorRole.Text, theme["base_text"])
        palette.setColor(QPalette.ColorRole.Button, theme["button_bg"])
        palette.setColor(QPalette.ColorRole.ButtonText, theme["button_text"])
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, theme["accent_primary"])
        palette.setColor(QPalette.ColorRole.Highlight, theme["accent_primary"])
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        
        app.setPalette(palette)
        app.setStyleSheet(f"""
 QMainWindow, QWidget, QDialog {{
    background-color: {theme["window_bg"].name()};
    color: {theme["window_text"].name()};
    font-family: "Segoe UI", "Arial", sans-serif;
}}

/* Стили для стрелок разворачивания в дереве (светлая тема) */
QTreeView::indicator:closed,
QTreeWidget::indicator:closed {{
    width: 16px;
    height: 16px;
    image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M6 4 L10 8 L6 12 Z" fill="{theme["window_text"].name()}"/></svg>');
}}

QTreeView::indicator:open,
QTreeWidget::indicator:open {{
    width: 16px;
    height: 16px;
    image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M4 6 L8 10 L12 6 Z" fill="{theme["window_text"].name()}"/></svg>');
}}

QTreeView::indicator:closed:hover,
QTreeWidget::indicator:closed:hover,
QTreeView::indicator:open:hover,
QTreeWidget::indicator:open:hover {{
    image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M6 4 L10 8 L6 12 Z" fill="{theme["accent_primary"].name()}"/></svg>');
}}

QPushButton {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["button_bg"].lighter(105).name()},
        stop: 0.5 {theme["button_bg"].name()},
        stop: 1 {theme["button_bg"].darker(105).name()});
    color: {theme["button_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    min-height: 24px;
}}
QPushButton:hover {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["button_bg"].lighter(110).name()},
        stop: 0.5 {theme["button_bg"].lighter(105).name()},
        stop: 1 {theme["button_bg"].name()});
    border: 1px solid {theme["accent_primary"].name()};
}}
QPushButton:pressed {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["button_bg"].darker(105).name()},
        stop: 0.5 {theme["button_bg"].darker(110).name()},
        stop: 1 {theme["button_bg"].darker(115).name()});
    padding: 9px 15px 7px 17px;
}}
QPushButton:disabled {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["button_bg"].lighter(120).name()},
        stop: 1 {theme["button_bg"].lighter(130).name()});
    color: {theme["button_text"].lighter(150).name()};
    border: 1px solid {theme["button_border"].lighter(120).name()};
}}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {theme["input_bg"].name()};
    color: {theme["input_text"].name()};
    border: 1px solid {theme["input_border"].name()};
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 14px;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {theme["accent_primary"].name()};
    background-color: {theme["input_bg"].darker(102).name()};
}}
QTableWidget {{
    background-color: {theme["table_bg"].name()};
    color: {theme["text"].name()};
    gridline-color: transparent;
    border: none;
    border-radius: 0px;
    alternate-background-color: {theme["highlight"].name()};
}}
QTableWidget::item {{
    border: none;
    padding: 4px;
}}
QTableWidget::item:selected {{
    background-color: {theme["highlight"].name()};
    color: {theme["text"].name()};
}}
/* Стили для уголка таблицы (левая верхняя ячейка) */
QTableCornerButton::section {{
    background-color: {theme["header_bg"].name()};
    border: none;
}}
QHeaderView::section {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["header_bg"].lighter(105).name()},
        stop: 1 {theme["header_bg"].name()});
    color: {theme["header_text"].name()};
    padding: 8px;
    border: none;
    font-weight: 600;
    font-size: 13px;
}}
QTreeWidget {{
    background-color: {theme["base_bg"].name()};
    color: {theme["base_text"].name()};
    border: none;
    border-radius: 0px;
    outline: 0;
}}
QTreeWidget::item {{
    border: 1px solid transparent;
    border-radius: 4px;
    margin: 2px;
    padding: 2px;
}}
QTreeWidget::item:hover {{
    background-color: {theme["highlight"].name()};
}}
QTreeWidget::item:selected {{
    background-color: {theme["accent_primary"].name()};
    color: white;
}}
QProgressBar {{
    border: 1px solid {theme["button_border"].name()};
    border-radius: 4px;
    text-align: center;
    background-color: {theme["button_bg"].name()};
    color: {theme["button_text"].name()};
}}
QProgressBar::chunk {{
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 {theme["accent_success"].darker(120).name()},
        stop: 1 {theme["accent_success"].name()});
    border-radius: 3px;
}}
QMenu {{
    background-color: {theme["base_bg"].name()};
    color: {theme["base_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    border-radius: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 24px;
    border-radius: 2px;
}}
QMenu::item:selected {{
    background-color: {theme["accent_primary"].name()};
    color: white;
}}
QMenuBar {{
    background-color: {theme["window_bg"].name()};
    color: {theme["window_text"].name()};
}}
QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {theme["accent_primary"].name()};
    color: white;
}}
QLabel {{
    color: {theme["window_text"].name()};
}}
QGroupBox {{
    color: {theme["window_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    border-radius: 6px;
    margin-top: 1ex;
    padding-top: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px 0 8px;
    background-color: {theme["window_bg"].name()};
}}
QSpinBox, QComboBox {{
    background-color: {theme["input_bg"].name()};
    color: {theme["input_text"].name()};
    border: 1px solid {theme["input_border"].name()};
    padding: 4px 6px;
    border-radius: 4px;
}}
QSpinBox:focus, QComboBox:focus {{
    border: 2px solid {theme["accent_primary"].name()};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 1px solid {theme["input_border"].name()};
    background-color: {theme["button_bg"].name()};
    width: 16px;
    height: 16px;
}}
QComboBox QAbstractItemView {{
    background-color: {theme["base_bg"].name()};
    color: {theme["base_text"].name()};
    border: 1px solid {theme["button_border"].name()};
    selection-background-color: {theme["accent_primary"].name()};
}}
QCheckBox {{
    spacing: 8px;
    color: {theme["window_text"].name()};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {theme["input_border"].name()};
    border-radius: 4px;
    background: {theme["input_bg"].name()};
}}
QCheckBox::indicator:hover {{
    border: 2px solid {theme["accent_primary"].name()};
}}
QCheckBox::indicator:checked {{
    background: {theme["accent_primary"].name()};
    border: 2px solid {theme["accent_primary"].name()};
    image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="white" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>');
}}
QCheckBox::indicator:disabled {{
    background: {theme["button_bg"].lighter(120).name()};
    border-color: {theme["button_border"].name()};
}}
QSplitter::handle {{
    background-color: transparent;
    margin: 0px;
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}
QSplitter::handle:hover {{
    background-color: transparent;
}}
QStatusBar {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {theme["header_bg"].name()},
        stop: 1 {theme["button_bg"].name()});
    color: {theme["header_text"].name()};
    border-top: none;
}}
""")