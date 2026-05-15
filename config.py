# config.py
import sys
from pathlib import Path
import logging
import os
import json
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Тип базы данных (postgresql или sqlite)
# Может быть изменен пользователем через настройки
DATABASE_TYPE = "postgresql"

# Параметры для PostgreSQL
# По умолчанию используется автоматическое обнаружение сервера
# Если автообнаружение не работает, можно указать адрес вручную
# Адрес сервера загружается из переменной окружения WB_PACKER_DB_HOST
POSTGRESQL_HOST = os.environ.get("WB_PACKER_DB_HOST", "")
POSTGRESQL_PORT = int(os.environ.get("WB_PACKER_DB_PORT", "5432"))
POSTGRESQL_DATABASE = os.environ.get("WB_PACKER_DB_NAME", "wb_packer")
POSTGRESQL_USER = os.environ.get("WB_PACKER_DB_USER", "wb_packer_user")
# Пароль загружается ТОЛЬКО из переменной окружения или файла настроек
# Никогда не храните пароль в коде!
POSTGRESQL_PASSWORD = os.environ.get("WB_PACKER_DB_PASSWORD", "")

# Параметры для SQLite (локальная база данных)
SQLITE_DATABASE = None  # Будет установлен в путь по умолчанию при инициализации
SQLITE_DB_FILENAME = "wb_packer.db"  # Имя файла БД в директории документов

# Флаг использования резервной БД (SQLite при ошибке PostgreSQL)
DATABASE_FALLBACK_ENABLED = True

# Функция для получения адреса PostgreSQL сервера
def get_postgresql_host() -> str:
    """Получить адрес PostgreSQL сервера (с кэшированием и автоматическим обнаружением)"""
    global POSTGRESQL_HOST, logger

    if POSTGRESQL_HOST:
        return POSTGRESQL_HOST

    # Запускаем автопоиск с использованием сохраненного адреса
    try:
        from db_discovery import PostgreSQLDiscovery
        discovery = PostgreSQLDiscovery(
            port=POSTGRESQL_PORT,
            database=POSTGRESQL_DATABASE,
            user=POSTGRESQL_USER,
            password=POSTGRESQL_PASSWORD
        )

        discovered_host = discovery.discover()

        if discovered_host:
            POSTGRESQL_HOST = discovered_host
            logger.info(f"PostgreSQL сервер найден: {discovered_host}")
            return discovered_host
        else:
            logger.warning("Автопоиск PostgreSQL сервера не удался")
            return ""

    except Exception as e:
        logger.error(f"Ошибка при определении адреса PostgreSQL: {e}")
        return ""

# Таймаут для подключения к базе данных (в секундах)
DATABASE_TIMEOUT = 15  # Уменьшен для более быстрого отклика при ошибках

# Параметры подключения к базе данных для оптимизации производительности
# Для удалённого сервера уменьшаем размер пула для экономии ресурсов
DATABASE_POOL_MIN_SIZE = 2   # Уменьшено с 5 - меньше соединений для удалённого сервера
DATABASE_POOL_MAX_SIZE = 15  # Уменьшено с 50 - достаточно для одного клиента
DATABASE_POOL_TIMEOUT = 30   # Уменьшено с 60 - быстрее отклик при ошибках
DATABASE_POOL_RECYCLE = 1800 # Уменьшено с 3600 - чаще обновляем соединения (30 мин)

# Параметры оптимизации PostgreSQL
POSTGRESQL_STATEMENT_TIMEOUT = 15000  # Уменьшено с 30000 - быстрее таймаут запросов
POSTGRESQL_IDLE_TIMEOUT = 30000       # Уменьшено с 60000 - быстрее освобождаем соединения

# Параметры оптимизации для сетевой работы
NETWORK_OPERATION_DELAY = 200  # Уменьшено для быстрого отклика (0.2 сек)

# Настройки по умолчанию
DEFAULT_FONT_SIZE = 10
DEFAULT_LABEL_FONT_SIZE = 20
DEFAULT_THEME = "macOS"
DEFAULT_COLORED_BUTTONS = True  # Разноцветные кнопки по умолчанию

# Настройки архива
ARCHIVE_ENABLED = True
ARCHIVE_AUTO_BACKUP = True

# Информация о поставщиках для упаковочных листов
SUPPLIER_INFO = {
    "ООО ОНДЕФОР": 'ООО "ОНДЕФОР ГРУПП" 5029279234',
    "ИП Лазарчук": "ИП Лазарчук К.Е., 632410867452"
}

# Настройки упаковочного листа
PACKING_LIST_DEFAULTS = {
    "pallets_count": "1",
    "pallet_number": "1", 
    "shipment_method": "Короб",
    "font_size": 24,
    "page_width": 8.5,
    "page_height": 11,
    "margins": 0.5,
    "column_widths": [3.5, 4.0]
}

# Глобальная переменная для кэширования базового пути ресурсов
_RESOURCE_BASE_PATH = None

