# Журнал сессий — WB Packer

## 2026-06-02 (сессия 3)

### Исправление: нулевая сумма после перезахода при загрузке групповой поставки из Google Sheets

> [!fix] КРИТИЧЕСКИЙ БАГ — Потеря shipment_items при закрытии программы

**Причина:** В `save_shipment_metadata_only()`, `save_shipment()`, `save_shipment_immediate()` (data_controller.py) и `_save_current_box_incremental()` (shipment_manager.py) для SQLite использовался `INSERT OR REPLACE INTO shipments`. В SQLite `INSERT OR REPLACE` работает как `DELETE` + `INSERT`: удаляет старую запись (включая `ON DELETE CASCADE` для `shipment_items`, `boxes`, `box_items`) и вставляет новую с новым `id`. При закрытии программы `save_all_shipments()` вызывает `save_shipment_metadata_only()` для всех поставок, что приводит к каскадному удалению всех `shipment_items` без их восстановления. После перезапуска `load_shipments()` загружает поставки, но `shipment_items` пустые — отсюда "0/0".

**Что сделано:**
1. Во всех 4 местах `INSERT OR REPLACE INTO shipments` заменён на `INSERT INTO shipments ... ON CONFLICT(destination_name) DO UPDATE SET ...` (UPSERT без CASCADE DELETE)
2. В `shipment_manager.save_shipment()` добавлено сохранение `shipment_id` в объект поставки после получения ID из БД

**Файлы:**
- `data_controller.py` — `save_shipment()`, `save_shipment_metadata_only()`, `save_shipment_immediate()`
- `shipment_manager.py` — `save_shipment()`, `_save_current_box_incremental()`

**Команды:** `pyinstaller WB_Packer.spec --clean`

---

## 2026-06-02 (сессия 2)

### Внедрение системы документации PROJECT_SYSTEM.md

> [!feat] Создана полноценная система документации, версионирования и git-хуков

**Что сделано:**
1. Создан `VERSION` файл (semver) — единый источник версии
2. Создан `SESSION_LOG.md` — журнал сессий в репозитории (перенесены записи из Obsidian)
3. Создан `CONTRIBUTING.md` — руководство для контрибьюторов
4. Создан `README.md` в корне — краткое описание + ссылки
5. Обновлён `docs/README.md` — оглавление документации
6. Создан `docs/_TEMPLATE.md` — шаблоны оформления
7. Создан `docs/_SUMMARY.md` — авто-индекс документации
8. Обновлён `AGENTS.md` — тонкий набор правил согласно PROJECT_SYSTEM
9. Обновлён `version.py` — теперь читает версию из `VERSION` файла
10. Создана папка `scripts/` с базовыми скриптами:
    - `bump_version.py` — обновление версии
    - `gen_summary.py` — генерация _SUMMARY.md
    - `check_secrets.py` — поиск секретов
    - `session_log.py` — черновик записи в SESSION_LOG.md
11. Создана папка `.githooks/` с pre-commit, pre-push, post-commit
12. Создан `Makefile` — удобные таргеты
13. Созданы конфиги: `.editorconfig`, `.gitattributes`, `.markdownlint.json`, `.ruff.toml`
14. Обновлён `.gitignore`

**Файлы:**
- `VERSION`, `README.md`, `SESSION_LOG.md`, `CONTRIBUTING.md`
- `AGENTS.md`, `version.py`, `.gitignore`
- `docs/README.md`, `docs/_TEMPLATE.md`, `docs/_SUMMARY.md`
- `scripts/bump_version.py`, `scripts/gen_summary.py`, `scripts/check_secrets.py`, `scripts/session_log.py`
- `.githooks/pre-commit`, `.githooks/pre-push`, `.githooks/post-commit`
- `Makefile`, `.editorconfig`, `.gitattributes`, `.markdownlint.json`, `.ruff.toml`

**Команды:** `git config core.hooksPath .githooks`

---

## 2026-06-02 (сессия)

### Исправление: пропадание направлений при загрузке групповой поставки из Google Sheets

> [!fix] Не все направления создавались при импорте из Google Sheets

**Причина:** `_create_group_shipment_from_df()` при определении числовых колонок брал первое «непустое» значение (`dropna().iloc[0]`). Пустая строка `""` не удаляется `dropna()`, поэтому `float("")` вызывал ValueError. Колонки с пустыми первыми значениями (например, "Екат", "Самара", "СПБ") игнорировались.

**Что сделано:**
1. `_create_group_shipment_from_df()` — проверка числовых данных теперь пропускает пустые строки и ищет ЛЮБОЕ числовое значение в колонке
2. `update_group_shipment_from_google_sheets_data()` — аналогичный фикс для определения `skip_cols`
3. `main_window.py:_import_shipment_from_sheet_worker()` — аналогичный фикс для авто-определения групповой поставки

