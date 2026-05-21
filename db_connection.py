# db_connection.py
import json
import logging
from pathlib import Path
import config
import os
import sys

# Установка переменной окружения для правильной кодировки PostgreSQL до импорта psycopg2
os.environ['PGCLIENTENCODING'] = 'UTF8'
# Also set Python IO encoding to handle any text output properly
os.environ['PYTHONIOENCODING'] = 'UTF-8'
# Force UTF-8 encoding for Python strings on Windows
os.environ['PYTHONUTF8'] = '1'

# Import PostgreSQL
# Установка кодировки до импорта psycopg2
import locale

logger = logging.getLogger(__name__)

# Пытаемся установить правильную локаль
try:
   locale.setlocale(locale.LC_ALL, 'C.UTF-8')
except locale.Error:
   try:
       locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
   except locale.Error:
       # Если не удается установить UTF-8 локаль, пробуем установить переменные окружения
       os.environ['LC_ALL'] = 'C.UTF-8'
       os.environ['LANG'] = 'C.UTF-8'
       logger.warning("Не удалось установить локаль, используем переменные окружения")

# Импортируем psycopg (psycopg3) для Python 3.14+
psycopg = None
psycopg2 = None
SimpleConnectionPool = None
RealDictCursor = None
psycopg_extras = None  # Для execute_values / execute_batch
if config.DATABASE_TYPE == "postgresql":
    # Сначала пробуем psycopg3 (совместим с Python 3.14+)
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool as SimpleConnectionPool
        from psycopg import extras as psycopg_extras
        logger.info("Используется psycopg3 (Python 3.14+)")
    except ImportError:
        psycopg = None
        # Fallback на psycopg2
        try:
            import psycopg2
            import psycopg2.extensions
            from psycopg2.extras import RealDictCursor
            from psycopg2.pool import SimpleConnectionPool
            from psycopg2 import extras as psycopg_extras
            logger.info("Используется psycopg2")
        except ImportError:
            logger.warning("psycopg2/psycopg3 не установлены. PostgreSQL не будет доступен.")

import socket
import subprocess
import threading
import sqlite3

# Глобальный флаг для отслеживания текущего типа подключения
_current_db_type = config.DATABASE_TYPE
_postgresql_available = True


