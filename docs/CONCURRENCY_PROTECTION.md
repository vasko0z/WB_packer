# Защита от конфликтов при одновременной работе нескольких клиентов

## Обзор изменений

Реализована защита от конфликтов и потери прогресса при одновременной работе нескольких копий программы на разных компьютерах в локальной сети.

## Реализованные механизмы

### 1. Атомарное обновление `allocated_qty`

**Проблема**: При одновременном сканировании одного и того же товара двумя пользователями происходила потеря прогресса (оба читали `allocated_qty = 0`, оба записывали `allocated_qty = 1`, хотя должно быть 2).

**Решение**: Использование атомарного UPDATE запроса с условием:

```sql
UPDATE shipment_items
SET allocated_qty = allocated_qty + 1,
    version = version + 1,
    updated_at = CURRENT_TIMESTAMP
WHERE shipment_id = X AND barcode = Y AND allocated_qty < total_qty
RETURNING allocated_qty
```

**Файлы**:
- `database.py`: функции `atomic_increment_allocated_qty()`, `atomic_decrement_allocated_qty()`
- `shipment_manager.py`: обновлены методы `handle_scan()`, `add_all_remaining_to_box_by_barcode()`, `remove_item_from_box()`

### 2. Блокировка товаров (Item Locking)

**Проблема**: Отсутствие механизма предотвращения одновременного доступа к одному товару.

**Решение**: Реализована система блокировок на уровне базы данных:

- Таблица `item_locks` хранит активные блокировки
- Блокировка автоматически истекает через заданное время (по умолчанию 60 секунд)
- При сканировании проверяется, не заблокирован ли товар другим пользователем

**Новая таблица БД**:
```sql
CREATE TABLE item_locks (
    barcode TEXT NOT NULL,
    shipment_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    PRIMARY KEY (barcode, shipment_id)
)
```

**Файлы**:
- `database.py`: функции `try_lock_item()`, `release_item_lock()`, `get_item_lock_info()`, `get_active_locks_for_shipment()`, `cleanup_expired_locks()`
- `lock_manager.py`: класс `LockManager` для управления блокировками
- `shipment_manager.py`: проверка блокировки в `handle_scan()`

### 3. Версионирование данных

**Проблема**: Невозможность определить, какие данные новее при конфликте изменений.

**Решение**: Добавлены колонки `version` и `updated_at` в основные таблицы:
- `shipments`
- `shipment_items`
- `boxes`
- `box_items`

При каждом изменении записи `version` увеличивается на 1.

**Миграция**:
```sql
ALTER TABLE shipments ADD COLUMN version INTEGER DEFAULT 0;
ALTER TABLE shipments ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
-- и т.д. для других таблиц
```

**Файлы**:
- `database.py`: функция `_add_version_columns_to_tables()`
- `data_controller.py`: обновление version при сохранении в `save_shipment()`, `save_shipment_immediate()`

### 4. Синхронизация кэшей между клиентами

**Проблема**: Каждый клиент имеет свой локальный кэш, изменения не синхронизируются.

**Решение**: Таблица `cache_invalidation` для записи об изменениях данных:

