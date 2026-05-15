# database.py
import json
import logging
from pathlib import Path
import config  # Добавляем импорт config
from db_connection import execute_query, execute_many, get_connection, _release_connection, get_db_type
# PostgreSQL is the only supported database

logger = logging.getLogger(__name__)


_product_names_cache = {}
_product_names_cache_ttl = {}
_PRODUCT_NAMES_CACHE_SECONDS = 60

def get_product_names_by_barcodes(barcodes):
   """
   Получает наименования товаров по списку штрихкодов из PostgreSQL
   Возвращает словарь {штрихкод: наименование}
   Отдаёт приоритет данным из таблицы sku, при их отсутствии использует shipment_items
   Кэширует результаты для уменьшения запросов к удалённой БД
   """
   global _product_names_cache, _product_names_cache_ttl
   try:
       if not barcodes:
           return {}

       import time
       now = time.time()
       
       # Проверяем кэш — берём только те штрихкоды, которых нет в кэше или устарели
       uncached_barcodes = []
       for bc in barcodes:
           if bc not in _product_names_cache or (bc in _product_names_cache_ttl and now - _product_names_cache_ttl[bc] > _PRODUCT_NAMES_CACHE_SECONDS):
               uncached_barcodes.append(bc)
       
       # Если всё в кэше — возвращаем из кэша
       result = {}
       if not uncached_barcodes:
           for bc in barcodes:
               if bc in _product_names_cache:
                   result[bc] = _product_names_cache[bc]
           return result
       
       # Запрашиваем только отсутствующие в кэше
       placeholders = ','.join(['%s'] * len(uncached_barcodes))

       db_type = get_db_type()
       
       if db_type == "sqlite":
           placeholders = ','.join(['?'] * len(uncached_barcodes))
           query = f"""
               SELECT barcode, MIN(name) as name
               FROM (
                   SELECT barcode, name, 1 as priority
                   FROM sku
                   WHERE barcode IN ({placeholders})
                   AND name IS NOT NULL
                   AND name != ''

                   UNION ALL

                   SELECT si.barcode, si.sku as name, 2 as priority
                   FROM shipment_items si
                   WHERE si.barcode IN ({placeholders})
                   AND si.sku IS NOT NULL
                   AND si.sku != ''
                   AND NOT EXISTS (
                       SELECT 1 FROM sku s
                       WHERE s.barcode = si.barcode
                       AND s.name IS NOT NULL
                       AND s.name != ''
                   )
               ) AS combined
               GROUP BY barcode
               ORDER BY barcode
           """
       else:
           query = f"""
               SELECT DISTINCT ON (barcode) barcode, name
               FROM (
                   SELECT barcode, name, 1 as priority
                   FROM sku
                   WHERE barcode IN ({placeholders})
                   AND name IS NOT NULL
                   AND name != ''

                   UNION ALL

                   SELECT si.barcode, si.sku as name, 2 as priority
                   FROM shipment_items si
                   WHERE si.barcode IN ({placeholders})
                   AND si.sku IS NOT NULL
                   AND si.sku != ''
                   AND NOT EXISTS (
                       SELECT 1 FROM sku s
                       WHERE s.barcode = si.barcode
                       AND s.name IS NOT NULL
                       AND s.name != ''
                   )
               ) AS combined
               ORDER BY barcode, priority
           """

       results = execute_query(query, uncached_barcodes * 2, fetchall=True)

       name_dict = {}
       for barcode, name in results:
           if barcode and name:
               name_dict[barcode] = name
               _product_names_cache[barcode] = name
               _product_names_cache_ttl[barcode] = now

       # Добавляем кэшированные значения
       for bc in barcodes:
           if bc in _product_names_cache and bc not in name_dict:
               name_dict[bc] = _product_names_cache[bc]

       return name_dict
   except Exception as e:
       logger.error(f"Ошибка при получении наименований по штрихкодам: {e}", exc_info=True)
       return {}

       placeholders = ','.join(['%s'] * len(barcodes))

       # Для SQLite используем GROUP BY вместо DISTINCT ON
       db_type = get_db_type()
       
       if db_type == 'sqlite':
           # Для SQLite используем GROUP BY вместо DISTINCT ON
           placeholders = ','.join(['?'] * len(barcodes))
           query = f"""
               SELECT barcode, MIN(name) as name
               FROM (
                   -- Сначала берём все записи из sku с приоритетом 1
                   SELECT barcode, name, 1 as priority
                   FROM sku
                   WHERE barcode IN ({placeholders})
                   AND name IS NOT NULL
                   AND name != ''

                   UNION ALL

                   -- Потом берём записи из shipment_items только для тех баркодов, которых нет в sku
                   SELECT si.barcode, si.sku as name, 2 as priority
                   FROM shipment_items si
                   WHERE si.barcode IN ({placeholders})
                   AND si.sku IS NOT NULL
                   AND si.sku != ''
                   AND NOT EXISTS (
                       SELECT 1 FROM sku s
                       WHERE s.barcode = si.barcode
                       AND s.name IS NOT NULL
                       AND s.name != ''
                   )
               ) AS combined
               GROUP BY barcode
               ORDER BY barcode
           """
       else:
           # Для PostgreSQL используем DISTINCT ON
           query = f"""
               SELECT DISTINCT ON (barcode) barcode, name
               FROM (
                   -- Сначала берём все записи из sku с приоритетом 1
                   SELECT barcode, name, 1 as priority
                   FROM sku
                   WHERE barcode IN ({placeholders})
                   AND name IS NOT NULL
                   AND name != ''

                   UNION ALL

                   -- Потом берём записи из shipment_items только для тех баркодов, которых нет в sku
                   SELECT si.barcode, si.sku as name, 2 as priority
                   FROM shipment_items si
                   WHERE si.barcode IN ({placeholders})
                   AND si.sku IS NOT NULL
                   AND si.sku != ''
                   AND NOT EXISTS (
                       SELECT 1 FROM sku s
                       WHERE s.barcode = si.barcode
                       AND s.name IS NOT NULL
                       AND s.name != ''
                   )
               ) AS combined
               ORDER BY barcode, priority
           """

       results = execute_query(query, barcodes * 2, fetchall=True)

       name_dict = {}
       for barcode, name in results:
           if barcode and name:
               name_dict[barcode] = name

       logger.info(f"Получены наименования для {len(name_dict)} из {len(barcodes)} штрихкодов")
       return name_dict
   except Exception as e:
       logger.error(f"Ошибка при получении наименований по штрихкодам: {e}", exc_info=True)
       return {}


_stock_qty_cache = {}
_stock_qty_cache_ttl = {}
_STOCK_QTY_CACHE_SECONDS = 60

def get_stock_cache(barcode):
    """Получает кэшированное количество остатков для штрихкода (с локальным кэшем)"""
    global _stock_qty_cache, _stock_qty_cache_ttl
    import time
    now = time.time()
    if barcode in _stock_qty_cache and barcode in _stock_qty_cache_ttl:
        if now - _stock_qty_cache_ttl[barcode] < _STOCK_QTY_CACHE_SECONDS:
            return _stock_qty_cache[barcode]
    try:
        result = execute_query(
            "SELECT quantity FROM stock_cache WHERE barcode = %s",
            (barcode,),
            fetchone=True
        )
        qty = result[0] if result else None
        _stock_qty_cache[barcode] = qty
        _stock_qty_cache_ttl[barcode] = now
        return qty
    except Exception as e:
        logger.error(f"Ошибка получения кэша остатков для {barcode}: {e}")
        return None


def set_stock_cache(barcode, quantity):
   """Обновляет кэшированное количество остатков для штрихкода"""
   try:
       db_type = get_db_type()
       if db_type == "sqlite":
           execute_query(
               """
               INSERT OR REPLACE INTO stock_cache (barcode, quantity)
               VALUES (?, ?)
               """,
               (barcode, quantity)
           )
       else:
           execute_query(
               """
               INSERT INTO stock_cache (barcode, quantity)
               VALUES (%s, %s)
               ON CONFLICT (barcode) DO UPDATE SET quantity = EXCLUDED.quantity
               """,
               (barcode, quantity)
           )
   except Exception as e:
       logger.error(f"Ошибка обновления кэша остатков для {barcode}: {e}")