def _get_resource_base_path() -> Path:
    """Получить базовый путь к ресурсам (кэшируется)"""
    global _RESOURCE_BASE_PATH

    if _RESOURCE_BASE_PATH is not None:
        return _RESOURCE_BASE_PATH

    if getattr(sys, 'frozen', False):
        # При работе из EXE файла (PyInstaller)
        # Используем _MEIPASS для onefile режима
        if hasattr(sys, '_MEIPASS'):
            # onefile режим - ресурсы во временной папке
            _RESOURCE_BASE_PATH = Path(sys._MEIPASS)
        else:
            # onedir режим - ресурсы рядом с exe
            _RESOURCE_BASE_PATH = Path(sys.executable).parent
    else:
        # При обычной разработке - директория с config.py
        _RESOURCE_BASE_PATH = Path(__file__).parent

    return _RESOURCE_BASE_PATH


def get_resource_path(relative_path: str) -> Path:
    """Получить путь к ресурсам (для упакованного приложения)"""
    import logging
    logger = logging.getLogger(__name__)

    # Получаем базовый путь к ресурсам
    base_path = _get_resource_base_path()

    # Преобразуем relative_path в строку если это Path
    if isinstance(relative_path, Path):
        relative_path_str = str(relative_path)
    else:
        relative_path_str = str(relative_path).replace('/', os.sep).replace('\\', os.sep)

    # Создаем полный путь и нормализуем его для Windows
    full_path = base_path / relative_path_str
    result = Path(os.path.normpath(str(full_path)))

    return result


# Файл для хранения настроек подключения к БД
DB_SETTINGS_FILE = Path.home() / ".wb_packer" / "db_settings.json"


def load_db_settings() -> Dict[str, Any]:
    """
    Загружает настройки подключения к базе данных из файла
    Возвращает словарь с настройками
    """
    try:
        if DB_SETTINGS_FILE.exists():
            with open(DB_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                logger.info(f"Настройки БД загружены из {DB_SETTINGS_FILE}")
                return settings
    except Exception as e:
        logger.warning(f"Ошибка при загрузке настроек БД: {e}")
    
    # Настройки по умолчанию
    return {
        'database_type': 'postgresql',
        'postgresql_host': None,
        'postgresql_port': 5432,
        'postgresql_database': 'wb_packer',
        'postgresql_user': 'wb_packer_user',
        'postgresql_password': os.environ.get("WB_PACKER_DB_PASSWORD", ""),
        'sqlite_database': None,
        'fallback_enabled': True
    }


def save_db_settings(settings: Dict[str, Any]) -> bool:
    """
    Сохраняет настройки подключения к базе данных в файл
    """
    try:
        # Создаем директорию если она не существует
        DB_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(DB_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Настройки БД сохранены в {DB_SETTINGS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении настроек БД: {e}")
        return False


def apply_db_settings(settings: Dict[str, Any]) -> None:
    """
    Применяет настройки подключения к базе данных из словаря
    """
    global DATABASE_TYPE, POSTGRESQL_HOST, POSTGRESQL_PORT, POSTGRESQL_DATABASE
    global POSTGRESQL_USER, POSTGRESQL_PASSWORD, SQLITE_DATABASE, DATABASE_FALLBACK_ENABLED
    
    DATABASE_TYPE = settings.get('database_type', 'postgresql')
    POSTGRESQL_HOST = settings.get('postgresql_host')
    POSTGRESQL_PORT = settings.get('postgresql_port', 5432)
    POSTGRESQL_DATABASE = settings.get('postgresql_database', 'wb_packer')
    POSTGRESQL_USER = settings.get('postgresql_user', 'wb_packer_user')
    POSTGRESQL_PASSWORD = settings.get('postgresql_password', os.environ.get("WB_PACKER_DB_PASSWORD", ""))
    SQLITE_DATABASE = settings.get('sqlite_database')
    DATABASE_FALLBACK_ENABLED = settings.get('fallback_enabled', True)
    
    logger.info(f"Применены настройки БД: тип={DATABASE_TYPE}, fallback={DATABASE_FALLBACK_ENABLED}")


def get_sqlite_database_path() -> str:
    """
    Получает полный путь к файлу SQLite базы данных
    """
    global SQLITE_DATABASE

    if SQLITE_DATABASE:
        return SQLITE_DATABASE

    # Путь по умолчанию в директории приложения (для портативности)
    # При работе из EXE - рядом с exe-файлом, при разработке - в папке проекта
    if getattr(sys, 'frozen', False):
        # При работе из EXE файла - БД в папке рядом с exe
        default_path = Path(sys.executable).parent / SQLITE_DB_FILENAME
    else:
        # При разработке - в папке проекта
        default_path = Path(__file__).parent / SQLITE_DB_FILENAME

    default_path.parent.mkdir(parents=True, exist_ok=True)

    return str(default_path)


def init_db_settings() -> None:
    """
    Инициализирует настройки базы данных из файла при запуске приложения
    Должна вызываться при старте приложения
    """
    settings = load_db_settings()
    
    # Применяем настройки и сбрасываем подключение если оно уже было создано
    from db_connection import apply_db_settings as apply_db_connection_settings
    apply_db_connection_settings(settings)
    
    logger.info(f"Инициализированы настройки БД: тип={DATABASE_TYPE}, файл={get_sqlite_database_path()}")


# Убедимся, что все строковые параметры в правильной кодировке
# Установка правильной кодировки для корректной обработки строк в PostgreSQL
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PGCLIENTENCODING'] = 'UTF8'