```sql
CREATE TABLE cache_invalidation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER NOT NULL,
    tables_changed TEXT NOT NULL,
    invalidated_by TEXT,
    invalidated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

При изменении данных создаётся запись об инвалидации, другие клиенты могут проверить наличие изменений.

**Файлы**:
- `database.py`: функции `invalidate_cache_for_shipment()`, `get_pending_cache_invalidations()`
- `data_controller.py`: создание записей при сохранении
- `shipment_manager.py`: создание записей при сканировании

## Новые файлы

### `lock_manager.py`
Менеджер блокировок (Singleton):
- `try_lock()` - попытка захвата блокировки
- `release()` - освобождение блокировки
- `release_all_for_user()` - освобождение всех блокировок пользователя
- `is_locked_by_other()` - проверка, заблокирован ли товар другим
- `get_active_locks()` - получение активных блокировок
- `cleanup_expired()` - очистка просроченных блокировок
- `start_auto_cleanup()` - автоматическая периодическая очистка

## Изменённые файлы

### `database.py`
- Добавлено создание таблиц `item_locks` и `cache_invalidation`
- Добавлены индексы для новых таблиц
- Добавлена функция `_add_version_columns_to_tables()` для миграции
- Добавлены функции для атомарного обновления и блокировок
- Обновлена функция `_add_indexes_to_postgresql()`

### `shipment_manager.py`
- `handle_scan()`: проверка блокировки + атомарное обновление
- `add_all_remaining_to_box_by_barcode()`: атомарное обновление
- `remove_item_from_box()`: атомарное уменьшение
- Добавлены вспомогательные методы `_get_lock_manager()`, `_format_lock_time()`

### `data_controller.py`
- `save_shipment()`: обновление version + инвалидация кэша
- `save_shipment_immediate()`: обновление version + инвалидация кэша

## Миграция базы данных

Миграция выполняется **автоматически** при запуске приложения:

1. Создаются новые таблицы (`item_locks`, `cache_invalidation`)
2. Добавляются колонки `version` и `updated_at` в существующие таблицы
3. Создаются индексы для производительности

**Важно**: Перед обновлением рекомендуется сделать резервную копию базы данных!

## Сценарии использования

### Сценарий 1: Два пользователя сканируют один товар

1. Пользователь A сканирует товар `12345`
2. Система атомарно увеличивает `allocated_qty` в БД
3. Пользователь B сканирует товар `12345`
4. Система атомарно увеличивает `allocated_qty` в БД
5. **Результат**: `allocated_qty` увеличен на 2 (корректно)

### Сценарий 2: Блокировка товара

1. Пользователь A начинает сканирование товара `12345`
2. Товар блокируется на 60 секунд
3. Пользователь B пытается сканировать товар `12345`
4. Система показывает предупреждение: "Товар заблокирован пользователем A"
5. **Результат**: Конфликт предотвращён

### Сценарий 3: Синхронизация кэшей

1. Пользователь A изменяет данные поставки
2. Создаётся запись в `cache_invalidation`
3. Пользователь B проверяет наличие изменений
4. Система обновляет локальный кэш пользователя B
5. **Результат**: Данные синхронизированы

## Настройки

В `lock_manager.py` можно настроить:
- `default_lock_duration = 60` - время блокировки в секундах
- `auto_cleanup_interval = 300` - интервал очистки просроченных блокировок (5 минут)

## Тестирование

Проверка синтаксиса выполнена успешно:
```bash
python -m py_compile database.py shipment_manager.py data_controller.py lock_manager.py
```

## Рекомендации по развёртыванию

1. **Сделайте резервную копию базы данных**
2. Обновите файлы на всех клиентах
3. Перезапустите приложение на всех компьютерах
4. Проверьте логи на наличие ошибок миграции
5. Протестируйте одновременное сканирование с разных компьютеров

## Мониторинг

Для отслеживания блокировок используйте:
```python
from lock_manager import get_lock_manager

lock_mgr = get_lock_manager()
stats = lock_mgr.get_lock_statistics()
print(stats)  # {'local_locks_count': N, 'by_user': {...}}
```

## Устранение проблем

### Если блокировка не снимается
- Дождитесь истечения времени (60 секунд)
- Или перезапустите приложение (блокировки освобождаются)
- Или выполните вручную: `cleanup_expired_locks()`

### Если кэш не синхронизируется
- Проверьте наличие записей в `cache_invalidation`
- Убедитесь, что `get_pending_cache_invalidations()` вызывается периодически

## Будущие улучшения

- [ ] Добавить WebSocket для push-уведомлений об изменениях
- [ ] Реализовать долгосрочные блокировки для редактирования
- [ ] Добавить визуальное отображение активных пользователей
- [ ] Реализовать механизм разрешения конфликтов "последний выигрывает"