def init_db():
   try:
       logger.info("Начало инициализации базы данных")
       conn = get_connection()
       db_type = get_db_type()
       use_sqlite = db_type == "sqlite"

       try:
           cursor = conn.cursor()

           # Определяем тип БД и выбираем синтаксис
           # Типы данных в зависимости от БД
           int_type = "INTEGER" if use_sqlite else "SERIAL"
           # Используем TEXT для PostgreSQL чтобы избежать ограничений VARCHAR
           str_type = "TEXT" if use_sqlite else "TEXT"
           bool_type = "INTEGER DEFAULT 0" if use_sqlite else "BOOLEAN DEFAULT FALSE"
           bool_true = "1" if use_sqlite else "TRUE"
           bool_false = "0" if use_sqlite else "FALSE"
           empty_json = "'{}'"  # Для обоих типов БД
           # AUTOINCREMENT нужен только для SQLite, для SERIAL в PostgreSQL не требуется
           autoincrement = "AUTOINCREMENT" if use_sqlite else ""

           # Таблица поставок
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS shipments (
                   id {int_type} PRIMARY KEY {autoincrement},
                   destination_name {str_type} NOT NULL UNIQUE,
                   font_size INTEGER DEFAULT 10,
                   label_font_size INTEGER DEFAULT 20,
                   theme {str_type} DEFAULT 'Светлая',
                   removed_items TEXT DEFAULT {empty_json},
                   parent_group {str_type} DEFAULT NULL,
                   properties TEXT DEFAULT {empty_json},
                   archived {bool_type},
                   archived_date TIMESTAMP DEFAULT NULL,
                   archived_by {str_type} DEFAULT NULL
               )
           """)

           # Таблица товаров поставки
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS shipment_items (
                   id {int_type} PRIMARY KEY {autoincrement},
                   shipment_id INTEGER NOT NULL,
                   barcode {str_type} NOT NULL,
                   sku {str_type} NOT NULL,
                   total_qty INTEGER NOT NULL,
                   allocated_qty INTEGER NOT NULL DEFAULT 0,
                   FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
               )
           """)

           # Таблица коробок
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS boxes (
                   id {int_type} PRIMARY KEY {autoincrement},
                   shipment_id INTEGER NOT NULL,
                   box_id {str_type} NOT NULL,
                   is_current {bool_type},
                   FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
                   UNIQUE(shipment_id, box_id)
               )
           """)

           # Таблица товаров в коробках
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS box_items (
                   id {int_type} PRIMARY KEY {autoincrement},
                   box_id INTEGER NOT NULL,
                   barcode {str_type} NOT NULL,
                   qty INTEGER NOT NULL,
                   FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE CASCADE,
                   UNIQUE(box_id, barcode)
               )
           """)

           # Добавляем уникальные ограничения для PostgreSQL если они не были созданы
           # Примечание: UNIQUE уже указан в CREATE TABLE, но для старых баз добавляем отдельно
           if db_type == 'postgresql':
               try:
                   # Проверяем, существует ли уже ограничение
                   cursor.execute("""
                       SELECT constraint_name FROM information_schema.table_constraints
                       WHERE table_schema = 'public'
                       AND table_name = 'boxes'
                       AND constraint_type = 'UNIQUE'
                       AND constraint_name = 'boxes_shipment_id_box_id_unique'
                   """)
                   if not cursor.fetchone():
                       cursor.execute("""
                           ALTER TABLE boxes
                           ADD CONSTRAINT boxes_shipment_id_box_id_unique
                           UNIQUE (shipment_id, box_id)
                       """)
                       logger.info("Добавлено уникальное ограничение для boxes(shipment_id, box_id)")
               except Exception as e:
                   logger.debug(f"Ограничение для boxes уже существует или ошибка: {e}")

               try:
                   # Проверяем, существует ли уже ограничение
                   cursor.execute("""
                       SELECT constraint_name FROM information_schema.table_constraints
                       WHERE table_schema = 'public'
                       AND table_name = 'box_items'
                       AND constraint_type = 'UNIQUE'
                       AND constraint_name = 'box_items_box_id_barcode_unique'
                   """)
                   if not cursor.fetchone():
                       cursor.execute("""
                           ALTER TABLE box_items
                           ADD CONSTRAINT box_items_box_id_barcode_unique
                           UNIQUE (box_id, barcode)
                       """)
                       logger.info("Добавлено уникальное ограничение для box_items(box_id, barcode)")
               except Exception as e:
                   # Ограничение может уже существовать
                   logger.debug(f"Ограничение для box_items уже существует или ошибка: {e}")

               # Добавляем уникальное ограничение для shipment_items (shipment_id, barcode)
               try:
                   cursor.execute("""
                       SELECT constraint_name FROM information_schema.table_constraints
                       WHERE table_schema = 'public'
                       AND table_name = 'shipment_items'
                       AND constraint_type = 'UNIQUE'
                       AND constraint_name = 'shipment_items_shipment_id_barcode_unique'
                   """)
                   if not cursor.fetchone():
                       cursor.execute("""
                           ALTER TABLE shipment_items
                           ADD CONSTRAINT shipment_items_shipment_id_barcode_unique
                           UNIQUE (shipment_id, barcode)
                       """)
                       logger.info("Добавлено уникальное ограничение для shipment_items(shipment_id, barcode)")
               except Exception as e:
                   logger.debug(f"Ограничение для shipment_items уже существует или ошибка: {e}")

           # Таблица настроек приложения
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS app_settings (
                   key {str_type} PRIMARY KEY,
                   value TEXT
               )
           """)

           # Таблица состояния окон
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS window_state (
                   key {str_type} PRIMARY KEY,
                   value TEXT
               )
           """)

           # Таблица пользователей
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS users (
                   id {int_type} PRIMARY KEY,
                   username {str_type} UNIQUE NOT NULL,
                   font_size INTEGER DEFAULT 10,
                   label_font_size INTEGER DEFAULT 20,
                   theme {str_type} DEFAULT 'Светлая',
                   ok_sound {str_type} DEFAULT 'ok.wav',
                   error_sound {str_type} DEFAULT 'error.wav',
                   tone_sound {bool_type},
                   sound_volume INTEGER DEFAULT 100,
                   shipment_columns_width TEXT DEFAULT '',
                   box_columns_width TEXT DEFAULT '',
                   main_splitter_sizes TEXT DEFAULT '',
                   window_width INTEGER DEFAULT 1300,
                   window_height INTEGER DEFAULT 800,
                   button_primary_color {str_type} DEFAULT '',
                   button_success_color {str_type} DEFAULT '',
                   button_warning_color {str_type} DEFAULT '',
                   button_danger_color {str_type} DEFAULT '',
                   button_colors TEXT DEFAULT ''
               )
           """)

           # Таблица сессий пользователей
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS user_sessions (
                   id {int_type} PRIMARY KEY,
                   shipment_name {str_type} NOT NULL,
                   username {str_type} NOT NULL,
                   last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   UNIQUE (shipment_name, username)
               )
           """)

           # Создаем индексы отдельно
           try:
               cursor.execute("CREATE INDEX IF NOT EXISTS idx_shipment_name ON user_sessions(shipment_name)")
           except Exception as e:
               logger.debug(f"Индекс idx_shipment_name уже существует или произошла ошибка: {e}")
           try:
               cursor.execute("CREATE INDEX IF NOT EXISTS idx_last_activity ON user_sessions(last_activity)")
           except Exception as e:
               logger.debug(f"Индекс idx_last_activity уже существует или произошла ошибка: {e}")

           # Создаем таблицу stock_cache если не существует
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS stock_cache (
                   barcode {str_type} PRIMARY KEY,
                   quantity INTEGER DEFAULT 0,
                   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
               )
           """)

           # Создаем таблицу sku если не существует
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS sku (
                   barcode {str_type} PRIMARY KEY,
                   name {str_type},
                   article {str_type},
                   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
               )
           """)

           # Таблица блокировок товаров (для защиты от конфликтов при одновременной работе)
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS item_locks (
                   barcode {str_type} NOT NULL,
                   shipment_id INTEGER NOT NULL,
                   username {str_type} NOT NULL,
                   locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   expires_at TIMESTAMP NOT NULL,
                   PRIMARY KEY (barcode, shipment_id)
               )
           """)

           # Таблица для синхронизации кэшей между клиентами
           cursor.execute(f"""
               CREATE TABLE IF NOT EXISTS cache_invalidation (
                   id {int_type} PRIMARY KEY {autoincrement},
                   shipment_id INTEGER NOT NULL,
                   tables_changed TEXT NOT NULL,
                   invalidated_by {str_type},
                   invalidated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
               )
           """)

           # Создаем индексы для ускорения поиска по barcode
           # Индексы создаются отдельно для каждой СУБД после создания всех таблиц

           # Один коммит в конце для всех операций
           conn.commit()

           # Для SQLite добавляем отсутствующие колонки если таблица уже существовала
           if use_sqlite:
               try:
                   _add_missing_columns_to_users_table(conn)
                   _create_missing_tables_for_sqlite(conn)
                   _add_version_columns_to_tables(conn)
               except Exception as e:
                   logger.error(f"Ошибка миграции SQLite: {e}")
                   conn.rollback()
           else:
               # Для PostgreSQL добавляем отсутствующие колонки и ограничения
               try:
                   _add_missing_columns_to_users_table_postgresql(conn)
                   _add_version_columns_to_tables(conn)
                   # commit вызывается внутри функции перед _clear_connection_pool
               except Exception as e:
                   logger.error(f"Ошибка добавления колонок PostgreSQL: {e}")
                   try:
                       if not conn.closed:
                           conn.rollback()
                   except Exception:
                       pass

               try:
                   _add_unique_constraint_to_user_sessions_postgresql(conn)
                   # commit вызывается внутри функции
               except Exception as e:
                   logger.error(f"Ошибка добавления ограничения PostgreSQL: {e}")
                   try:
                       if not conn.closed:
                           conn.rollback()
                   except Exception:
                       pass

               try:
                   _add_indexes_to_postgresql(conn)
                   # commit вызывается внутри функции
               except Exception as e:
                   logger.error(f"Ошибка создания индексов PostgreSQL: {e}")
                   try:
                       if not conn.closed:
                           conn.rollback()
                   except Exception:
                       pass

           logger.info("Инициализация базы данных завершена успешно")
       except Exception as e:
           logger.error(f"Ошибка при инициализации БД: {e}", exc_info=True)
           if not use_sqlite:
               # Проверяем, не закрыто ли соединение перед rollback
               try:
                   if not conn.closed:
                       conn.rollback()
               except Exception:
                   pass
           raise
       finally:
           # Возвращаем соединение в пул вместо закрытия
           # Проверяем, не закрыто ли соединение
           try:
               if use_sqlite:
                   _release_connection(conn)
               else:
                   if not conn.closed:
                       _release_connection(conn)
           except Exception:
               pass
   except Exception as e:
       logger.error(f"Ошибка инициализации базы данных: {e}", exc_info=True)
       # Не прерываем работу приложения из-за ошибки инициализации базы данных
       pass

def _add_missing_columns_to_users_table(conn):
    """Добавляет отсутствующие колонки в таблицу users для SQLite"""
    try:
        cursor = conn.cursor()

        # Миграция для таблицы shipments - пересоздание с AUTOINCREMENT для SQLite
        # Сначала проверяем, есть ли записи с NULL id
        cursor.execute("SELECT COUNT(*) FROM shipments WHERE id IS NULL")
        null_id_count = cursor.fetchone()[0]
        if null_id_count > 0:
            logger.info(f"Найдено {null_id_count} записей с NULL id в таблице shipments, удаляем их")
            cursor.execute("DELETE FROM shipments WHERE id IS NULL")
            conn.commit()

        # Проверяем тип БД и структуру таблицы
        db_type = get_db_type()
        if db_type == "sqlite":
            cursor.execute("PRAGMA table_info(shipments)")
            columns = cursor.fetchall()
            id_column = None
            for col in columns:
                if col[1] == 'id':
                    id_column = col
                    break

            # Для SQLite проверяем, что id имеет тип INTEGER и AUTOINCREMENT
            need_recreate = False
            if id_column:
                col_type = id_column[2]  # Тип колонки
                if col_type != 'INTEGER' or 'AUTOINCREMENT' not in (id_column[5] or ''):
                    need_recreate = True
                    logger.info(f"Таблица shipments требует пересоздания: тип={col_type}, autoinc={id_column[5]}")
        else:
            # PostgreSQL: проверяем наличие и тип колонки id через information_schema
            cursor.execute("""
                SELECT data_type, column_default FROM information_schema.columns
                WHERE table_name = 'shipments' AND column_name = 'id'
            """)
            result = cursor.fetchone()
            need_recreate = False
            if result:
                data_type, column_default = result
                # В PostgreSQL SERIAL использует nextval() для default
                if data_type != 'integer' or not (column_default and 'nextval' in column_default.lower()):
                    need_recreate = True
                    logger.info(f"Таблица shipments требует пересоздания: тип={data_type}, default={column_default}")
            else:
                need_recreate = True
                logger.info("Таблица shipments не существует")
        
        if need_recreate:
            # Нужно пересоздать таблицу с AUTOINCREMENT
            logger.info("Пересоздание таблицы shipments с AUTOINCREMENT")
            
            # Получаем все данные (исключая записи с NULL id)
            cursor.execute("SELECT * FROM shipments WHERE id IS NOT NULL")
            data = cursor.fetchall()
            
            # Переименовываем таблицу
            cursor.execute("ALTER TABLE shipments RENAME TO shipments_old")
            
            # Создаём новую таблицу
            cursor.execute("""
                CREATE TABLE shipments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    destination_name TEXT NOT NULL UNIQUE,
                    font_size INTEGER DEFAULT 10,
                    label_font_size INTEGER DEFAULT 20,
                    theme TEXT DEFAULT 'Светлая',
                    removed_items TEXT DEFAULT '{}',
                    parent_group TEXT DEFAULT NULL,
                    properties TEXT DEFAULT '{}',
                    archived INTEGER,
                    archived_date TIMESTAMP DEFAULT NULL,
                    archived_by TEXT DEFAULT NULL
                )
            """)
            
            # Вставляем данные обратно
            if data:
                cursor.executemany("""
                    INSERT INTO shipments (id, destination_name, font_size, label_font_size, theme,
                                          removed_items, parent_group, properties, archived, archived_date, archived_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
            
            # Удаляем старую таблицу
            cursor.execute("DROP TABLE IF EXISTS shipments_old")
            conn.commit()
            logger.info("Таблица shipments пересоздана с AUTOINCREMENT")
            
            # Исправляем внешние ключи в связанных таблицах
            logger.info("Исправление внешних ключей в связанных таблицах")
            
            # Пересоздаём таблицу shipment_items с правильным FK
            cursor.execute("SELECT * FROM shipment_items")
            items_data = cursor.fetchall()
            cursor.execute("DROP TABLE shipment_items")
            cursor.execute("""
                CREATE TABLE shipment_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shipment_id INTEGER,
                    barcode TEXT,
                    sku TEXT,
                    total_qty INTEGER DEFAULT 0,
                    allocated_qty INTEGER DEFAULT 0,
                    FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
                )
            """)
            if items_data:
                cursor.executemany("""
                    INSERT INTO shipment_items (id, shipment_id, barcode, sku, total_qty, allocated_qty)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, items_data)
            
            # Пересоздаём таблицу boxes с правильным FK
            cursor.execute("SELECT * FROM boxes")
            boxes_data = cursor.fetchall()
            cursor.execute("DROP TABLE boxes")
            cursor.execute("""
                CREATE TABLE boxes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shipment_id INTEGER,
                    box_id TEXT,
                    is_current INTEGER DEFAULT 0,
                    FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
                )
            """)
            if boxes_data:
                cursor.executemany("""
                    INSERT INTO boxes (id, shipment_id, box_id, is_current)
                    VALUES (?, ?, ?, ?)
                """, boxes_data)
            
            # Пересоздаём таблицу box_items с правильным FK и уникальным ограничением
            cursor.execute("SELECT * FROM box_items")
            box_items_data = cursor.fetchall()
            cursor.execute("DROP TABLE box_items")
            cursor.execute("""
                CREATE TABLE box_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    box_id INTEGER NOT NULL,
                    barcode TEXT NOT NULL,
                    qty INTEGER NOT NULL,
                    FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE CASCADE,
                    UNIQUE(box_id, barcode)
                )
            """)
            if box_items_data:
                # Преобразуем старые данные (sku, quantity) в новый формат (qty)
                for row in box_items_data:
                    # row: (id, box_id, barcode, sku, quantity)
                    cursor.execute("""
                        INSERT INTO box_items (id, box_id, barcode, qty)
                        VALUES (?, ?, ?, ?)
                    """, (row[0], row[1], row[2], row[4] if len(row) > 4 else 0))
            
            conn.commit()
            logger.info("Внешние ключи в связанных таблицах исправлены")

            # Очищаем пул соединений, чтобы новые соединения использовали обновлённую схему
            try:
                from db_connection import _clear_connection_pool
                _clear_connection_pool()
                logger.info("Пул соединений очищен после пересоздания таблицы shipments")
            except Exception as e:
                logger.warning(f"Не удалось очистить пул соединений: {e}")

        # Список колонок которые должны быть в таблице users
        expected_columns = [
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
            ('colored_buttons', 'INTEGER DEFAULT 1'),
            ('tone_sound', 'INTEGER DEFAULT 0'),
            ('sound_volume', 'INTEGER DEFAULT 100')
        ]

        # Получаем список существующих колонок
        db_type = get_db_type()
        if db_type == "sqlite":
            cursor.execute("PRAGMA table_info(users)")
            columns_info = cursor.fetchall()
            # PRAGMA table_info возвращает кортежи: (cid, name, type, notnull, dflt_value, pk)
            existing_columns = [col[1] for col in columns_info] if columns_info else []
        else:
            # PostgreSQL: используем information_schema
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users'
            """)
            existing_columns = [col[0] for col in cursor.fetchall()]

        # Добавляем отсутствующие колонки
        for col_name, col_def in expected_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Добавлена колонка {col_name} в таблицу users")
                except Exception as e:
                    logger.debug(f"Ошибка при добавлении колонки {col_name}: {e}")

        conn.commit()
        
        # Очищаем пул соединений, чтобы новые соединения использовали обновлённую схему
        try:
            from db_connection import _clear_connection_pool
            _clear_connection_pool()
            logger.info("Пул соединений очищен после добавления колонок в таблицу users")
        except Exception as e:
            logger.warning(f"Не удалось очистить пул соединений: {e}")
    except Exception as e:
        logger.error(f"Ошибка при добавлении колонок в таблицу users: {e}")

