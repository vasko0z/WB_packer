# local_db.py
"""
Модуль для работы с локальной базой данных SQLite
Используется как запасной вариант при недоступности PostgreSQL
"""
import sqlite3
import logging
import os
import threading
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SQLiteConnection:
    """
    Класс для управления подключением к SQLite базе данных.
    Использует паттерн Singleton для обеспечения единственного экземпляра.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Предотвращаем повторную инициализацию Singleton
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.db_type = "sqlite"
        self.db_path = None
        self._local = threading.local()
        self._lock = threading.Lock()
        self._initialize_database()
        self._initialized = True

    def _get_db_path(self):
        """Получить путь к файлу базы данных"""
        # Пытаемся получить путь из config
        try:
            import config
            if hasattr(config, 'SQLITE_DATABASE'):
                return config.SQLITE_DATABASE
        except Exception:
            pass
        
        # Путь по умолчанию - в директории документа пользователя
        default_path = Path.home() / "Documents" / "WB_Packer" / "wb_packer.db"
        default_path.parent.mkdir(parents=True, exist_ok=True)
        return str(default_path)

    def _initialize_database(self):
        """Инициализирует подключение к базе данных SQLite"""
        try:
            self.db_path = self._get_db_path()
            logger.info(f"Инициализация SQLite базы данных: {self.db_path}")
            
            # Создаем подключение для проверки
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            self._return_connection(conn)
            
            logger.info(f"SQLite база данных инициализирована: {self.db_path}")
        except Exception as e:
            logger.error(f"Ошибка инициализации SQLite: {e}", exc_info=True)
            raise

    def _get_connection(self):
        """Создает новое подключение к SQLite"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Включаем поддержку внешних ключей
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _get_thread_connection(self):
        """Получает подключение для текущего потока"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._get_connection()
        return self._local.conn

    def get_connection(self):
        """Получает соединение из пула (для SQLite - создает новое для потока)"""
        return self._get_thread_connection()

    def _return_connection(self, conn):
        """Возвращает соединение в пул (для SQLite - закрывает если не основное)"""
        if conn is not None:
            try:
                # Не закрываем основное подключение потока
                if hasattr(self._local, 'conn') and self._local.conn is conn:
                    pass  # Оставляем подключение открытым
                else:
                    conn.close()
            except Exception as e:
                logger.warning(f"Ошибка при возврате соединения SQLite: {e}")

    def close_all_connections(self):
        """Закрывает все соединения"""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                self._local.conn.close()
                self._local.conn = None
                logger.info("Соединение с SQLite закрыто")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии соединения SQLite: {e}")

    @classmethod
    def get_instance(cls):
        """Получить экземпляр SQLiteConnection (Singleton)"""
        return cls()


# Глобальный экземпляр подключения
_sqlite_instance = None


def get_sqlite_connection():
    """Получить соединение с SQLite базой данных"""
    global _sqlite_instance
    if _sqlite_instance is None:
        _sqlite_instance = SQLiteConnection()
    return _sqlite_instance.get_connection()


def _return_sqlite_connection(conn):
    """Вернуть соединение в пул SQLite"""
    global _sqlite_instance
    if _sqlite_instance:
        _sqlite_instance._return_connection(conn)


@contextmanager
def sqlite_transaction():
    """
    Контекстный менеджер для транзакций SQLite
    """
    conn = get_sqlite_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка транзакции SQLite: {e}", exc_info=True)
        raise


def init_sqlite_db():
    """
    Инициализирует структуру базы данных SQLite
    Создает все необходимые таблицы
    """
    try:
        logger.info("Начало инициализации SQLite базы данных")
        conn = get_sqlite_connection()
        cursor = conn.cursor()

        # Таблица поставок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination_name TEXT NOT NULL UNIQUE,
                font_size INTEGER DEFAULT 10,
                label_font_size INTEGER DEFAULT 20,
                theme TEXT DEFAULT 'Светлая',
                removed_items TEXT DEFAULT '{}',
                parent_group TEXT DEFAULT NULL,
                properties TEXT DEFAULT '{}',
                archived INTEGER DEFAULT 0,
                archived_date TIMESTAMP DEFAULT NULL,
                archived_by TEXT DEFAULT NULL
            )
        """)

        # Таблица товаров поставки
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shipment_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shipment_id INTEGER NOT NULL,
                barcode TEXT NOT NULL,
                sku TEXT NOT NULL,
                total_qty INTEGER NOT NULL,
                allocated_qty INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
            )
        """)

        # Таблица коробок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS boxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shipment_id INTEGER NOT NULL,
                box_id TEXT NOT NULL,
                is_current INTEGER DEFAULT 0,
                FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
            )
        """)

        # Таблица товаров в коробках
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS box_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                box_id INTEGER NOT NULL,
                barcode TEXT NOT NULL,
                qty INTEGER NOT NULL,
                FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE CASCADE
            )
        """)

        # Таблица настроек приложения
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Таблица состояния окон
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS window_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                font_size INTEGER DEFAULT 10,
                label_font_size INTEGER DEFAULT 20,
                theme TEXT DEFAULT 'Светлая',
                ok_sound TEXT DEFAULT 'ok.wav',
                error_sound TEXT DEFAULT 'error.wav',
                tone_sound INTEGER DEFAULT 0,
                sound_volume INTEGER DEFAULT 100,
                shipment_columns_width TEXT DEFAULT '',
                box_columns_width TEXT DEFAULT '',
                main_splitter_sizes TEXT DEFAULT '',
                window_width INTEGER DEFAULT 1300,
                window_height INTEGER DEFAULT 800,
                button_primary_color TEXT DEFAULT '',
                button_success_color TEXT DEFAULT '',
                button_warning_color TEXT DEFAULT '',
                button_danger_color TEXT DEFAULT ''
            )
        """)

        # Миграция: добавляем колонку sound_volume если её нет
        try:
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'sound_volume' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN sound_volume INTEGER DEFAULT 100")
                logger.info("Добавлена колонка sound_volume в таблицу users")
        except Exception as e:
            logger.debug(f"Проверка/добавление колонки sound_volume: {e}")

        # Таблица сессий пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shipment_name TEXT NOT NULL,
                username TEXT NOT NULL,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Создаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shipment_name ON user_sessions(shipment_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_last_activity ON user_sessions(last_activity)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shipment_items_shipment ON shipment_items(shipment_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_boxes_shipment ON boxes(shipment_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_box_items_box ON box_items(box_id)")

        # Таблица кэша остатков
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_cache (
                barcode TEXT PRIMARY KEY,
                quantity INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица SKU
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sku (
                barcode TEXT PRIMARY KEY,
                name TEXT,
                article TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица для хранения настроек базы данных (тип БД, путь и т.д.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS db_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.commit()
        logger.info("Инициализация SQLite базы данных завершена успешно")

    except Exception as e:
        logger.error(f"Ошибка инициализации SQLite базы данных: {e}", exc_info=True)
        raise


def execute_sqlite_query(query, params=None, fetch=False, fetchone=False, fetchall=False):
    """
    Выполняет запрос к SQLite базе данных
    Автоматически конвертирует параметры и обрабатывает результаты
    """
    conn = get_sqlite_connection()
    try:
        cursor = conn.cursor()
        
        # Преобразуем параметры в кортеж
        if params is None:
            params = ()
        elif not isinstance(params, (tuple, list)):
            params = (params,)
        
        # SQLite использует ? вместо %s
        sqlite_query = query.replace("%s", "?")
        
        cursor.execute(sqlite_query, params)
        
        if fetchall:
            result = cursor.fetchall()
        elif fetchone:
            result = cursor.fetchone()
        elif fetch:
            result = cursor.fetchall()
        else:
            result = None
        
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Ошибка выполнения запроса SQLite: {e}", exc_info=True)
        conn.rollback()
        raise


def execute_sqlite_many(query, params_list):
    """
    Выполняет массовую вставку/обновление в SQLite
    """
    conn = get_sqlite_connection()
    try:
        cursor = conn.cursor()
        
        # SQLite использует ? вместо %s
        sqlite_query = query.replace("%s", "?")
        
        if params_list:
            cursor.executemany(sqlite_query, params_list)
        else:
            cursor.execute(sqlite_query)
        
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка выполнения массового запроса SQLite: {e}", exc_info=True)
        conn.rollback()
        raise


def get_sqlite_db_path():
    """Получить путь к файлу SQLite базы данных"""
    return SQLiteConnection.get_instance().db_path if SQLiteConnection.get_instance().db_path else "wb_packer.db"


def set_sqlite_db_path(path):
    """Установить путь к файлу SQLite базы данных"""
    global _sqlite_instance
    if _sqlite_instance:
        _sqlite_instance.close_all_connections()
        _sqlite_instance.db_path = path
        _sqlite_instance._initialized = False
        _sqlite_instance._initialize_database()
    else:
        # Создаем новый экземпляр с указанным путем
        import config
        config.SQLITE_DATABASE = path
        _sqlite_instance = SQLiteConnection()
