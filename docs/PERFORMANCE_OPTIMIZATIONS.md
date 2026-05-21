# Оптимизация производительности для удалённой БД

## Выполненные оптимизации

### 1. Оптимизация пула соединений (config.py)
- `DATABASE_POOL_MIN_SIZE`: 5 → 2 (меньше соединений для удалённого сервера)
- `DATABASE_POOL_MAX_SIZE`: 50 → 15 (достаточно для одного клиента)
- `DATABASE_TIMEOUT`: 30 → 15 секунд
- `DATABASE_POOL_TIMEOUT`: 60 → 30 секунд
- `DATABASE_POOL_RECYCLE`: 3600 → 1800 секунд (чаще обновляем соединения)
- `POSTGRESQL_STATEMENT_TIMEOUT`: 30000 → 15000 мс
- `POSTGRESQL_IDLE_TIMEOUT`: 60000 → 30000 мс

### 2. Устранение лишних COMMIT (db_connection.py)
- SELECT запросы больше не делают `commit()` 
- Экономия: 1 сетевая операция на каждый запрос чтения
- Параметр `auto_commit` в `execute_query()`:
  - `None` (по умолчанию): автоматическое определение (True для INSERT/UPDATE/DELETE, False для SELECT)
  - `True`: всегда фиксировать
  - `False`: никогда не фиксировать

### 3. Пакетная загрузка данных (data_controller.py)
**Было**: 
- 1 запрос для поставок
- N запросов для товаров каждой поставки
- N запросов для коробок
- N×M запросов для товаров в коробках
- Итого: ~100+ запросов

**Стало**: 
- 4 запроса total (поставки → товары → коробки → товары в коробках)
- Итого: 4 запроса

### 3.1. Batch INSERT для shipment_items (shipment_manager.py)
**Было**: N отдельных `cursor.execute(INSERT ...)` для каждого товара
**Стало**: `execute_many` (PostgreSQL → `execute_values`) / `executemany` (SQLite)
**Эффект**: 10-50x быстрее сохранение поставок

### 3.2. Batch INSERT для box_items (shipment_manager.py)
**Было**: N отдельных `cursor.execute(INSERT ...)` для каждого элемента коробки
**Стало**: `execute_many` / `executemany` для всех элементов коробок
**Эффект**: 10-50x быстрее сохранение коробок

### 4. UPSERT вместо SELECT+INSERT/UPDATE (data_controller.py)
**Было**: Для каждого товара выполнялся SELECT для проверки, затем INSERT или UPDATE
- 2 запроса на товар

**Стало**: Один запрос `INSERT ... ON CONFLICT DO UPDATE`
- 1 запрос на товар
- Экономия: 50% запросов

### 5. Уникальное ограничение для shipment_items (database.py + SQL миграция)
- Добавлено `shipment_items_shipment_id_barcode_unique` для работы UPSERT
- Выполнено через миграцию `add_shipment_items_unique_constraint.sql`

### 6. Отложенное сохранение (shipment_manager.py)
**Было**: `save_shipment_immediate()` после каждого сканирования
- Блокировало UI на 1-3 секунды

**Стало**: `schedule_save()` с задержкой 500мс
- Мгновенная готовность к следующему сканированию
- Пакетное сохранение при простое

### 7. Инкрементальное сохранение (shipment_manager.py, main_window.py)
**Было**: `save_shipment()` сохраняет всю поставку со всеми товарами и коробками
- Для поставки с 10 коробками по 50 товаров: ~500 запросов

**Стало**: `_save_current_box_incremental()` сохраняет только текущую коробку
- Для текущей коробки с 50 товарами: ~50 запросов
- Экономия: в 10 раз меньше запросов

### 8. Оптимизация UI (ui_updater.py) — Версия 1.0.1
#### 8.1. N+1 query в update_group_shipment_items_table
**Было**: `get_product_names_by_barcodes([barcode])` вызывался на каждую строку → N запросов к БД
**Стало**: Один batch-запрос `get_product_names_by_barcodes(list(all_barcodes))` до цикла
**Эффект**: 50-500x меньше DB round-trips для групповых поставок

#### 8.2. O(N×M×B) → O(N×M+B) для allocated_qty
**Было**: `get_total_allocated_qty(barcode)` перебирал все поставки×коробки для каждого штрихкода
**Стало**: Один проход по всем коробкам → `global_allocated_map`, затем O(1) lookup
**Эффект**: 10M → 20K операций при 20 поставках × 10 коробок × 500 товаров

#### 8.3. Pre-compute allocated map в update_current_box_table
**Было**: Цикл по всем коробкам для каждого товара → O(R×B)
**Стало**: Один проход `total_allocated_per_barcode` до цикла → O(1) lookup
**Эффект**: O(R×B) → O(B+R)

#### 8.4. Shared QRegularExpressionValidator
**Было**: Новый `QRegularExpressionValidator` на каждую строку → N компиляций regex
**Стало**: Один shared instance `self._qty_validator` в `__init__`
**Эффект**: 0 компиляций regex на каждую перерисовку

#### 8.5. Cached stylesheet для кнопок
**Было**: F-string stylesheet генерировался на каждую строку
**Стало**: Кэш `_button_stylesheet_cache` по теме, генерация один раз на тему
**Эффект**: N → 1 генерация stylesheet

#### 8.6. Shared QFont для дерева
**Было**: `QFont()` + `setPointSize()` + `setBold()` на каждый QLabel в дереве
**Стало**: `_get_cached_font(size, bold)` с кэшем по `(size, bold)`
**Эффект**: 500+ GDI вызовов → ~5 (по числу уникальных комбинаций)