def _add_missing_columns_to_users_table_postgresql(conn):
    """Добавляет отсутствующие колонки в таблицу users для PostgreSQL"""
    try:
        cursor = conn.cursor()

        # Проверяем тип поля username и изменяем на TEXT если он VARCHAR(50)
        cursor.execute("""
            SELECT data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'username' AND table_schema = 'public'
        """)
        username_info = cursor.fetchone()
        if username_info:
            data_type, char_max_length = username_info
            # Если VARCHAR с длиной 50, изменяем на TEXT
            if data_type == 'character varying' and char_max_length == 50:
                logger.info("Изменение типа поля username с VARCHAR(50) на TEXT")
                cursor.execute("ALTER TABLE users ALTER COLUMN username TYPE TEXT")
                conn.commit()
                logger.info("Поле username изменено на TEXT")

        # Проверяем тип поля tone_sound и изменяем на BOOLEAN если он INTEGER
        cursor.execute("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'tone_sound' AND table_schema = 'public'
        """)
        tone_sound_info = cursor.fetchone()
        if tone_sound_info:
            data_type = tone_sound_info[0]
            if data_type == 'integer':
                logger.info("Изменение типа поля tone_sound с INTEGER на BOOLEAN")
                cursor.execute("ALTER TABLE users ALTER COLUMN tone_sound TYPE BOOLEAN")
                conn.commit()
                logger.info("Поле tone_sound изменено на BOOLEAN")

        # Проверяем и изменяем типы других boolean полей с INTEGER на BOOLEAN
        bool_columns = [
            ('moysklad_enabled', 'INTEGER'),
            ('shipment_locking_enabled', 'INTEGER'),
            ('article_column_visible', 'INTEGER'),
            ('name_column_visible', 'INTEGER'),
            ('stock_column_visible', 'INTEGER'),
            ('hide_completed_items', 'INTEGER'),
            ('total_qty_column_visible', 'INTEGER'),
            ('colored_buttons', 'INTEGER')
        ]

        for col_name, old_type in bool_columns:
            cursor.execute("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = %s AND table_schema = 'public'
            """, (col_name,))
            col_info = cursor.fetchone()
            if col_info and col_info[0] == old_type:
                logger.info(f"Изменение типа поля {col_name} с INTEGER на BOOLEAN")
                cursor.execute(f"ALTER TABLE users ALTER COLUMN {col_name} TYPE BOOLEAN")
                conn.commit()
                logger.info(f"Поле {col_name} изменено на BOOLEAN")

        # Список колонок которые должны быть в таблице users
        expected_columns = [
            ('moysklad_token', 'TEXT DEFAULT \'\''),
            ('moysklad_stores', 'TEXT DEFAULT \'\''),
            ('moysklad_enabled', 'BOOLEAN DEFAULT FALSE'),
            ('shipment_locking_enabled', 'BOOLEAN DEFAULT FALSE'),
            ('article_column_visible', 'BOOLEAN DEFAULT TRUE'),
            ('name_column_visible', 'BOOLEAN DEFAULT FALSE'),
            ('stock_column_visible', 'BOOLEAN DEFAULT TRUE'),
            ('hide_completed_items', 'BOOLEAN DEFAULT FALSE'),
            ('total_qty_column_visible', 'BOOLEAN DEFAULT TRUE'),
            ('button_colors', 'TEXT DEFAULT \'\''),
            ('colored_buttons', 'BOOLEAN DEFAULT TRUE'),
            ('tone_sound', 'BOOLEAN DEFAULT FALSE'),
            ('sound_volume', 'INTEGER DEFAULT 100'),
            ('cached_server_ip', 'TEXT DEFAULT \'\''),
            ('encoded_button_colors', 'TEXT DEFAULT \'\'')
        ]

        # Получаем список существующих колонок из information_schema
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users' AND table_schema = 'public'
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]

        # Добавляем отсутствующие колонки
        for col_name, col_def in expected_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Добавлена колонка {col_name} в таблицу users (PostgreSQL)")
                except Exception as e:
                    logger.debug(f"Ошибка при добавлении колонки {col_name}: {e}")

        # commit() вызывается в вызывающей функции (init_db)
        # Очищаем пул соединений, чтобы новые соединения использовали обновлённую схему
        try:
            from db_connection import _clear_connection_pool
            _clear_connection_pool()
            logger.info("Пул соединений очищен после добавления колонок в таблицу users (PostgreSQL)")
        except Exception as e:
            logger.warning(f"Не удалось очистить пул соединений: {e}")
    except Exception as e:
        logger.error(f"Ошибка при добавлении колонок в таблицу users (PostgreSQL): {e}")
        raise

def _add_unique_constraint_to_user_sessions_postgresql(conn):
    """Добавляет уникальное ограничение на (shipment_name, username) в таблицу user_sessions"""
    try:
        cursor = conn.cursor()

        # Проверяем, существует ли уже ограничение
        cursor.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'user_sessions'
            AND constraint_type = 'UNIQUE'
        """)
        constraints = cursor.fetchall()

        # Проверяем, есть ли уже уникальное ограничение на нужных колонках
        has_unique = False
        for constraint in constraints:
            constraint_name = constraint[0]
            # Проверяем колонки этого ограничения
            cursor.execute("""
                SELECT column_name
                FROM information_schema.key_column_usage
                WHERE constraint_name = %s
                ORDER BY ordinal_position
            """, (constraint_name,))
            columns = [row[0] for row in cursor.fetchall()]
            if set(columns) == {'shipment_name', 'username'}:
                has_unique = True
                break
        
        if not has_unique:
            # Сначала удалим дубликаты если есть
            cursor.execute("""
                DELETE FROM user_sessions a USING (
                    SELECT MIN(ctid) as ctid, shipment_name, username
                    FROM user_sessions
                    GROUP BY shipment_name, username
                    HAVING COUNT(*) > 1
                ) b
                WHERE a.shipment_name = b.shipment_name
                AND a.username = b.username
                AND a.ctid <> b.ctid
            """)
            logger.info("Удалены дубликаты из user_sessions если существовали")

            # Добавляем уникальное ограничение
            cursor.execute("""
                ALTER TABLE user_sessions
                ADD CONSTRAINT unique_shipment_username UNIQUE (shipment_name, username)
            """)
            logger.info("Добавлено уникальное ограничение на (shipment_name, username) в user_sessions (PostgreSQL)")
            conn.commit()
        else:
            logger.debug("Уникальное ограничение уже существует в user_sessions")
            conn.commit()
    except Exception as e:
        logger.debug(f"Ошибка при добавлении уникального ограничения: {e}")
        raise


def _add_indexes_to_postgresql(conn):
    """Добавляет индексы в существующую базу данных PostgreSQL"""
    try:
        cursor = conn.cursor()

        # Список индексов для создания
        indexes = [
            ("idx_shipment_items_barcode", "shipment_items", "barcode"),
            ("idx_box_items_barcode", "box_items", "barcode"),
            ("idx_stock_cache_barcode", "stock_cache", "barcode"),
            ("idx_shipment_items_shipment_id", "shipment_items", "shipment_id"),
            ("idx_boxes_shipment_id", "boxes", "shipment_id"),
            ("idx_box_items_box_id", "box_items", "box_id"),
            ("idx_user_sessions_shipment_name", "user_sessions", "shipment_name"),
            ("idx_user_sessions_username", "user_sessions", "username"),
            ("idx_item_locks_barcode", "item_locks", "barcode"),
            ("idx_item_locks_shipment_id", "item_locks", "shipment_id"),
            ("idx_item_locks_expires", "item_locks", "expires_at"),
            ("idx_cache_invalidation_shipment_id", "cache_invalidation", "shipment_id"),
            ("idx_cache_invalidation_invalidated_at", "cache_invalidation", "invalidated_at"),
        ]

        for index_name, table_name, column_name in indexes:
            try:
                # Проверяем, существует ли уже индекс
                cursor.execute("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    AND tablename = %s
                    AND indexname = %s
                """, (table_name, index_name))

                if not cursor.fetchone():
                    # Создаем индекс
                    cursor.execute(f"""
                        CREATE INDEX {index_name}
                        ON public.{table_name}({column_name})
                    """)
                    logger.info(f"Создан индекс {index_name} для таблицы {table_name}")
                else:
                    logger.debug(f"Индекс {index_name} уже существует")
            except Exception as e:
                logger.debug(f"Ошибка при создании индекса {index_name}: {e}")

        conn.commit()
        logger.info("Индексы PostgreSQL добавлены")
    except Exception as e:
        logger.error(f"Ошибка при добавлении индексов PostgreSQL: {e}")
        raise