class DatabaseConnection:
    """
    Класс для управления подключениями к базе данных.
    Использует паттерн Singleton для обеспечения единственного экземпляра.
    Поддерживает PostgreSQL и SQLite (как резервный вариант).
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Предотвращаем повторную инициализацию Singleton
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.db_type = config.DATABASE_TYPE
        self.local_ip_warning_shown = False  # Флаг для отслеживания вывода сообщения
        self._sqlite_conn = None  # Подключение к SQLite

        # Инициализируем пул соединений
        self.connection_pool = None
        self._pool_lock = threading.Lock()  # Блокировка для потокобезопасности
        
        # Пытаемся инициализировать подключение
        self._initialize_connection_pool()
        self._initialized = True

    def _initialize_connection_pool(self):
        """Инициализирует пул соединений с базой данных"""
        global _current_db_type, _postgresql_available
        
        # Сначала пробуем основной тип БД
        if self.db_type == "postgresql":
            try:
                self._init_postgresql_pool()
                return  # Успешно, выходим
            except Exception as e:
                # Если ошибка и включен fallback, пробуем SQLite
                if config.DATABASE_FALLBACK_ENABLED:
                    logger.warning(f"Ошибка подключения к PostgreSQL: {e}")
                    logger.info("Переключение на SQLite (резервный вариант)...")
                    _postgresql_available = False
                    _current_db_type = "sqlite"
                    self.db_type = "sqlite"
                    try:
                        self._init_sqlite_connection()
                        return  # Успешно переключились
                    except Exception as sqlite_error:
                        logger.error(f"Ошибка инициализации SQLite: {sqlite_error}", exc_info=True)
                        # Пробрасываем оригинальную ошибку PostgreSQL
                        raise e
                else:
                    logger.error(f"Ошибка инициализации пула соединений: {e}", exc_info=True)
                    raise
        else:
            # SQLite
            try:
                self._init_sqlite_connection()
            except Exception as e:
                logger.error(f"Ошибка инициализации SQLite: {e}", exc_info=True)
                raise

    def _init_postgresql_pool(self):
        """Инициализирует пул соединений PostgreSQL"""
        if not psycopg and not psycopg2:
            raise ImportError("psycopg2/psycopg3 не установлены. PostgreSQL не будет доступен.")

        try:
            # Получаем параметры из конфига
            # Используем функцию для автоматического определения адреса
            host = config.get_postgresql_host()
            port = config.POSTGRESQL_PORT
            database = config.POSTGRESQL_DATABASE
            user = config.POSTGRESQL_USER
            password = config.POSTGRESQL_PASSWORD

            # Получаем параметры пула из конфига
            min_conn = getattr(config, 'DATABASE_POOL_MIN_SIZE', 1)
            max_conn = getattr(config, 'DATABASE_POOL_MAX_SIZE', 20)
            pool_timeout = getattr(config, 'DATABASE_POOL_TIMEOUT', 30)

            logger.info(f"Попытка подключения к PostgreSQL: {host}:{port}")
            logger.info(f"Параметры пула: минимум={min_conn}, максимум={max_conn}, таймаут={pool_timeout}с")

            # Создаем пул соединений
            if psycopg is not None:
                # psycopg3 (Python 3.14+)
                from psycopg_pool import ConnectionPool
                
                # Для psycopg3 передаем параметры через kwargs
                conn_kwargs = {
                    'host': host,
                    'port': port,
                    'dbname': database,
                    'user': user,
                    'password': password,
                    'connect_timeout': config.DATABASE_TIMEOUT,
                    'sslmode': 'disable',
                    'client_encoding': 'UTF8',
                }
                
                self.connection_pool = ConnectionPool(
                    conninfo='',  # Пустая строка, параметры в kwargs
                    kwargs=conn_kwargs,
                    min_size=min_conn,
                    max_size=max_conn,
                    open=True,
                )
            else:
                # psycopg2
                # Передаем параметры как именованные аргументы для избежания проблем с кодировкой
                logger.debug(f"Подключение к PostgreSQL: host={host} port={port} dbname={database} user={user} password=***")

                self.connection_pool = SimpleConnectionPool(
                    minconn=min_conn,
                    maxconn=max_conn,
                    host=host,
                    port=port,
                    database=database,
                    user=user,
                    password=password,
                    connect_timeout=config.DATABASE_TIMEOUT,
                    sslmode='disable',
                    client_encoding='UTF8'
                )

            logger.info(f"Пул соединений с базой данных инициализирован: {database} на {host}:{port}")
            logger.info(f"Размер пула: {min_conn}-{max_conn} соединений")
        except Exception as e:
            logger.error(f"Ошибка инициализации пула PostgreSQL: {e}", exc_info=True)
            raise

    def _init_sqlite_connection(self):
        """Инициализирует подключение к SQLite"""
        try:
            import sqlite3

            db_path = config.get_sqlite_database_path()
            logger.info(f"Инициализация SQLite: {db_path}")

            # Создаем подключение
            self._sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
            self._sqlite_conn.row_factory = sqlite3.Row

            # Включаем поддержку внешних ключей
            self._sqlite_conn.execute("PRAGMA foreign_keys = ON")

            # Проверяем подключение
            cursor = self._sqlite_conn.cursor()
            cursor.execute("SELECT 1")
            
            # Добавляем недостающие колонки в таблицу users если их нет
            self._migrate_sqlite_users_table(cursor)
            
            cursor.close()

            logger.info(f"SQLite база данных инициализирована: {db_path}")
        except Exception as e:
            logger.error(f"Ошибка инициализации SQLite: {e}", exc_info=True)
            raise

    def _migrate_sqlite_users_table(self, cursor):
        """Добавляет недостающие колонки в таблицу users при первом подключении"""
        try:
            # Получаем список существующих колонок
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Список колонок которые должны быть
            expected_columns = [
                ('tone_sound', 'INTEGER DEFAULT 0'),
                ('sound_volume', 'INTEGER DEFAULT 100'),
                ('cached_server_ip', 'TEXT DEFAULT ""'),
                ('moysklad_token', 'TEXT DEFAULT ""'),
                ('moysklad_stores', 'TEXT DEFAULT ""'),
                ('moysklad_enabled', 'INTEGER DEFAULT 0'),
                ('shipment_locking_enabled', 'INTEGER DEFAULT 0'),
                ('article_column_visible', 'INTEGER DEFAULT 1'),
                ('name_column_visible', 'INTEGER DEFAULT 0'),
                ('stock_column_visible', 'INTEGER DEFAULT 1'),
                ('hide_completed_items', 'INTEGER DEFAULT 0'),
                ('total_qty_column_visible', 'INTEGER DEFAULT 1'),
                ('button_colors', 'TEXT DEFAULT ""'),
                ('colored_buttons', 'INTEGER DEFAULT 1')
            ]
            
            # Добавляем отсутствующие колонки
            for col_name, col_def in expected_columns:
                if col_name not in columns:
                    try:
                        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                        logger.info(f"Добавлена колонка {col_name} в таблицу users (SQLite)")
                    except Exception as e:
                        logger.debug(f"Ошибка при добавлении колонки {col_name}: {e}")
            
            # Фиксируем изменения
            self._sqlite_conn.commit()
            
        except Exception as e:
            logger.debug(f"Миграция таблицы users: {e}")

    def is_local_ip(self, ip):
        """Проверяет, является ли IP-адрес локальным IP-адресом текущего компьютера"""
        try:
            # Получаем имя хоста и все IP-адреса
            hostname = socket.gethostname()
            local_ips = socket.gethostbyname_ex(hostname)[2]

            # Добавляем localhost и 127.0.0.1
            local_ips.extend(['127.0.1', 'localhost'])

            # Проверяем, является ли указанный IP одним из локальных
            return ip in local_ips
        except Exception as e:
            logger.warning(f"Ошибка при проверке локального IP-адреса {ip}: {e}")
            # В случае ошибки просто возвращаем False
            return False

    def get_connection(self):
        """Получает соединение из пула"""
        if self.connection_pool is None and self._sqlite_conn is None:
            self._initialize_connection_pool()

        if self.db_type == "sqlite":
            # Для SQLite возвращаем то же подключение
            # Проверяем, не закрыто ли оно или не был ли сброшен флаг _initialized
            if self._sqlite_conn is None or not getattr(self, '_initialized', True):
                logger.debug("Соединение SQLite пересоздаётся после миграции")
                self._init_sqlite_connection()
                self._initialized = True
            else:
                # Проверяем, живо ли соединение
                try:
                    self._sqlite_conn.execute("SELECT 1")
                except sqlite3.ProgrammingError:
                    # Соединение закрыто, создаем новое
                    logger.debug("Соединение SQLite закрыто, создаем новое")
                    self._init_sqlite_connection()
            return self._sqlite_conn
        else:
            # Для PostgreSQL берем из пула
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    if psycopg is not None:
                        # psycopg3
                        conn = self.connection_pool.getconn()
                        # Проверяем, живо ли соединение
                        if conn.closed:
                            logger.debug("Соединение закрыто, получаем новое")
                            continue
                        # Сбрасываем любое незавершённое состояние транзакции
                        try:
                            if conn.pq.status == psycopg.pq.TransactionStatus.INTRANS:
                                conn.rollback()
                        except Exception:
                            pass
                        # Проверяем соединение простым запросом
                        try:
                            with conn.cursor() as cur:
                                cur.execute("SELECT 1")
                        except Exception:
                            # Соединение невалидно, закрываем и пробуем снова
                            logger.debug("Соединение невалидно, получаем новое")
                            try:
                                conn.close()
                            except Exception:
                                pass
                            continue
                        # Устанавливаем параметры сессии (таймауты) из конфигурации
                        with conn.cursor() as cur:
                            cur.execute(f"SET statement_timeout TO {getattr(config, 'POSTGRESQL_STATEMENT_TIMEOUT', 30000)}")
                            cur.execute(f"SET idle_in_transaction_session_timeout TO {getattr(config, 'POSTGRESQL_IDLE_TIMEOUT', 60000)}")
                        return conn
                    else:
                        # psycopg2
                        with self._pool_lock:
                            conn = self.connection_pool.getconn()
                        # Проверяем, живо ли соединение
                        if conn.closed:
                            logger.debug("Соединение закрыто, получаем новое")
                            continue
                        # Сбрасываем любое незавершённое состояние транзакции
                        try:
                            if hasattr(conn, 'status') and conn.status == 2:  # 2 = INTRANS
                                conn.rollback()
                        except Exception:
                            pass
                        # Проверяем соединение простым запросом
                        try:
                            cursor = conn.cursor()
                            cursor.execute("SELECT 1")
                            cursor.close()
                        except Exception:
                            # Соединение невалидно, закрываем и пробуем снова
                            logger.debug("Соединение невалидно, получаем новое")
                            try:
                                conn.close()
                            except Exception:
                                pass
                            continue
                        conn.set_client_encoding('UTF8')
                        cursor = conn.cursor()
                        # Используем таймауты из конфигурации
                        cursor.execute(f"SET statement_timeout TO {getattr(config, 'POSTGRESQL_STATEMENT_TIMEOUT', 30000)}")
                        cursor.execute(f"SET idle_in_transaction_session_timeout TO {getattr(config, 'POSTGRESQL_IDLE_TIMEOUT', 60000)}")
                        cursor.close()
                        return conn
                except Exception as e:
                    logger.error(f"Ошибка получения соединения из пула (попытка {attempt + 1}): {e}", exc_info=True)
                    if attempt == max_retries - 1:
                        raise
                    # Закрываем пул и пересоздаем
                    try:
                        self.close_all_connections()
                    except Exception:
                        pass
                    self._initialize_connection_pool()
            raise Exception("Не удалось получить валидное соединение после нескольких попыток")

    def return_connection(self, conn):
        """Возвращает соединение в пул"""
        if self.db_type == "sqlite":
            # Для SQLite ничего не делаем, подключение остается открытым
            pass
        elif conn is not None and self.connection_pool is not None:
            try:
                if psycopg is not None:
                    # psycopg3: проверяем, живо ли соединение
                    if conn.closed:
                        logger.debug("Соединение уже закрыто, не возвращаем в пул")
                        return
                    
                    # Возвращаем соединение в пул
                    # Если возникает ошибка "unkeyed connection", просто закрываем соединение
                    self.connection_pool.putconn(conn)
                else:
                    # psycopg2
                    with self._pool_lock:
                        self.connection_pool.putconn(conn)
            except Exception as e:
                # Если соединение уже закрыто или недействительно (включая "unkeyed connection"),
                # просто закрываем соединение и не возвращаем в пул
                logger.debug(f"Не удалось вернуть соединение в пул psycopg3: {e}")
                try:
                    conn.close()
                except Exception:
                    pass

    def close_all_connections(self):
        """Закрывает все соединения в пуле"""
        if self.connection_pool:
            if psycopg is not None:
                # psycopg3 использует close() вместо closeall()
                self.connection_pool.close()
            else:
                self.connection_pool.closeall()
            logger.info("Все соединения PostgreSQL закрыты")
        if self._sqlite_conn:
            self._sqlite_conn.close()
            self._sqlite_conn = None
            logger.info("Соединение с SQLite закрыто")

    def get_pool_stats(self):
        """Получить статистику пула соединений"""
        if self.connection_pool:
            try:
                # Получаем внутренние метрики пула
                stats = {
                    'minconn': self.connection_pool.minconn,
                    'maxconn': self.connection_pool.maxconn,
                    'used': len([1 for conn in self.connection_pool._pool if conn is not None]),
                    'available': len([1 for conn in self.connection_pool._pool if conn is None])
                }
                return stats
            except Exception as e:
                logger.error(f"Ошибка получения статистики пула: {e}")
                return None
        return None

    def log_pool_status(self):
        """Залогировать текущее состояние пула соединений"""
        stats = self.get_pool_stats()
        if stats:
            logger.info(f"Состояние пула соединений: "
                       f"используется={stats['used']}, "
                       f"доступно={stats['available']}, "
                       f"всего={stats['minconn']}-{stats['maxconn']}")

    @classmethod
    def get_instance(cls):
        """Получить экземпляр DatabaseConnection (Singleton)"""
        return cls()


def get_connection():
    """Получить соединение из пула (удобная функция)"""
    return DatabaseConnection.get_instance().get_connection()


def get_db_type():
    """
    Получить фактический тип текущей базы данных.
    Возвращает 'sqlite' или 'postgresql' в зависимости от активного соединения.
    Это важно использовать вместо config.DATABASE_TYPE, так как при fallback
    с PostgreSQL на SQLite config.DATABASE_TYPE не обновляется.
    """
    return DatabaseConnection.get_instance().db_type


def _clear_connection_pool():
    """
    Очистить пул соединений (используется после миграций БД)
    Закрывает соединения PostgreSQL, но не закрывает SQLite соединение,
    так как оно может ещё использоваться в вызывающей функции.
    """
    if DatabaseConnection._instance is not None:
        # Закрываем только пул PostgreSQL
        if DatabaseConnection._instance.connection_pool:
            if psycopg is not None:
                # psycopg3 использует close() вместо closeall()
                DatabaseConnection._instance.connection_pool.close()
            else:
                DatabaseConnection._instance.connection_pool.closeall()
            logger.info("Пул соединений PostgreSQL очищен")
        # Для SQLite просто сбрасываем _initialized, чтобы следующее соединение было новым
        DatabaseConnection._instance._initialized = False
        # Не сбрасываем _instance и не закрываем _sqlite_conn, так как оно может ещё использоваться
        logger.info("Пул соединений очищен (SQLite соединение будет пересоздано при следующем запросе)")


def apply_db_settings(settings):
    """
    Применяет настройки подключения к базе данных
    Сбрасывает существующее подключение для применения новых настроек
    """
    global _current_db_type, _postgresql_available
    
    # Сбрасываем существующее подключение
    if DatabaseConnection._instance is not None:
        DatabaseConnection._instance.close_all_connections()
        DatabaseConnection._instance._initialized = False
        DatabaseConnection._instance = None
    
    # Применяем новые настройки
    config.apply_db_settings(settings)
    
    logger.info(f"Настройки БД применены: тип={config.DATABASE_TYPE}")


def _release_connection(conn):
    """Вспомогательная функция для освобождения соединения"""
    try:
        DatabaseConnection.get_instance().return_connection(conn)
    except Exception as e:
        logger.error(f"Ошибка освобождения соединения: {e}", exc_info=True)


def execute_query(query, params=None, fetch=False, fetchone=False, fetchall=False, auto_commit=None):
    """
    Выполняет запрос к базе данных (PostgreSQL или SQLite)
    Автоматически определяет тип БД и адаптирует запрос
    
    Args:
        auto_commit: автоматически фиксировать транзакцию (по умолчанию True для INSERT/UPDATE/DELETE, False для SELECT)
    """
    global _current_db_type

    max_retries = 2
    last_error = None
    
    for attempt in range(max_retries):
        conn = get_connection()
        db_type = DatabaseConnection.get_instance().db_type

        try:
            # Определяем тип базы данных и адаптируем запрос
            if db_type == "sqlite":
                # Для SQLite используем ? вместо %s
                sqlite_query = query.replace("%s", "?")

                # Преобразуем параметры в кортеж
                if params is None:
                    params = ()
                elif not isinstance(params, (tuple, list)):
                    params = (params,)

                cursor = conn.cursor()
                cursor.execute(sqlite_query, params)

                if fetchall:
                    # Преобразуем sqlite3.Row в кортежи для совместимости
                    result = [tuple(row) for row in cursor.fetchall()]
                elif fetchone:
                    row = cursor.fetchone()
                    result = tuple(row) if row else None
                elif fetch:
                    # Преобразуем sqlite3.Row в кортежи для совместимости
                    result = [tuple(row) for row in cursor.fetchall()]
                else:
                    result = None

                # Фиксируем только для модифицирующих запросов или если явно указано
                if auto_commit is True or (auto_commit is None and not query.strip().upper().startswith('SELECT')):
                    conn.commit()
                return result
            else:
                # PostgreSQL
                # psycopg2 нативно поддерживает UTF-8, избыточное кодирование не требуется
                # Преобразуем параметры в кортеж если нужно
                if params and not isinstance(params, tuple):
                    params = tuple(params)

                cursor = conn.cursor()

                # Convert placeholder to PostgreSQL-style %s
                query = query.replace("?", "%s")

                cursor.execute(query, params)

                if fetchall:
                    result = cursor.fetchall()
                elif fetchone:
                    result = cursor.fetchone()
                elif fetch:
                    result = cursor.fetchall()
                else:
                    result = None

                # Фиксируем только для модифицирующих запросов или если явно указано
                # Это ИЗБЕГАЕТ лишнего commit() для SELECT запросов
                if auto_commit is True or (auto_commit is None and not query.strip().upper().startswith('SELECT')):
                    conn.commit()
                return result

        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            # Проверяем, является ли ошибка разрывом соединения
            is_connection_error = any(keyword in error_str for keyword in [
                'server closed the connection unexpectedly',
                'consuming input failed',
                'connection already closed',
                'connection reset by peer',
                'broken pipe',
                'terminating connection',
                'no connection to the server'
            ])
            
            if is_connection_error and attempt < max_retries - 1:
                logger.warning(f"Разрыв соединения (попытка {attempt + 1}/{max_retries}): {e}")
                # Закрываем пул и пересоздаем
                try:
                    db_conn = DatabaseConnection.get_instance()
                    db_conn.close_all_connections()
                except Exception:
                    pass
                db_conn._initialize_connection_pool()
                continue
            else:
                logger.error(f"Ошибка выполнения запроса ({db_type}): {e}", exc_info=True)
                try:
                    if db_type == "sqlite" or not conn.closed:
                        conn.rollback()
                except Exception:
                    pass
                raise
        finally:
            # Завершаем транзакцию перед возвратом соединения в пул
            # Используем rollback для безопасности (не повредит данным SELECT)
            try:
                if db_type == "sqlite":
                    pass  # SQLite не требует проверки
                elif psycopg is not None:
                    # psycopg3
                    try:
                        if not conn.closed and conn.pq.status == psycopg.pq.TransactionStatus.INTRANS:
                            conn.rollback()
                    except Exception:
                        pass
                elif psycopg2 is not None and hasattr(conn, 'status'):
                    # psycopg2
                    if not conn.closed and conn.status == psycopg2.extensions.INTRANS:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
            except Exception:
                pass
            # Возвращаем соединение в пул вместо закрытия
            _release_connection(conn)
    
    if last_error:
        raise last_error


def execute_many(query, params_list):
    """
    Выполняет массовые запросы к базе данных (PostgreSQL или SQLite)
    Автоматически определяет тип БД и адаптирует запрос
    """
    max_retries = 2
    last_error = None
    
    for attempt in range(max_retries):
        conn = get_connection()
        db_type = DatabaseConnection.get_instance().db_type
        
        try:
            if db_type == "sqlite":
                # Для SQLite используем ? вместо %s
                sqlite_query = query.replace("%s", "?")
                
                cursor = conn.cursor()
                
                if params_list:
                    # Обрабатываем параметры для SQLite
                    processed_params_list = []
                    for params in params_list:
                        if isinstance(params, (list, tuple)):
                            processed_params = tuple(params)
                        else:
                            processed_params = (params,)
                        processed_params_list.append(processed_params)
                    
                    # Используем executemany для массового выполнения
                    cursor.executemany(sqlite_query, processed_params_list)
                else:
                    cursor.execute(sqlite_query)
                
                conn.commit()
                
            else:
                # PostgreSQL — используем execute_values для batch insert (в 10-50x быстрее)
                cursor = conn.cursor()

                # Convert placeholder to PostgreSQL-style %s if not already done
                if "?" in query:
                    query = query.replace("?", "%s")

                if params_list:
                    # Преобразуем параметры в кортежи
                    processed_params = []
                    for params in params_list:
                        if not isinstance(params, (tuple, list)):
                            processed_params.append((params,))
                        else:
                            processed_params.append(tuple(params))

                    # execute_values генерирует один большой INSERT с VALUES (...), (...), ...
                    if psycopg_extras is not None:
                        psycopg_extras.execute_values(
                            cursor, query, processed_params, page_size=1000
                        )
                    else:
                        # Fallback: обычный цикл если extras не доступен
                        for params in processed_params:
                            cursor.execute(query, params)
                else:
                    cursor.execute(query)

                conn.commit()
                
            return  # Успех, выходим из цикла
                
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            is_connection_error = any(keyword in error_str for keyword in [
                'server closed the connection unexpectedly',
                'consuming input failed',
                'connection already closed',
                'connection reset by peer',
                'broken pipe',
                'terminating connection',
                'no connection to the server'
            ])
            
            if is_connection_error and attempt < max_retries - 1:
                logger.warning(f"Разрыв соединения в execute_many (попытка {attempt + 1}/{max_retries}): {e}")
                try:
                    db_conn = DatabaseConnection.get_instance()
                    db_conn.close_all_connections()
                except Exception:
                    pass
                db_conn._initialize_connection_pool()
                continue
            else:
                logger.error(f"Ошибка выполнения массового запроса ({db_type}): {e}", exc_info=True)
                try:
                    if db_type == "sqlite" or not conn.closed:
                        conn.rollback()
                except Exception:
                    pass
                raise
        finally:
            _release_connection(conn)
    
    if last_error:
        raise last_error


def execute_transaction(queries_with_params):
    """
    Выполняет несколько запросов к базе данных в одной транзакции.
    Если один из запросов завершается ошибкой, вся транзакция откатывается.
    
    Args:
        queries_with_params: Список кортежей (query, params)
        
    Returns:
        Список результатов выполнения запросов (или None для запросов без результата)
        
    Raises:
        Exception: Пробрасывает оригинальное исключение при ошибке
    """
    max_retries = 2
    last_error = None
    
    for attempt in range(max_retries):
        conn = get_connection()
        db_type = DatabaseConnection.get_instance().db_type
        results = []
        
        try:
            # Определяем тип базы данных
            use_sqlite = db_type == "sqlite"
            
            if use_sqlite:
                # Для SQLite отключаем автокоммит на время транзакции
                # SQLite по умолчанию в режиме autocommit, управляем вручную
                cursor = conn.cursor()
                
                for query, params in queries_with_params:
                    # Для SQLite используем ? вместо %s
                    sqlite_query = query.replace("%s", "?")
                    
                    # Преобразуем параметры в кортеж
                    if params is None:
                        params = ()
                    elif not isinstance(params, (tuple, list)):
                        params = (params,)
                        
                    cursor.execute(sqlite_query, params)
                    
                    # Сохраняем результат если есть (для SELECT)
                    if cursor.description:
                        results.append([tuple(row) for row in cursor.fetchall()])
                    else:
                        results.append(None)
                
                # Коммитим транзакцию только если все запросы успешны
                conn.commit()
                
            else:
                # PostgreSQL
                cursor = conn.cursor()

                for query, params in queries_with_params:
                    # psycopg2 нативно поддерживает UTF-8, избыточное кодирование не требуется
                    # Преобразуем параметры в кортеж если нужно
                    if params and not isinstance(params, tuple):
                        params = tuple(params)

                    # Convert placeholder to PostgreSQL-style %s
                    query = query.replace("?", "%s")

                    cursor.execute(query, params)

                    # Сохраняем результат если есть (для SELECT)
                    if cursor.description:
                        results.append(cursor.fetchall())
                    else:
                        results.append(None)

                # Коммитим транзакцию только если все запросы успешны
                conn.commit()
            
            return results
            
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            is_connection_error = any(keyword in error_str for keyword in [
                'server closed the connection unexpectedly',
                'consuming input failed',
                'connection already closed',
                'connection reset by peer',
                'broken pipe',
                'terminating connection',
                'no connection to the server'
            ])
            
            if is_connection_error and attempt < max_retries - 1:
                logger.warning(f"Разрыв соединения в execute_transaction (попытка {attempt + 1}/{max_retries}): {e}")
                try:
                    db_conn = DatabaseConnection.get_instance()
                    db_conn.close_all_connections()
                except Exception:
                    pass
                db_conn._initialize_connection_pool()
                continue
            else:
                logger.error(f"Ошибка транзакции ({db_type}): {e}", exc_info=True)
                try:
                    if use_sqlite or not conn.closed:
                        conn.rollback()
                except Exception:
                    pass
                raise
        finally:
            _release_connection(conn)
    
    if last_error:
        raise last_error


class DatabaseTransaction:
    """
    Контекстный менеджер для управления транзакциями базы данных.
    Обеспечивает автоматическое получение и возврат соединения,
    а также коммит/откат транзакции.
    
    Пример использования:
        with DatabaseTransaction() as tx:
            tx.execute("INSERT INTO table VALUES (%s)", (value,))
            # Коммит произойдет автоматически при выходе из контекста
    """
    
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.db_type = None
        
    def __enter__(self):
        """Получить соединение при входе в контекст"""
        self.conn = get_connection()
        self.db_type = get_db_type()
        self.cursor = self.conn.cursor()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Обработка выхода из контекста"""
        try:
            if exc_type is None:
                # Если нет исключений, коммитим транзакцию
                if self.db_type == "sqlite" or not self.conn.closed:
                    self.conn.commit()
                logger.debug("Транзакция успешно закоммичена")
            else:
                # При ошибке откатываем транзакцию
                if self.db_type == "sqlite" or not self.conn.closed:
                    self.conn.rollback()
                logger.error(f"Транзакция откатана из-за ошибки: {exc_val}")
        except Exception as e:
            logger.error(f"Ошибка при завершении транзакции: {e}", exc_info=True)
        finally:
            # Закрываем курсор и возвращаем соединение в пул
            if self.cursor:
                try:
                    self.cursor.close()
                except Exception:
                    pass
            if self.conn:
                _release_connection(self.conn)

        # Не подавляем исключения (возвращаем False)
        return False
    
    def execute(self, query, params=None):
        """
        Выполнить SQL запрос
        
        Args:
            query: SQL запрос
            params: Параметры запроса
        """
        if self.cursor is None:
            raise RuntimeError("Курсор не инициализирован. Используйте в контексте 'with'")
        
        # Адаптируем запрос для типа БД
        if self.db_type == "sqlite":
            query = query.replace("%s", "?")
        
        # Преобразуем параметры
        if params and not isinstance(params, (tuple, list)):
            params = (params,)
        
        try:
            self.cursor.execute(query, params)
        except Exception as e:
            error_str = str(e).lower()
            is_connection_error = any(keyword in error_str for keyword in [
                'server closed the connection unexpectedly',
                'consuming input failed',
                'connection already closed',
                'connection reset by peer',
                'broken pipe',
                'terminating connection',
                'no connection to the server'
            ])
            if is_connection_error:
                logger.warning(f"Разрыв соединения в DatabaseTransaction: {e}")
                # Помечаем соединение как невалидное
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            raise
        
        return self.cursor
    
    def executemany(self, query, params_list):
        """
        Выполнить массовый SQL запрос
        Для PostgreSQL использует execute_values (в 10-50x быстрее)
        
        Args:
            query: SQL запрос
            params_list: Список параметров
        """
        if self.cursor is None:
            raise RuntimeError("Курсор не инициализирован")
        
        # Адаптируем запрос для типа БД
        if self.db_type == "sqlite":
            query = query.replace("%s", "?")
            self.cursor.executemany(query, params_list)
        else:
            # PostgreSQL — execute_values для batch insert
            query = query.replace("?", "%s")
            if psycopg_extras is not None:
                processed_params = [tuple(p) if not isinstance(p, tuple) else p for p in params_list]
                psycopg_extras.execute_values(
                    self.cursor, query, processed_params, page_size=1000
                )
            else:
                self.cursor.executemany(query, params_list)
        
        return self.cursor
    
    def fetchone(self):
        """Получить одну строку результата"""
        if self.cursor is None:
            raise RuntimeError("Курсор не инициализирован")
        return self.cursor.fetchone()
    
    def fetchall(self):
        """Получить все строки результата"""
        if self.cursor is None:
            raise RuntimeError("Курсор не инициализирован")
        return self.cursor.fetchall()


# Удобная функция для создания транзакции
def transaction():
    """
    Создать контекстный менеджер транзакции
    
    Returns:
        DatabaseTransaction: Контекстный менеджер
    """
    return DatabaseTransaction()