**Файлы:**
- `shipment_operations.py` — `_create_group_shipment_from_df()`, `update_group_shipment_from_google_sheets_data()`
- `main_window.py` — `_import_shipment_from_sheet_worker()`
- `version.py` — VERSION_BUILD 11 → 12

**Команды:** `pyinstaller WB_Packer.spec --clean`

---

## 2026-05-28 (сессия)

### Исправление критических багов: потеря прогресса поставок, race condition таймеров, loss allocated_qty

> [!fix] Три критических бага, вызывающих потерю данных

**Причина:**
1. `update_group_shipment_from_google_sheets_data()` удаляла ВСЕ подпоставки и пересоздавала из Google Sheets. Если данные устарели или пусты — товары пропадали (прогресс "0/0")
2. `schedule_save()` и `schedule_full_save()` переиспользовали один QTimer с переподключением сигналов. При быстрой последовательности вызовов инкрементальное сохранение подменялось полным (DELETE-ALL → INSERT), что могло привести к потере данных
3. `add_all_remaining_for_all_items_to_box()` обновляла `allocated_qty` только в памяти, но не сохраняла в БД. `save_shipment_immediate()` использует UPSERT без `allocated_qty` в ON CONFLICT. При перезапуске allocated_qty сбрасывалось в 0

**Что сделано:**
1. `update_group_shipment_from_google_sheets_data()` — теперь не удаляет подпоставки, а обновляет состав существующих (UPSERT shipment_items). Новые подпоставки создаются только для колонок, которых ещё нет
2. Новый метод `_update_existing_shipment_items()` — обновляет `total_qty` и `allocated_qty` существующей подпоставки, сохраняя коробки и box_items
3. Таймеры: вместо переподключения сигналов — единый `_on_save_timer_timeout()` с флагами `save_pending` / `full_save_pending`. Полное сохранение всегда приоритетнее
4. `add_all_remaining_for_all_items_to_box()` — добавлено пакетное обновление `allocated_qty` в БД после цикла добавления товаров

**Файлы:**
- `shipment_operations.py` — `update_group_shipment_from_google_sheets_data()`, `_update_existing_shipment_items()`, `_update_shipment_items_preserving_boxes()`
- `shipment_manager.py` — `schedule_save()`, `schedule_full_save()`, `_on_save_timer_timeout()`, `add_all_remaining_for_all_items_to_box()`
- `main_window.py` — сброс `full_save_pending` при отмене таймеров
- `version.py` — VERSION_BUILD 10 → 11

**Команды:** `pyinstaller WB_Packer.spec --clean`

---

## 2026-05-22 (сессия)

### Исправление потери allocated_qty при перезапуске после загрузки состояния + обновления из Google Sheets

> [!fix] КРИТИЧЕСКИЙ БАГ — Потеря allocated_qty при перезапуске

**Причина:**
- `shipment.shipment_id` не устанавливался после `save_shipment()`. Из-за этого при сканировании срабатывала ветка `no_shipment_id` (только память, без записи в БД), а `_save_current_box_incremental` при отсутствии `shipment_id` вызывал `save_session()` (no-op). После перезапуска allocated_qty сбрасывалось.
- Новые товары в Google Sheets получали allocated_qty=0: В `_update_shipment_items_preserving_boxes()` новые товары вставлялись в БД с hardcoded `0` вместо `item.allocated_qty`, и UPDATE выполнялся до INSERT.
- Ручное добавление товара не вызывало полное сохранение: Использовался `schedule_save()` (только коробка) вместо `schedule_full_save()` (полное сохранение с shipment_items).

**Что сделано:**
- `data_controller.py`: `shipment.shipment_id = shipment_id` в `save_shipment()` и `save_shipment_immediate()`
- `main_window.py`: `schedule_full_save()` при ручном добавлении товара; `shipment.shipment_id` вместо повторного SELECT
- `shipment_manager.py`: UPDATE `allocated_qty` для товаров коробки в `_save_current_box_incremental()`
- `shipment_operations.py`: `item.allocated_qty` вместо `0` в INSERT; `allocated_qty = EXCLUDED.allocated_qty` в UPSERT

**Файлы:**
- `data_controller.py`, `shipment_manager.py`, `main_window.py`, `shipment_operations.py`

---

## 2026-05-21 (сессия)

### Исправление потери прогресса при обновлении из Google Sheets, сохранение/загрузка состояния коробок, оптимизация закрытия

> [!fix] Потеря прогресса при обновлении из Google Sheets

**Что сделано:**
- `shipment_operations.py`: Исправлено удаление всех подпоставок при обновлении из Google Sheets
- `main_window.py`: Добавлено сохранение/загрузка состояния коробок
- `data_controller.py`: Оптимизация закрытия приложения
- `shipment_manager.py`: Улучшено управление сессиями

**Файлы:**
- `shipment_operations.py`, `main_window.py`, `data_controller.py`, `shipment_manager.py`
