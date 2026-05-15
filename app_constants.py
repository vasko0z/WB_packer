"""
Константы приложения WB Packer
"""
from enum import IntEnum
from PyQt6.QtGui import QColor


class ColumnIndex(IntEnum):
    """Индексы столбцов таблицы поставки"""
    BARCODE = 0
    SKU = 1
    NAME = 2
    TOTAL_QTY = 3
    REMAINING_QTY = 4
    STOCK_QTY = 5
    ACTION = 6


class BoxColumnIndex(IntEnum):
    """Индексы столбцов таблицы коробки"""
    BARCODE = 0
    SKU = 1
    QTY = 2


class RemovedColumnIndex(IntEnum):
    """Индексы столбцов таблицы удалённых товаров"""
    BARCODE = 0
    SKU = 1
    ACTION = 2


# ============================================================================
# Размеры элементов UI
# ============================================================================

# Таблицы
TABLE_ROW_HEIGHT_MIN = 28
TABLE_ROW_HEIGHT_PADDING = 8
TABLE_ROW_HEIGHT_DEFAULT = 32

# Столбцы таблиц
ACTION_COLUMN_WIDTH = 85
ACTION_BUTTON_SIZE = 16
QTY_INPUT_WIDTH = 40

# Дерево поставок
SHIPMENT_ITEM_HEIGHT_WITH_PROGRESS = 50
SHIPMENT_ITEM_HEIGHT_NO_PROGRESS = 42
BOX_ITEM_HEIGHT = 36
BOX_ITEM_HEIGHT_COMPACT = 32

# Отступы
TREE_ITEM_MARGIN_LEFT = 8
TREE_ITEM_MARGIN_RIGHT = 8
TREE_ITEM_MARGIN_TOP = 4
TREE_ITEM_MARGIN_BOTTOM = 4
BOX_ITEM_MARGIN_LEFT = 8
BOX_ITEM_MARGIN_RIGHT = 6
BOX_ITEM_MARGIN_TOP = 2
BOX_ITEM_MARGIN_BOTTOM = 2

# Интервалы
TREE_ITEM_SPACING = 4
BOX_ITEM_SPACING = 3

# Иконки
ICON_SIZE_SMALL = 16
ICON_SIZE_MEDIUM = 20
ICON_SIZE_LARGE = 24

# Шрифты
FONT_SIZE_DEFAULT = 10
LABEL_FONT_SIZE_DEFAULT = 14

# ============================================================================
# Цвета
# ============================================================================

# Основные цвета
COLOR_PRIMARY = QColor(76, 175, 80)
COLOR_SUCCESS = QColor(76, 175, 80)
COLOR_WARNING = QColor(255, 152, 0)
COLOR_DANGER = QColor(244, 67, 54)
COLOR_INFO = QColor(33, 150, 243)

# Цвета текста
COLOR_TEXT_PRIMARY = QColor(40, 40, 40)
COLOR_TEXT_SECONDARY = QColor(100, 100, 100)
COLOR_TEXT_DISABLED = QColor(150, 150, 150)

# Цвета фона
COLOR_BACKGROUND = QColor(245, 245, 247)
COLOR_BACKGROUND_HOVER = QColor(235, 235, 237)

# Цвета для статусов
COLOR_STOCK_POSITIVE = QColor(0, 100, 200)  # Синий
COLOR_STOCK_NEGATIVE = QColor(200, 50, 50)  # Красный

# ============================================================================
# Пути к ресурсам
# ============================================================================

ICONS = {
    'barcode': 'Res/basrc.png',
    'box': 'Res/box.png',
    'main_icon': 'Res/icon.ico',
    'ok_sound': 'Res/ok.wav',
    'error_sound': 'Res/error.wav',
}

# ============================================================================
# Тайминги
# ============================================================================

# Задержки сохранения
SAVE_DELAY_MS = 500  # Уменьшено с 3000 - быстрее сохранение для удалённого сервера
UI_UPDATE_DELAY_MS = 100

# Тайминги сообщений статус-бара
STATUS_MESSAGE_SHORT_MS = 200
STATUS_MESSAGE_NORMAL_MS = 2000
STATUS_MESSAGE_LONG_MS = 5000

# ============================================================================
# Ограничения
# ============================================================================

# Максимальные значения
MAX_PROGRESS_BAR_VALUE = 2147483647  # Максимальное значение для 32-bit int

# Лимиты
MAX_RECENT_FILES = 10
MAX_LOG_SIZE_MB = 10
MAX_CACHE_SIZE_MB = 100

# ============================================================================
# Настройки БД
# ============================================================================

DB_TABLES = {
    'shipments': 'shipments',
    'shipment_items': 'shipment_items',
    'boxes': 'boxes',
    'box_items': 'box_items',
    'users': 'users',
    'user_sessions': 'user_sessions',
    'stock_cache': 'stock_cache',
    'sku': 'sku',
}

DB_INDEXES = [
    'idx_shipment_items_barcode',
    'idx_box_items_barcode',
    'idx_stock_cache_barcode',
    'idx_shipment_items_shipment_id',
    'idx_boxes_shipment_id',
    'idx_box_items_box_id',
    'idx_user_sessions_shipment_name',
    'idx_user_sessions_username',
]


class ShipmentStatus:
    """Статусы поставки"""
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    HAS_DISCREPANCIES = "has_discrepancies"


STATUS_ICONS = {
    ShipmentStatus.COMPLETED: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#4CAF50"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>',
    ShipmentStatus.HAS_DISCREPANCIES: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#FF9800"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>',
    ShipmentStatus.IN_PROGRESS: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2196F3"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>',
}