def _migrate_database_to_autoincrement(conn):
    """Миграция базы данных для добавления AUTOINCREMENT к таблицам"""
    try:
        cursor = conn.cursor()
        
        # Сохраняем данные из таблиц перед пересозданием
        logger.info("Сохранение данных для миграции...")
        
        # Сохраняем данные из shipments
        cursor.execute("SELECT * FROM shipments")
        shipments_data = cursor.fetchall()
        
        # Сохраняем данные из shipment_items
        cursor.execute("SELECT * FROM shipment_items")
        shipment_items_data = cursor.fetchall()
        
        # Сохраняем данные из boxes
        cursor.execute("SELECT * FROM boxes")
        boxes_data = cursor.fetchall()
        
        # Сохраняем данные из box_items
        cursor.execute("SELECT * FROM box_items")
        box_items_data = cursor.fetchall()
        
        logger.info(f"Сохранено: {len(shipments_data)} поставок, {len(shipment_items_data)} товаров, {len(boxes_data)} коробок, {len(box_items_data)} товаров в коробках")
        
        # Включаем внешние ключи
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Переименовываем старые таблицы
        cursor.execute("ALTER TABLE shipments RENAME TO shipments_old")
        cursor.execute("ALTER TABLE shipment_items RENAME TO shipment_items_old")
        cursor.execute("ALTER TABLE boxes RENAME TO boxes_old")
        cursor.execute("ALTER TABLE box_items RENAME TO box_items_old")
        
        # Создаём новые таблицы с AUTOINCREMENT
        cursor.execute("""
            CREATE TABLE shipments (
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
        
        cursor.execute("""
            CREATE TABLE shipment_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shipment_id INTEGER NOT NULL,
                barcode TEXT NOT NULL,
                sku TEXT NOT NULL,
                total_qty INTEGER NOT NULL,
                allocated_qty INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE boxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shipment_id INTEGER NOT NULL,
                box_id TEXT NOT NULL,
                is_current INTEGER DEFAULT 0,
                FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE box_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                box_id INTEGER NOT NULL,
                barcode TEXT NOT NULL,
                qty INTEGER NOT NULL,
                FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE CASCADE,
                UNIQUE(box_id, barcode)
            )
        """)
        
        # Восстанавливаем данные
        if shipments_data:
            cursor.executemany("INSERT INTO shipments VALUES (?,?,?,?,?,?,?,?,?,?,?)", shipments_data)
        if shipment_items_data:
            cursor.executemany("INSERT INTO shipment_items VALUES (?,?,?,?,?,?)", shipment_items_data)
        if boxes_data:
            cursor.executemany("INSERT INTO boxes VALUES (?,?,?,?)", boxes_data)
        if box_items_data:
            cursor.executemany("INSERT INTO box_items VALUES (?,?,?,?)", box_items_data)
        
        # Удаляем старые таблицы
        cursor.execute("DROP TABLE shipments_old")
        cursor.execute("DROP TABLE shipment_items_old")
        cursor.execute("DROP TABLE boxes_old")
        cursor.execute("DROP TABLE box_items_old")
        
        # Включаем внешние ключи обратно
        cursor.execute("PRAGMA foreign_keys = ON")
        
        conn.commit()
        logger.info("Миграция базы данных завершена успешно")
        
    except Exception as e:
        logger.error(f"Ошибка при миграции базы данных: {e}", exc_info=True)
        conn.rollback()


def _add_version_columns_to_tables(conn):
    """Добавляет колонки version и updated_at в основные таблицы для контроля версий"""
    try:
        db_type = get_db_type()
        use_sqlite = db_type == "sqlite"
        
        # Для PostgreSQL проверяем, не закрыто ли соединение, и получаем новое если нужно
        if not use_sqlite and conn.closed:
            logger.debug("Соединение закрыто, получаем новое для добавления колонок version")
            conn = get_connection()
        
        cursor = conn.cursor()

        logger.info("Добавление колонок version и updated_at в таблицы")

        # Список таблиц и колонок для добавления
        tables_to_migrate = [
            ('shipments', ['version INTEGER DEFAULT 0', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP']),
            ('shipment_items', ['version INTEGER DEFAULT 0', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP']),
            ('boxes', ['version INTEGER DEFAULT 0', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP']),
            ('box_items', ['version INTEGER DEFAULT 0', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP']),
        ]

        for table_name, columns in tables_to_migrate:
            # Проверяем существование таблицы
            if use_sqlite:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            else:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                """, (table_name,))

            if not cursor.fetchone():
                logger.debug(f"Таблица {table_name} не существует, пропускаем")
                continue

            # Проверяем и добавляем каждую колонку
            for column_def in columns:
                column_name = column_def.split()[0]  # Извлекаем имя колонки

                # Проверяем существование колонки
                if use_sqlite:
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    existing_columns = [col[1] for col in cursor.fetchall()]
                    column_exists = column_name in existing_columns
                else:
                    cursor.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = %s AND column_name = %s
                    """, (table_name, column_name))
                    result = cursor.fetchone()
                    column_exists = result is not None

                if not column_exists:
                    try:
                        # Для SQLite ALTER TABLE поддерживает только ADD COLUMN
                        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")
                        logger.info(f"Добавлена колонка {column_name} в таблицу {table_name}")
                    except Exception as col_error:
                        logger.debug(f"Колонка {column_name} уже существует в {table_name}: {col_error}")
                else:
                    logger.debug(f"Колонка {column_name} уже существует в {table_name}")

        conn.commit()
        logger.info("Колонки version и updated_at добавлены успешно")

    except Exception as e:
        logger.error(f"Ошибка при добавлении колонок version: {e}", exc_info=True)
        try:
            if not conn.closed:
                conn.rollback()
        except Exception:
            pass


def _create_missing_tables_for_sqlite(conn):
    """Создает отсутствующие таблицы для SQLite"""
    try:
        cursor = conn.cursor()

        # Получаем список существующих таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]

        # Проверяем, нужно ли пересоздать таблицы с AUTOINCREMENT
        need_recreate = False
        if 'boxes' in existing_tables:
            cursor.execute("PRAGMA table_info(boxes)")
            columns = cursor.fetchall()
            # Проверяем, есть ли колонка id и является ли она PRIMARY KEY с autoincrement
            for col in columns:
                if col[1] == 'id':
                    # col[5] содержит pk (1 если primary key), но не содержит info об autoincrement
                    # Проверяем через sql запрос
                    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='boxes'")
                    sql = cursor.fetchone()
                    if sql and sql[0] and 'AUTOINCREMENT' not in sql[0].upper():
                        need_recreate = True
                        logger.info("Таблица boxes требует пересоздания для AUTOINCREMENT")
                    break
        
        if 'box_items' in existing_tables and not need_recreate:
            cursor.execute("PRAGMA table_info(box_items)")
            columns = cursor.fetchall()
            for col in columns:
                if col[1] == 'id':
                    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='box_items'")
                    sql = cursor.fetchone()
                    if sql and sql[0] and 'AUTOINCREMENT' not in sql[0].upper():
                        need_recreate = True
                        logger.info("Таблица box_items требует пересоздания для AUTOINCREMENT")
                    break
                    
        if 'shipment_items' in existing_tables and not need_recreate:
            cursor.execute("PRAGMA table_info(shipment_items)")
            columns = cursor.fetchall()
            for col in columns:
                if col[1] == 'id':
                    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='shipment_items'")
                    sql = cursor.fetchone()
                    if sql and sql[0] and 'AUTOINCREMENT' not in sql[0].upper():
                        need_recreate = True
                        logger.info("Таблица shipment_items требует пересоздания для AUTOINCREMENT")
                    break
        
        # Если нужно пересоздать таблицы, создадим скрипт миграции
        if need_recreate:
            logger.warning("Обнаружены таблицы без AUTOINCREMENT. Требуется миграция базы данных.")
            # Создадим резервную копию данных перед пересозданием
            _migrate_database_to_autoincrement(conn)

        # Создаем таблицу stock_cache если не существует
        if 'stock_cache' not in existing_tables:
            cursor.execute("""
                CREATE TABLE stock_cache (
                    barcode TEXT PRIMARY KEY,
                    quantity INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.debug("Создана таблица stock_cache")

        # Создаем таблицу sku если не существует
        if 'sku' not in existing_tables:
            cursor.execute("""
                CREATE TABLE sku (
                    barcode TEXT PRIMARY KEY,
                    name TEXT,
                    article TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.debug("Создана таблица sku")

        # Создаем таблицу item_locks если не существует
        if 'item_locks' not in existing_tables:
            cursor.execute("""
                CREATE TABLE item_locks (
                    barcode TEXT NOT NULL,
                    shipment_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    PRIMARY KEY (barcode, shipment_id)
                )
            """)
            logger.debug("Создана таблица item_locks")

        # Создаем таблицу cache_invalidation если не существует
        if 'cache_invalidation' not in existing_tables:
            cursor.execute("""
                CREATE TABLE cache_invalidation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shipment_id INTEGER NOT NULL,
                    tables_changed TEXT NOT NULL,
                    invalidated_by TEXT,
                    invalidated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.debug("Создана таблица cache_invalidation")

        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц для SQLite: {e}")

_app_settings_cache = {}
_app_settings_cache_ttl = {}
_APP_SETTINGS_CACHE_SECONDS = 30

def get_app_setting(key, default=None):
    global _app_settings_cache, _app_settings_cache_ttl
    import time
    now = time.time()
    if key in _app_settings_cache and key in _app_settings_cache_ttl:
        if now - _app_settings_cache_ttl[key] < _APP_SETTINGS_CACHE_SECONDS:
            return _app_settings_cache[key]
    try:
        result = execute_query(
            "SELECT value FROM app_settings WHERE key = %s",
            (key,),
            fetchone=True
        )
        value = result[0] if result else default
        _app_settings_cache[key] = value
        _app_settings_cache_ttl[key] = now
        return value
    except Exception as e:
        logger.warning(f"Ошибка получения настройки {key}: {e}")
        return default

def set_app_setting(key, value):
    try:
        db_type = get_db_type()
        if db_type == "sqlite":
            execute_query(
                """
                INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)
                """,
                (key, value)
            )
        else:
            execute_query(
                """
                INSERT INTO app_settings (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value)
            )
    except Exception as e:
        logger.error(f"Ошибка сохранения настройки {key}: {e}", exc_info=True)

def get_window_state(key, default=None):
    try:
        result = execute_query(
            "SELECT value FROM window_state WHERE key = %s",
            (key,),
            fetchone=True
        )
        return result[0] if result else default
    except Exception as e:
        logger.warning(f"Ошибка получения состояния окна {key}: {e}")
        return default

def set_window_state(key, value):
    try:
        db_type = get_db_type()
        if db_type == "sqlite":
            execute_query(
                """
                INSERT OR REPLACE INTO window_state (key, value) VALUES (?, ?)
                """,
                (key, value)
            )
        else:
            execute_query(
                """
                INSERT INTO window_state (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value)
            )
    except Exception as e:
        logger.error(f"Ошибка сохранения состояния окна {key}: {e}", exc_info=True)


# === Глобальные настройки МойСклад (для всех пользователей) ===

def get_moysklad_token() -> str:
    """
    Получить глобальный токен МойСклад (общий для всех пользователей)
    
    Returns:
        str: Токен МойСклад или пустую строку если не настроен
    """
    return get_app_setting('moysklad_token', '') or ''


def set_moysklad_token(token: str) -> bool:
    """
    Сохранить глобальный токен МойСклад (общий для всех пользователей)
    
    Args:
        token: Токен МойСклад
        
    Returns:
        bool: True если успешно, False иначе
    """
    try:
        set_app_setting('moysklad_token', token)
        logger.info("Глобальный токен МойСклад сохранён")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения глобального токена МойСклад: {e}")
        return False


def get_moysklad_stores() -> str:
    """
    Получить глобальные настройки складов МойСклад (общие для всех пользователей)
    
    Returns:
        str: JSON строка со списком складов
    """
    return get_app_setting('moysklad_stores', '') or ''


def set_moysklad_stores(stores_json: str) -> bool:
    """
    Сохранить глобальные настройки складов МойСклад (общие для всех пользователей)
    
    Args:
        stores_json: JSON строка со списком складов
        
    Returns:
        bool: True если успешно, False иначе
    """
    try:
        set_app_setting('moysklad_stores', stores_json)
        logger.info("Глобальные настройки складов МойСклад сохранены")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения глобальных настроек складов МойСклад: {e}")
        return False


def get_moysklad_enabled() -> bool:
    """
    Получить глобальный флаг включения синхронизации с МойСклад

    Returns:
        bool: True если синхронизация включена (по умолчанию True)
    """
    value = get_app_setting('moysklad_enabled', 'True')
    return value in ('True', 'true', '1', 'yes')


def set_moysklad_enabled(enabled: bool) -> bool:
    """
    Установить глобальный флаг включения синхронизации с МойСклад

    Args:
        enabled: True для включения синхронизации

    Returns:
        bool: True если успешно, False иначе
    """
    try:
        set_app_setting('moysklad_enabled', 'True' if enabled else 'False')
        logger.info(f"Глобальный флаг синхронизации МойСклад установлен в {enabled}")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения глобального флага синхронизации МойСклад: {e}")
        return False


def get_user_settings(username):
    try:
        db_type = get_db_type()
        placeholder = "?" if db_type == "sqlite" else "%s"

        result = execute_query(
            f"""
            SELECT font_size, label_font_size, theme, ok_sound, error_sound, tone_sound, sound_volume,
                   shipment_columns_width, box_columns_width, main_splitter_sizes,
                   window_width, window_height, button_primary_color, button_success_color,
                   button_warning_color, button_danger_color,
                   moysklad_token, moysklad_stores, moysklad_enabled, shipment_locking_enabled,
                   article_column_visible, name_column_visible, total_qty_column_visible,
                   stock_column_visible, hide_completed_items, colored_buttons, button_colors
            FROM users WHERE username = {placeholder}
            """,
            (username,),
            fetchone=True
        )
        if result:
            # Вспомогательная функция для безопасного декодирования строк
            def decode_if_bytes(val, default=""):
                if val is None:
                    return default
                if isinstance(val, bytes):
                    return val.decode('utf-8')
                if isinstance(val, str):
                    return val
                return default

            # Вспомогательная функция для преобразования в boolean (универсальная для SQLite и PostgreSQL)
            def to_bool(val, default=False):
                if val is None:
                    return default
                if isinstance(val, bool):
                    return val  # PostgreSQL возвращает boolean
                if isinstance(val, int):
                    return val != 0  # SQLite возвращает 0/1
                return bool(val)

            settings_dict = {
                "font_size": result[0],
                "label_font_size": result[1],
                "theme": decode_if_bytes(result[2], "Светлая"),
                "ok_sound": decode_if_bytes(result[3], "ok.wav"),
                "error_sound": decode_if_bytes(result[4], "error.wav"),
                "tone_sound": to_bool(result[5], False),
                "sound_volume": result[6] if result[6] is not None else 100,
                "shipment_columns_width": decode_if_bytes(result[7], ""),
                "box_columns_width": decode_if_bytes(result[8], ""),
                "main_splitter_sizes": decode_if_bytes(result[9], ""),
                "window_width": result[10] or 1300,
                "window_height": result[11] or 800,
                "button_primary_color": decode_if_bytes(result[12], ""),
                "button_success_color": decode_if_bytes(result[13], ""),
                "button_warning_color": decode_if_bytes(result[14], ""),
                "button_danger_color": decode_if_bytes(result[15], ""),
                "moysklad_token": decode_if_bytes(result[16], ""),
                "moysklad_stores": decode_if_bytes(result[17], "[]"),
                "moysklad_enabled": to_bool(result[18], False),
                "shipment_locking_enabled": to_bool(result[19], False),
                "article_column_visible": to_bool(result[20], True),
                "name_column_visible": to_bool(result[21], False),
                "total_qty_column_visible": to_bool(result[22], True),
                "stock_column_visible": to_bool(result[23], True),
                "hide_completed_items": to_bool(result[24], False),
                "colored_buttons": to_bool(result[25], config.DEFAULT_COLORED_BUTTONS),
                "button_colors": decode_if_bytes(result[26], "{}")
            }
            logger.debug(f"get_user_settings({username}): moysklad_enabled={result[16]} (type={type(result[16])}), преобразовано в {settings_dict['moysklad_enabled']}")
            logger.debug(f"get_user_settings({username}): moysklad_enabled={settings_dict['moysklad_enabled']}, moysklad_token={'настроен' if settings_dict['moysklad_token'] else 'не настроен'}")
            return settings_dict
        logger.debug(f"get_user_settings({username}): настройки не найдены в БД")
        return None
    except Exception as e:
        logger.error(f"Ошибка получения настроек пользователя {username}: {e}", exc_info=True)
        return None

def set_user_settings(username, font_size, label_font_size, theme, ok_sound, error_sound,
                     shipment_columns_width="", box_columns_width="", main_splitter_sizes="",
                     window_width=1300, window_height=800, button_primary_color="",
                     button_success_color="", button_warning_color="", button_danger_color="",
                     moysklad_token="", moysklad_stores="", moysklad_enabled=False,
                     shipment_locking_enabled=False, article_column_visible=True,
                     name_column_visible=False, total_qty_column_visible=True,
                     stock_column_visible=True, hide_completed_items=False, cached_server_ip="",
                     colored_buttons=True, button_colors="", tone_sound=False, sound_volume=100):
    try:
        # Логирование для отладки сохранения настроек
        logger.info(f"set_user_settings: username={username}, stock_column_visible={stock_column_visible}, hide_completed_items={hide_completed_items}")
        # Логирование для отладки сохранения токена
        logger.debug(f"Сохранение настроек пользователя {username}: moysklad_token='{moysklad_token[:10] if moysklad_token else ''}...' (длина={len(moysklad_token) if moysklad_token else 0})")
        
        # Проверяем длину username и обрезаем если нужно (максимум 50 символов для PostgreSQL)
        if username and len(username) > 50:
            logger.warning(f"Имя пользователя '{username}' слишком длинное ({len(username)} символов), обрезается до 50")
            username = username[:50]

        # Проверяем и добавляем колонку button_colors если её нет
        try:
            db_type_check = get_db_type()
            if db_type_check == "sqlite":
                from db_connection import get_connection
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(users)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'button_colors' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN button_colors TEXT DEFAULT ''")
                    conn.commit()
                    logger.info("Колонка button_colors добавлена в таблицу users")
                from db_connection import _release_connection
                _release_connection(conn)
            else:
                # Для PostgreSQL проверяем наличие колонки через information_schema
                result = execute_query(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'button_colors'
                    """,
                    (),
                    fetchone=True
                )
                if not result:
                    execute_query("ALTER TABLE users ADD COLUMN button_colors TEXT DEFAULT ''")
                    logger.info("Колонка button_colors добавлена в таблицу users (PostgreSQL)")
        except Exception as e:
            logger.debug(f"Проверка/добавление колонки button_colors: {e}")
        
        # Ensure all string data is properly encoded
        encoded_username = username.encode('utf-8').decode('utf-8') if isinstance(username, str) else username
        encoded_theme = theme.encode('utf-8').decode('utf-8') if isinstance(theme, str) else theme
        encoded_ok_sound = ok_sound.encode('utf-8').decode('utf-8') if isinstance(ok_sound, str) else ok_sound
        encoded_error_sound = error_sound.encode('utf-8').decode('utf-8') if isinstance(error_sound, str) else error_sound
        encoded_shipment_columns_width = shipment_columns_width.encode('utf-8').decode('utf-8') if isinstance(shipment_columns_width, str) else shipment_columns_width
        encoded_box_columns_width = box_columns_width.encode('utf-8').decode('utf-8') if isinstance(box_columns_width, str) else box_columns_width
        encoded_main_splitter_sizes = main_splitter_sizes.encode('utf-8').decode('utf-8') if isinstance(main_splitter_sizes, str) else main_splitter_sizes
        encoded_button_primary_color = button_primary_color.encode('utf-8').decode('utf-8') if isinstance(button_primary_color, str) else button_primary_color
        encoded_button_success_color = button_success_color.encode('utf-8').decode('utf-8') if isinstance(button_success_color, str) else button_success_color
        encoded_button_warning_color = button_warning_color.encode('utf-8').decode('utf-8') if isinstance(button_warning_color, str) else button_warning_color
        encoded_button_danger_color = button_danger_color.encode('utf-8').decode('utf-8') if isinstance(button_danger_color, str) else button_danger_color
        encoded_moysklad_token = moysklad_token.encode('utf-8').decode('utf-8') if isinstance(moysklad_token, str) else moysklad_token
        encoded_moysklad_stores = moysklad_stores.encode('utf-8').decode('utf-8') if isinstance(moysklad_stores, str) else moysklad_stores
        encoded_button_colors = button_colors.encode('utf-8').decode('utf-8') if isinstance(button_colors, str) else button_colors

        db_type = get_db_type()

        if db_type == "sqlite":
            # SQLite использует INSERT OR REPLACE
            execute_query(
                """
                INSERT OR REPLACE INTO users
                (username, font_size, label_font_size, theme, ok_sound, error_sound, tone_sound, sound_volume,
                 shipment_columns_width, box_columns_width, main_splitter_sizes, window_width, window_height,
                 button_primary_color, button_success_color, button_warning_color, button_danger_color,
                 moysklad_token, moysklad_stores, moysklad_enabled, shipment_locking_enabled,
                 article_column_visible, name_column_visible, total_qty_column_visible, stock_column_visible, hide_completed_items,
                 cached_server_ip, colored_buttons, button_colors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (encoded_username, font_size, label_font_size, encoded_theme, encoded_ok_sound, encoded_error_sound,
                 1 if tone_sound else 0, sound_volume,
                 encoded_shipment_columns_width, encoded_box_columns_width, encoded_main_splitter_sizes, window_width, window_height,
                 encoded_button_primary_color, encoded_button_success_color, encoded_button_warning_color, encoded_button_danger_color,
                 encoded_moysklad_token, encoded_moysklad_stores, moysklad_enabled, shipment_locking_enabled,
                 article_column_visible, name_column_visible, total_qty_column_visible, stock_column_visible, hide_completed_items,
                 cached_server_ip, 1 if colored_buttons else 0, encoded_button_colors)
            )
        else:
            # PostgreSQL использует ON CONFLICT DO UPDATE
            # Преобразуем boolean в True/False для PostgreSQL
            tone_sound_bool = bool(tone_sound) if tone_sound is not None else False
            colored_buttons_bool = bool(colored_buttons) if colored_buttons is not None else False
            moysklad_enabled_bool = bool(moysklad_enabled) if moysklad_enabled is not None else False
            shipment_locking_enabled_bool = bool(shipment_locking_enabled) if shipment_locking_enabled is not None else False
            article_column_visible_bool = bool(article_column_visible) if article_column_visible is not None else True
            name_column_visible_bool = bool(name_column_visible) if name_column_visible is not None else False
            total_qty_column_visible_bool = bool(total_qty_column_visible) if total_qty_column_visible is not None else True
            stock_column_visible_bool = bool(stock_column_visible) if stock_column_visible is not None else True
            hide_completed_items_bool = bool(hide_completed_items) if hide_completed_items is not None else False

            execute_query(
                """
                INSERT INTO users
                (username, font_size, label_font_size, theme, ok_sound, error_sound, tone_sound, sound_volume,
                 shipment_columns_width, box_columns_width, main_splitter_sizes, window_width, window_height,
                 button_primary_color, button_success_color, button_warning_color, button_danger_color,
                 moysklad_token, moysklad_stores, moysklad_enabled, shipment_locking_enabled,
                 article_column_visible, name_column_visible, total_qty_column_visible, stock_column_visible, hide_completed_items,
                 cached_server_ip, colored_buttons, button_colors)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    font_size = EXCLUDED.font_size,
                    label_font_size = EXCLUDED.label_font_size,
                    theme = EXCLUDED.theme,
                    ok_sound = EXCLUDED.ok_sound,
                    error_sound = EXCLUDED.error_sound,
                    tone_sound = EXCLUDED.tone_sound,
                    sound_volume = EXCLUDED.sound_volume,
                    shipment_columns_width = EXCLUDED.shipment_columns_width,
                    box_columns_width = EXCLUDED.box_columns_width,
                    main_splitter_sizes = EXCLUDED.main_splitter_sizes,
                    window_width = EXCLUDED.window_width,
                    window_height = EXCLUDED.window_height,
                    button_primary_color = EXCLUDED.button_primary_color,
                    button_success_color = EXCLUDED.button_success_color,
                    button_warning_color = EXCLUDED.button_warning_color,
                    button_danger_color = EXCLUDED.button_danger_color,
                    moysklad_token = EXCLUDED.moysklad_token,
                    moysklad_stores = EXCLUDED.moysklad_stores,
                    moysklad_enabled = EXCLUDED.moysklad_enabled,
                    shipment_locking_enabled = EXCLUDED.shipment_locking_enabled,
                    article_column_visible = EXCLUDED.article_column_visible,
                    name_column_visible = EXCLUDED.name_column_visible,
                    total_qty_column_visible = EXCLUDED.total_qty_column_visible,
                    stock_column_visible = EXCLUDED.stock_column_visible,
                    hide_completed_items = EXCLUDED.hide_completed_items,
                    cached_server_ip = EXCLUDED.cached_server_ip,
                    colored_buttons = EXCLUDED.colored_buttons,
                    button_colors = EXCLUDED.button_colors
                """,
                (encoded_username, font_size, label_font_size, encoded_theme, encoded_ok_sound, encoded_error_sound,
                 tone_sound_bool, sound_volume,
                 encoded_shipment_columns_width, encoded_box_columns_width, encoded_main_splitter_sizes, window_width, window_height,
                 encoded_button_primary_color, encoded_button_success_color, encoded_button_warning_color, encoded_button_danger_color,
                 encoded_moysklad_token, encoded_moysklad_stores, moysklad_enabled_bool, shipment_locking_enabled_bool,
                 article_column_visible_bool, name_column_visible_bool, total_qty_column_visible_bool, stock_column_visible_bool, hide_completed_items_bool,
                 cached_server_ip, colored_buttons_bool, encoded_button_colors)
            )
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек пользователя {username}: {e}", exc_info=True)

def get_all_users():
    try:
        result = execute_query(
            "SELECT username FROM users ORDER BY username",
            fetchall=True
        )
        # Возвращаем список кортежей с именами пользователей
        return [(user[0],) for user in result] if result else []
    except Exception as e:
        logger.error(f"Ошибка получения списка пользователей: {e}", exc_info=True)
        return []

def delete_user(username):
    try:
        execute_query(
            "DELETE FROM users WHERE username = %s",
            (username,)
        )
        logger.info(f"Пользователь {username} удален")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя {username}: {e}", exc_info=True)
        return False

def get_shipment_properties(destination_name):
    """Получить свойства поставки"""
    try:
        result = execute_query(
            "SELECT properties FROM shipments WHERE destination_name = %s",
            (destination_name,),
            fetchone=True
        )
        if result and result[0]:
            return json.loads(result[0])
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON свойств поставки {destination_name}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Ошибка получения свойств поставки {destination_name}: {e}", exc_info=True)
        return {}

def save_shipment_properties(destination_name, properties):
    """Сохранить свойства поставки"""
    try:
        properties_json = json.dumps(properties, ensure_ascii=False)
        execute_query(
            "UPDATE shipments SET properties = %s WHERE destination_name = %s",
            (properties_json, destination_name)
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения свойств поставки {destination_name}: {e}", exc_info=True)
        return False

# Новые методы для работы с архивом
def get_archived_shipments():
    """Получить список архивированных поставок"""
    try:
        result = execute_query(
            """
            SELECT destination_name, archived_date, archived_by
            FROM shipments
            WHERE archived = %s
            ORDER BY archived_date DESC
            """,
            (True,),
            fetchall=True
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка получения архивированных поставок: {e}", exc_info=True)
        return []

def archive_shipment(shipment_name, username):
    """Архивировать поставку"""
    try:
        from datetime import datetime
        archived_date = datetime.now().isoformat()
        execute_query(
            "UPDATE shipments SET archived = %s, archived_date = %s, archived_by = %s WHERE destination_name = %s",
            (True, archived_date, username, shipment_name)
        )
        logger.info(f"Поставка {shipment_name} архивирована пользователем {username}")
        return True
    except Exception as e:
        logger.error(f"Ошибка архивации поставки {shipment_name}: {e}", exc_info=True)
        return False

def unarchive_shipment(shipment_name):
    """Восстановить поставку из архива"""
    try:
        # Сначала обновляем статус архивации
        execute_query(
            "UPDATE shipments SET archived = %s, archived_date = NULL, archived_by = NULL WHERE destination_name = %s",
            (False, shipment_name)
        )
        
        # После изменения статуса архивации, загружаем данные поставки для восстановления коробок
        shipment_data = execute_query(
            "SELECT id FROM shipments WHERE destination_name = %s",
            (shipment_name,),
            fetchone=True
        )
        
        if shipment_data:
            shipment_id = shipment_data[0]
            logger.info(f"Во��становлена поставка с ID {shipment_id}: {shipment_name}")
        else:
            logger.warning(f"Поставка не найдена в базе данных: {shipment_name}")
        
        logger.info(f"Поставка {shipment_name} восстановлена из архива")
        return True
    except Exception as e:
        logger.error(f"Ошибка восстановления поставки {shipment_name}: {e}", exc_info=True)
        return False

def delete_archived_shipment(shipment_name):
    """Удалить архивированную поставку"""
    try:
        db_type = get_db_type()
        placeholder = "?" if db_type == "sqlite" else "%s"
        
        conn = get_connection()
        cursor = conn.cursor()

        # Получаем ID поставки
        cursor.execute(
            f"SELECT id FROM shipments WHERE destination_name = {placeholder}",
            (shipment_name,)
        )
        result = cursor.fetchone()
        if not result:
            return False

        shipment_id = result[0]

        # Удаляем связанные записи
        cursor.execute(
            f"DELETE FROM box_items WHERE box_id IN (SELECT id FROM boxes WHERE shipment_id = {placeholder})",
            (shipment_id,)
        )
        cursor.execute(
            f"DELETE FROM boxes WHERE shipment_id = {placeholder}",
            (shipment_id,)
        )
        cursor.execute(
            f"DELETE FROM shipment_items WHERE shipment_id = {placeholder}",
            (shipment_id,)
        )
        cursor.execute(
            f"DELETE FROM shipments WHERE id = {placeholder}",
            (shipment_id,)
        )

        conn.commit()
        _release_connection(conn)
        logger.info(f"Архивированна�� поставка {shipment_name} удалена")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления ��рхивированной поставки {shipment_name}: {e}", exc_info=True)
        return False

# Добавляем индексы для улучшен��я производительности
def create_indexes():
    """��оздание индексов для улучшения производительности з��просов"""
    try:
        logger.info("Начало создания индексов")
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            # Индексы для PostgreSQL
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_shipments_archived ON shipments(archived)",
                "CREATE INDEX IF NOT EXISTS idx_shipments_destination ON shipments(destination_name)",
                "CREATE INDEX IF NOT EXISTS idx_shipment_items_shipment_id ON shipment_items(shipment_id)",
                "CREATE INDEX IF NOT EXISTS idx_boxes_shipment_id ON boxes(shipment_id)",
                "CREATE INDEX IF NOT EXISTS idx_box_items_box_id ON box_items(box_id)",
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
            ]
            
            for index_query in indexes:
                try:
                    cursor.execute(index_query)
                except Exception as e:
                    logger.warning(f"Ошибка при создании индекса: {e}")
            
            conn.commit()
            logger.info("Создание индексов завершено успешно")
        finally:
            _release_connection(conn)
    except Exception as e:
        logger.error(f"Ошибка при создании индексов: {e}", exc_info=True)
        # Не прерываем работу приложения из-за ошибки создания индексов
        pass

# Функция для очистки базы данных
def clear_database():
    """Удалить все данные из базы данных: поставки, архивированные поставки, пользователей и настройки"""
    try:
        logger.info("Начало очистки базы данных")
        conn = get_connection()
        try:
            cursor = conn.cursor()
            db_type = get_db_type()

            # Удаляем все данные из таблиц в правильном порядке (учитывая внешние ключи)
            if db_type == "sqlite":
                # Для SQLite просто удаляем данные из всех таблиц
                cursor.execute("DELETE FROM user_sessions")
                cursor.execute("DELETE FROM box_items")
                cursor.execute("DELETE FROM boxes")
                cursor.execute("DELETE FROM shipment_items")
                cursor.execute("DELETE FROM shipments")
                cursor.execute("DELETE FROM app_settings")
                cursor.execute("DELETE FROM window_state")
                cursor.execute("DELETE FROM users")
            else:
                # Для PostgreSQL проверяем существование таблицы user_sessions перед очисткой
                cursor.execute("""
                    SELECT EXISTS (
                      SELECT FROM information_schema.tables
                      WHERE table_schema = 'public'
                      AND table_name = 'user_sessions'
                    );
                """)
                user_sessions_exists = cursor.fetchone()[0]
                if user_sessions_exists:
                    cursor.execute("DELETE FROM user_sessions")

                cursor.execute("DELETE FROM box_items")
                cursor.execute("DELETE FROM boxes")
                cursor.execute("DELETE FROM shipment_items")
                cursor.execute("DELETE FROM shipments")
                cursor.execute("DELETE FROM app_settings")
                cursor.execute("DELETE FROM window_state")
                cursor.execute("DELETE FROM users")

            conn.commit()
            logger.info("База данных успешно очищена")
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при очистке базы данных: {e}", exc_info=True)
            return False
        finally:
            # Возвращаем соединение в пул
            _release_connection(conn)
    except Exception as e:
        logger.error(f"Ошибка при подключении для очистки базы данных: {e}", exc_info=True)
        return False


def update_user_session(shipment_name, username):
    """Обновить сессию пользователя для определенной поставки"""
    try:
        from datetime import datetime
        db_type = get_db_type()

        if db_type == "sqlite":
            # SQLite использует INSERT OR REPLACE
            execute_query(
                """
                INSERT OR REPLACE INTO user_sessions (shipment_name, username, last_activity)
                VALUES (?, ?, ?)
                """,
                (shipment_name, username, datetime.now())
            )
        else:
            # Проверяем существование таблицы user_sessions перед использованием
            # Используем execute_query для автоматического управления соединением
            table_exists_result = execute_query(
                """
                SELECT EXISTS (
                  SELECT FROM information_schema.tables
                  WHERE table_schema = 'public'
                  AND table_name = 'user_sessions'
                );
                """,
                fetchone=True
            )
            table_exists = table_exists_result[0] if table_exists_result else False

            if table_exists:
                # Сначала убеждаемся, что пользователь существует (для FK)
                user_exists = execute_query(
                    "SELECT EXISTS(SELECT 1 FROM users WHERE username = %s)",
                    (username,),
                    fetchone=True
                )[0]
                if not user_exists:
                    # Создаем пользователя по умолчанию, если не существует
                    execute_query(
                        """
                        INSERT INTO users (username, font_size, label_font_size, theme)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (username) DO NOTHING
                        """,
                        (username, 14, 14, 'light')
                    )
                    logger.info(f"Создан пользователь {username} по умолчанию")

                execute_query(
                    """
                    INSERT INTO user_sessions (shipment_name, username, last_activity)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (shipment_name, username)
                    DO UPDATE SET last_activity = %s
                    """,
                    (shipment_name, username, datetime.now(), datetime.now())
                )
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления сессии пользователя {username} для поставки {shipment_name}: {e}", exc_info=True)
        return False


def remove_user_session(shipment_name, username):
    """Удалить сессию пользователя для определенной поставки"""
    try:
        # Проверяем существование таблицы user_sessions перед использованием
        # Используем execute_query для автоматического управления соединением
        table_exists_result = execute_query(
            """
            SELECT EXISTS (
              SELECT FROM information_schema.tables
              WHERE table_schema = 'public'
              AND table_name = 'user_sessions'
            );
            """,
            fetchone=True
        )
        table_exists = table_exists_result[0] if table_exists_result else False

        if table_exists:
            execute_query(
                "DELETE FROM user_sessions WHERE shipment_name = %s AND username = %s",
                (shipment_name, username)
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления сессии пользователя {username} для поставки {shipment_name}: {e}", exc_info=True)
        return False


def get_active_users_for_shipment(shipment_name):
    """Получить список активных пользователей для определенной пост��вки"""
    try:
        from datetime import datetime, timedelta
        # Считаем активными пользователей, у которых последняя активность была в течение последних 5 минут
        five_minutes_ago = datetime.now() - timedelta(minutes=5)
        
        # Проверяем существование таблицы user_sessions перед использованием
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
              SELECT FROM information_schema.tables
              WHERE table_schema = 'public'
              AND table_name = 'user_sessions'
            );
        """)
        table_exists = cursor.fetchone()[0]
        cursor.close()
        _release_connection(conn)

        if table_exists:
            result = execute_query(
                """
                SELECT username, last_activity
                FROM user_sessions
                WHERE shipment_name = %s AND last_activity > %s
                ORDER BY last_activity DESC
                """,
                (shipment_name, five_minutes_ago),
                fetchall=True
            )
            return result if result else []
        else:
            return []
    except Exception as e:
        logger.error(f"Ошибка получения активных пользователей для поставки {shipment_name}: {e}", exc_info=True)
        return []


def cleanup_old_sessions():
    """Очистка старых ��ессий пользователей (старше 10 минут)"""
    try:
        from datetime import datetime, timedelta
        ten_minutes_ago = datetime.now() - timedelta(minutes=10)
        
        # Проверяем существование таблицы user_sessions перед использованием
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
              SELECT FROM information_schema.tables
              WHERE table_schema = 'public'
              AND table_name = 'user_sessions'
            );
        """)
        table_exists = cursor.fetchone()[0]
        cursor.close()
        _release_connection(conn)

        if table_exists:
            execute_query(
                "DELETE FROM user_sessions WHERE last_activity < %s",
                (ten_minutes_ago,)
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка очис��ки ста��ых сессий: {e}", exc_info=True)
        return False








def remove_avatar_column():
    """Уд��лить колонку avatar из таблицы пользователей, если она существует"""
    try:
        logger.info("Проверка и удаление колонки avatar из таблицы пользователей")
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            # Проверяем, существует ли колонка icon
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'icon'
            """)
            
            result = cursor.fetchone()
            
            if result:
                logger.info("Колонка 'icon' найдена в таблице 'users', выполняем удаление...")
                
                # Удаляем колонку icon
                cursor.execute("ALTER TABLE users DROP COLUMN icon;")
                
                conn.commit()
                logger.info("Колонка 'icon' успешно удалена из таблицы 'users'")
                return True
            else:
                logger.info("Колонка 'icon' не найдена в таблице 'users', удаление не требуется")
                return True
        finally:
            _release_connection(conn)
    except Exception as e:
        logger.error(f"Ошибка при удалении колонки avatar: {e}", exc_info=True)
        return False


# =============================================================================
# Функции для атомарного обновления и блокировок (защита от конфликтов)
# =============================================================================

def atomic_increment_allocated_qty(shipment_id, barcode, increment=1):
    """
    Атомарно увеличивает allocated_qty для товара в поставке.
    Использует UPDATE с условием для предотвращения гонки данных.
    
    Args:
        shipment_id: ID поставки
        barcode: штрихкод товара
        increment: на сколько увеличить (по умолчанию 1)
    
    Returns:
        tuple: (success, new_allocated_qty, message)
        - success: True если обновление успешно
        - new_allocated_qty: новое значение allocated_qty или None
        - message: сообщение об ошибке или успехе
    """
    try:
        db_type = get_db_type()
        use_sqlite = db_type == "sqlite"
        
        if use_sqlite:
            result = execute_query("""
                UPDATE shipment_items
                SET allocated_qty = allocated_qty + ?,
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE shipment_id = ? AND barcode = ? AND allocated_qty < total_qty
                RETURNING allocated_qty
            """, (increment, shipment_id, barcode), fetchone=True)
        else:
            result = execute_query("""
                UPDATE shipment_items
                SET allocated_qty = allocated_qty + %s,
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE shipment_id = %s AND barcode = %s AND allocated_qty < total_qty
                RETURNING allocated_qty
            """, (increment, shipment_id, barcode), fetchone=True)
        
        if result:
            # Успешно - логирование не нужно (вызывается при каждом сканировании)
            return (True, result[0], "Успешно")
        else:
            logger.warning(f"Не удалось увеличить allocated_qty для {barcode}: товар уже полностью распределён или не найден")
            return (False, None, "Товар уже полностью распределён или не найден")
            
    except Exception as e:
        logger.error(f"Ошибка атомарного увеличения allocated_qty: {e}", exc_info=True)
        return (False, None, str(e))


def atomic_decrement_allocated_qty(shipment_id, barcode, decrement=1):
    """
    Атомарно уменьшает allocated_qty для товара в поставке.
    
    Args:
        shipment_id: ID поставки
        barcode: штрихкод товара
        decrement: на сколько уменьшить (по умолчанию 1)
    
    Returns:
        tuple: (success, new_allocated_qty, message)
    """
    try:
        db_type = get_db_type()
        use_sqlite = db_type == "sqlite"
        
        if use_sqlite:
            result = execute_query("""
                UPDATE shipment_items
                SET allocated_qty = MAX(0, allocated_qty - ?),
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE shipment_id = ? AND barcode = ? AND allocated_qty > 0
                RETURNING allocated_qty
            """, (decrement, shipment_id, barcode), fetchone=True)
        else:
            result = execute_query("""
                UPDATE shipment_items
                SET allocated_qty = GREATEST(0, allocated_qty - %s),
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE shipment_id = %s AND barcode = %s AND allocated_qty > 0
                RETURNING allocated_qty
            """, (decrement, shipment_id, barcode), fetchone=True)
        
        if result:
            # Успешно - логирование не нужно (вызывается при каждом удалении)
            return (True, result[0], "Успешно")
        else:
            logger.warning(f"Не удалось уменьшить allocated_qty для {barcode}: allocated_qty уже 0 или товар не найден")
            return (False, None, "allocated_qty уже 0 или товар не найден")
            
    except Exception as e:
        logger.error(f"Ошибка атомарного уменьшения allocated_qty: {e}", exc_info=True)
        return (False, None, str(e))


def try_lock_item(barcode, shipment_id, username, lock_duration_sec=60):
    """
    Пытается захватить блокировку на товар для предотвращения конфликтов.
    
    Args:
        barcode: штрихкод товара
        shipment_id: ID поставки
        username: имя пользователя, захватывающего блокировку
        lock_duration_sec: время действия блокировки в секундах
    
    Returns:
        tuple: (success, lock_info, message)
        - success: True если блокировка захвачена
        - lock_info: dict с информацией о блокировке или None
        - message: сообщение об успехе или ошибке
    """
    try:
        from datetime import datetime, timedelta
        db_type = get_db_type()
        use_sqlite = db_type == "sqlite"
        
        now = datetime.now()
        expires = now + timedelta(seconds=lock_duration_sec)
        now_str = now.isoformat()
        expires_str = expires.isoformat()
        
        # Сначала удаляем просроченные блокировки
        if use_sqlite:
            execute_query("""
                DELETE FROM item_locks WHERE expires_at < ?
            """, (now_str,))
        else:
            execute_query("""
                DELETE FROM item_locks WHERE expires_at < %s
            """, (now_str,))
        
        # Пытаемся захватить блокировку
        if use_sqlite:
            # Для SQLite используем INSERT OR REPLACE
            execute_query("""
                INSERT OR REPLACE INTO item_locks (barcode, shipment_id, username, locked_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (barcode, shipment_id, username, now_str, expires_str))
            
            # Проверяем, удалось ли захватить (не заблокировано ли другим)
            lock_info = execute_query("""
                SELECT username, expires_at FROM item_locks
                WHERE barcode = ? AND shipment_id = ?
            """, (barcode, shipment_id), fetchone=True)
            
            if lock_info:
                # Проверяем, наша ли это блокировка или чужая
                if lock_info[0] == username:
                    return (True, {'username': lock_info[0], 'expires_at': lock_info[1]}, "Блокировка захвачена")
                else:
                    # Проверяем, не истекла ли чужая блокировка
                    try:
                        expires_at = datetime.fromisoformat(lock_info[1])
                        if datetime.now() > expires_at:
                            # Блокировка истекла, пытаемся захватить снова
                            execute_query("""
                                UPDATE item_locks SET username = ?, locked_at = ?, expires_at = ?
                                WHERE barcode = ? AND shipment_id = ?
                            """, (username, now_str, expires_str, barcode, shipment_id))
                            return (True, {'username': username, 'expires_at': expires_str}, "Блокировка захвачена (истекла)")
                    except Exception:
                        pass
                    return (False, {'username': lock_info[0], 'expires_at': lock_info[1]}, 
                            f"Товар заблокирован пользователем {lock_info[0]}")
            return (False, None, "Не удалось захватить блокировку")
        else:
            # Для PostgreSQL используем INSERT ... ON CONFLICT с условием
            result = execute_query("""
                INSERT INTO item_locks (barcode, shipment_id, username, locked_at, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (barcode, shipment_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    locked_at = EXCLUDED.locked_at,
                    expires_at = EXCLUDED.expires_at
                WHERE item_locks.expires_at < %s OR item_locks.username = %s
                RETURNING username, expires_at
            """, (barcode, shipment_id, username, now_str, expires_str, now_str, username), fetchone=True)
            
            if result:
                return (True, {'username': result[0], 'expires_at': result[1]}, "Блокировка захвачена")
            else:
                # Не удалось захватить - блокировка активна другим пользователем
                lock_info = execute_query("""
                    SELECT username, expires_at FROM item_locks
                    WHERE barcode = %s AND shipment_id = %s
                """, (barcode, shipment_id), fetchone=True)
                
                if lock_info:
                    return (False, {'username': lock_info[0], 'expires_at': str(lock_info[1])},
                            f"Товар заблокирован пользователем {lock_info[0]}")
                return (False, None, "Не удалось захватить блокировку")
                
    except Exception as e:
        logger.error(f"Ошибка захвата блокировки для {barcode}: {e}", exc_info=True)
        return (False, None, str(e))


def release_item_lock(barcode, shipment_id, username=None):
    """
    Освобождает блокировку товара.
    
    Args:
        barcode: штрихкод товара
        shipment_id: ID поставки
        username: имя пользователя (опционально, для проверки владельца)
    
    Returns:
        bool: True если блокировка успешно снята
    """
    try:
        db_type = get_db_type()
        use_sqlite = db_type == "sqlite"
        
        if username:
            if use_sqlite:
                execute_query("""
                    DELETE FROM item_locks WHERE barcode = ? AND shipment_id = ? AND username = ?
                """, (barcode, shipment_id, username))
            else:
                execute_query("""
                    DELETE FROM item_locks WHERE barcode = %s AND shipment_id = %s AND username = %s
                """, (barcode, shipment_id, username))
        else:
            if use_sqlite:
                execute_query("""
                    DELETE FROM item_locks WHERE barcode = ? AND shipment_id = ?
                """, (barcode, shipment_id))
            else:
                execute_query("""
                    DELETE FROM item_locks WHERE barcode = %s AND shipment_id = %s
                """, (barcode, shipment_id))
        
        logger.debug(f"Блокировка снята с {barcode} (shipment {shipment_id})")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка освобождения блокировки: {e}", exc_info=True)
        return False


def get_item_lock_info(barcode, shipment_id):
    """
    Получает информацию о блокировке товара.
    
    Args:
        barcode: штрихкод товара
        shipment_id: ID поставки
    
    Returns:
        dict или None: информация о блокировке или None
    """
    try:
        db_type = get_db_type()
        use_sqlite = db_type == "sqlite"
        
        if use_sqlite:
            result = execute_query("""
                SELECT username, locked_at, expires_at FROM item_locks
                WHERE barcode = ? AND shipment_id = ?
            """, (barcode, shipment_id), fetchone=True)
        else:
            result = execute_query("""
                SELECT username, locked_at, expires_at FROM item_locks
                WHERE barcode = %s AND shipment_id = %s
            """, (barcode, shipment_id), fetchone=True)
        
        if result:
            return {
                'username': result[0],
                'locked_at': result[1],
                'expires_at': result[2]
            }
        return None
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о блокировке: {e}", exc_info=True)
        return None


def get_active_locks_for_shipment(shipment_id, username=None):
    """
    Получает все активные блокировки для поставки.
    
    Args:
        shipment_id: ID поставки
        username: фильтр по пользователю (опционально)
    
    Returns:
        list: список блокировок
    """
    try:
        from datetime import datetime
        db_type = get_db_type()
        use_sqlite = db_type == "sqlite"
        now_str = datetime.now().isoformat()
        
        if username:
            if use_sqlite:
                result = execute_query("""
                    SELECT barcode, username, locked_at, expires_at FROM item_locks
                    WHERE shipment_id = ? AND username = ? AND expires_at > ?
                """, (shipment_id, username, now_str), fetchall=True)
            else:
                result = execute_query("""
                    SELECT barcode, username, locked_at, expires_at FROM item_locks
                    WHERE shipment_id = %s AND username = %s AND expires_at > %s
                """, (shipment_id, username, now_str), fetchall=True)
        else:
            if use_sqlite:
                result = execute_query("""
                    SELECT barcode, username, locked_at, expires_at FROM item_locks
                    WHERE shipment_id = ? AND expires_at > ?
                """, (shipment_id, now_str), fetchall=True)
            else:
                result = execute_query("""
                    SELECT barcode, username, locked_at, expires_at FROM item_locks
                    WHERE shipment_id = %s AND expires_at > %s
                """, (shipment_id, now_str), fetchall=True)
        
        locks = []
        for row in result:
            locks.append({
                'barcode': row[0],
                'username': row[1],
                'locked_at': row[2],
                'expires_at': row[3]
            })
        
        return locks
        
    except Exception as e:
        logger.error(f"Ошибка получения активных блокировок: {e}", exc_info=True)
        return []


def invalidate_cache_for_shipment(shipment_id, tables_changed, invalidated_by=None):
    """
    Создаёт запись об инвалидации кэша для поставки.
    Используется для синхронизации кэшей между клиентами.
    
    Args:
        shipment_id: ID поставки
        tables_changed: список изменённых таблиц
        invalidated_by: кто вызвал инвалидацию
    
    Returns:
        bool: True если успешно
    """
    try:
        import json
        db_type = get_db_type()
        use_sqlite = db_type == "sqlite"
        tables_json = json.dumps(tables_changed, ensure_ascii=False)
        
        if use_sqlite:
            execute_query("""
                INSERT INTO cache_invalidation (shipment_id, tables_changed, invalidated_by)
                VALUES (?, ?, ?)
            """, (shipment_id, tables_json, invalidated_by))
        else:
            execute_query("""
                INSERT INTO cache_invalidation (shipment_id, tables_changed, invalidated_by)
                VALUES (%s, %s, %s)
            """, (shipment_id, tables_json, invalidated_by))
        
        logger.debug(f"Создана запись об инвалидации кэша для shipment {shipment_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка инвалидации кэша: {e}", exc_info=True)
        return False


def get_pending_cache_invalidations(shipment_id, last_check_time=None):
    """
    Получаетpending записи об инвалидации кэша.
    
    Args:
        shipment_id: ID поставки
        last_check_time: время последней проверки (datetime)
    
    Returns:
        list: список записей об инвалидации
    """
    try:
        import json
        from datetime import datetime, timedelta
        db_type = get_db_type()
        use_sqlite = db_type == "sqlite"
        
        # По умолчанию проверяем за последние 5 минут
        if last_check_time is None:
            last_check_time = datetime.now() - timedelta(minutes=5)
        
        last_check_str = last_check_time.isoformat()
        
        if use_sqlite:
            result = execute_query("""
                SELECT id, tables_changed, invalidated_by, invalidated_at FROM cache_invalidation
                WHERE shipment_id = ? AND invalidated_at > ?
                ORDER BY invalidated_at DESC
            """, (shipment_id, last_check_str), fetchall=True)
        else:
            result = execute_query("""
                SELECT id, tables_changed, invalidated_by, invalidated_at FROM cache_invalidation
                WHERE shipment_id = %s AND invalidated_at > %s
                ORDER BY invalidated_at DESC
            """, (shipment_id, last_check_str), fetchall=True)
        
        invalidations = []
        for row in result:
            invalidations.append({
                'id': row[0],
                'tables_changed': json.loads(row[1]),
                'invalidated_by': row[2],
                'invalidated_at': row[3]
            })
        
        return invalidations
        
    except Exception as e:
        logger.error(f"Ошибка получения pending инвалидаций: {e}", exc_info=True)
        return []


def cleanup_expired_locks():
    """
    Удаляет просроченные блокировки из базы данных.
    Рекомендуется запускать периодически.
    
    Returns:
        int: количество удалённых записей
    """
    try:
        from datetime import datetime
        db_type = get_db_type()
        use_sqlite = db_type == "sqlite"
        now_str = datetime.now().isoformat()
        
        if use_sqlite:
            # Для SQLite нужно использовать другую форму
            execute_query("""
                DELETE FROM item_locks WHERE expires_at < ?
            """, (now_str,))
            # Получаем количество удалённых (SQLite не возвращает)
            return -1  # Неизвестно
        else:
            result = execute_query("""
                DELETE FROM item_locks WHERE expires_at < %s
                RETURNING COUNT(*)
            """, (now_str,), fetchone=True)
            return result[0] if result else 0
        
    except Exception as e:
        logger.error(f"Ошибка очистки просроченных блокировок: {e}", exc_info=True)
        return 0


# Вызываем создание индексов при инициализации
create_indexes()