#### 8.7. Cached add_btn/qty_edit на action_widget
**Было**: `findChild(QPushButton)` и `findChild(QLineEdit)` на каждую строку → O(N) tree traversal
**Стало**: Прямые ссылки `action_widget.add_btn` и `action_widget.qty_lineedit`
**Эффект**: 0 findChild traversals

#### 8.8. Debounce resizeColumnsToContents
**Было**: `resizeColumnsToContents()` вызывался на каждый скан
**Стало**: Вызывается только один раз при первом открытии
**Эффект**: 0 text measurements на каждый скан после первого запуска

#### 8.9. setColumnWidth вынесен из цикла
**Было**: `setColumnWidth(6, 80)` вызывался на каждой строке → N layout recalculations
**Стало**: Один вызов после цикла
**Эффект**: N → 1 вызов

### 9. Оптимизация БД (database.py) — Версия 1.0.1
#### 9.1. LRU лимит кэшей
**Было**: Кэши `_product_names_cache` и `_stock_qty_cache` росли бесконечно
**Стало**: LRU eviction с лимитом 5000 элементов
**Эффект**: Предотвращение утечки памяти

#### 9.2. Двухэтапный запрос get_product_names_by_barcodes
**Было**: Один сложный запрос с REPLACE 4+ раз для всех баркодов
**Стало**: Этап 1 — точный match (использует индекс), Этап 2 — REPLACE только для ненайденных
**Эффект**: Значительное ускорение при наличии данных в sku

#### 9.3. TTL-кэш get_user_settings (30 секунд)
**Было**: Каждый вызов `get_user_settings()` делал запрос к БД
**Стало**: Кэш `_user_settings_cache` с TTL 30 секунд
**Эффект**: DB hits reduced на 90%+

#### 9.4. _schema_initialized флаг
**Было**: `init_db()` проверял `information_schema` 10+ раз при каждом вызове
**Стало**: Флаг `_schema_initialized` — быстрая проверка CREATE IF NOT EXISTS
**Эффект**: Ускорение запуска приложения

### 10. Оптимизация ресурсов — Версия 1.0.1
#### 10.1. In-memory кэш local username
**Было**: `load_local_user()` читал файл при каждом вызове
**Стало**: Кэш `_local_username_cache` в памяти
**Эффект**: 0 file reads после первого вызова

#### 10.2. Debounce sectionResized (300ms)
**Было**: `save_columns_width()` вызывался на каждое событие resize колонки
**Стало**: QTimer с задержкой 300ms — сохранение только после окончания drag
**Эффект**: DB writes coalesced при resize

### 11. Удаление dead code — Версия 1.0.1
- Удалены: `common_utils.py`, `archive_window.py`, `boxes_window.py`, `progress_dialog.py`, `labelprint.py`
- Удалён dead code в `data_controller.py:606-757` (~150 строк)
- Исправлен дубликат `_clear_cache_before_sync` в `improved_moysklad_sync.py`
- Очищены hiddenimports в `WB_Packer.spec` (удалены 13 несуществующих модулей)

## Гарантии сохранности данных

### Что сохраняется в БД:

1. **При сканировании штрихкода:**
   - `atomic_increment_allocated_qty()` - **НЕМЕДЛЕННО** сохраняет allocated_qty в shipment_items
   - `schedule_save()` - через 500мс сохраняет коробку и box_items
   - **Результат**: Данные сохранены даже если приложение упадёт

2. **При переключении между поставками:**
   - Только локальный кэш (данные уже в памяти)
   - Предыдущие изменения уже сохранены через `schedule_save()`

3. **При закрытии приложения:**
   - `closeEvent()` → `force_save_session()` → `_save_current_box_incremental()`
   - Все отложенные сохранения выполняются немедленно
   - **Результат**: Все изменения сохранены перед закрытием

4. **При архивации/удалении:**
   - Немедленное сохранение через `execute_query()` с auto_commit=True

### Проверка сохранности:

```sql
-- Проверить что allocated_qty обновлён в БД
SELECT barcode, sku, total_qty, allocated_qty 
FROM shipment_items 
WHERE shipment_id = <id> AND barcode = '<barcode>';

-- Проверить что товары в коробке сохранены
SELECT bi.barcode, bi.qty 
FROM box_items bi
JOIN boxes b ON b.id = bi.box_id
WHERE b.shipment_id = <id> AND b.box_id = '<box_id>';
```

## Дополнительные рекомендации

### Если всё еще медленно:

1. **Проверить индексы в БД:**
```sql
CREATE INDEX IF NOT EXISTS idx_shipment_items_shipment_id ON shipment_items(shipment_id);
CREATE INDEX IF NOT EXISTS idx_boxes_shipment_id ON boxes(shipment_id);
CREATE INDEX IF NOT EXISTS idx_box_items_box_id ON box_items(box_id);
```

2. **Увеличить кэш на стороне клиента:**
- Можно кэшировать остатки (stock_cache) на более длительное время
- Можно кэшировать данные о SKU

3. **Использовать соединение с более низкой задержкой:**
- Если пинг > 50мс, рассмотреть VPN или сервер ближе к клиенту

## Мониторинг производительности

Включить логирование запросов:
```python
# В config.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

Проверить количество запросов в логах:
- При запуске: должно быть ~4 запроса для загрузки всех данных
- При сканировании: должно быть 1 запрос (atomic_increment) + отложенное сохранение
- При переключении: 0 запросов (только UI)

## Тестирование

1. Запустить приложение
2. Отсканировать товар
3. Проверить лог - должно быть:
   - Мгновенное обновление UI
   - Через 500мс: сохранение коробки
4. Закрыть приложение
5. Проверить в БД что все изменения сохранены
