# План: Добавить API-режим в десктоп (как опцию)

## Цель
Десктопная программа продолжает работать с прямым подключением к БД, но получает **опциональную возможность** переключиться на работу через HTTP API.

---

## 1. Добавить `api_client.py` — HTTP-клиент к API-серверу

Новый файл в корне проекта. Все методы синхронные, используют `requests.Session()` с keep-alive.

```python
# api_client.py
import requests
import json
import logging
from typing import Optional, Any
from models import Shipment, Box, ShipmentItem

logger = logging.getLogger(__name__)


class APIClient:
    """HTTP client for WB Packer API"""

    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})
        self.session.headers.update({"Content-Type": "application/json"})

    def set_credentials(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session.headers.update({"X-API-Key": api_key})

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api{path}"

    def _get(self, path: str, params: dict = None) -> dict:
        resp = self.session.get(self._url(path), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict = None, files: dict = None) -> dict:
        resp = self.session.post(self._url(path), json=data, files=files, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, data: dict = None) -> dict:
        resp = self.session.put(self._url(path), json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> dict:
        resp = self.session.delete(self._url(path), timeout=30)
        resp.raise_for_status()
        return resp.json()

    # --- Shipments ---
    def get_shipments(self, archived=False, limit=500, offset=0) -> list:
        return self._get("/shipments", {"archived": str(archived).lower(), "limit": limit, "offset": offset}).get("shipments", [])

    def get_shipment(self, shipment_id: int) -> dict:
        return self._get(f"/shipments/{shipment_id}").get("shipment", {})

    def get_shipment_by_name(self, name: str) -> dict:
        return self._get(f"/shipments/by-name/{name}").get("shipment", {})

    def create_shipment(self, data: dict) -> dict:
        return self._post("/shipments", data)

    def update_shipment(self, shipment_id: int, data: dict) -> dict:
        return self._put(f"/shipments/{shipment_id}", data)

    def delete_shipment(self, shipment_id: int) -> dict:
        return self._delete(f"/shipments/{shipment_id}")

    def archive_shipment(self, shipment_id: int) -> dict:
        return self._post(f"/shipments/{shipment_id}/archive")

    def unarchive_shipment(self, shipment_id: int) -> dict:
        return self._post(f"/shipments/{shipment_id}/unarchive")

    # --- Items ---
    def get_items(self, shipment_id: int) -> list:
        return self._get(f"/shipments/{shipment_id}/items").get("items", [])

    def update_item(self, shipment_id: int, barcode: str, data: dict) -> dict:
        return self._put(f"/shipments/{shipment_id}/items/{barcode}", data)

    def bulk_create_items(self, shipment_id: int, items: list) -> dict:
        return self._post(f"/shipments/{shipment_id}/items", items)

    # --- Boxes ---
    def get_boxes(self, shipment_id: int) -> list:
        return self._get(f"/shipments/{shipment_id}/boxes").get("boxes", [])

    def create_box(self, shipment_id: int, box_id: str) -> dict:
        return self._post(f"/shipments/{shipment_id}/boxes", {"box_id": box_id, "is_current": False})

    def delete_box(self, shipment_id: int, box_id: str) -> dict:
        return self._delete(f"/shipments/{shipment_id}/boxes/{box_id}")

    def add_items_to_box(self, shipment_id: int, box_id: str, items: dict) -> dict:
        return self._post(f"/shipments/{shipment_id}/boxes/{box_id}/items", items)

    def update_item_in_box(self, shipment_id: int, box_id: str, barcode: str, qty: int) -> dict:
        return self._put(f"/shipments/{shipment_id}/boxes/{box_id}/items/{barcode}", {"qty": qty})

    def remove_item_from_box(self, shipment_id: int, box_id: str, barcode: str) -> dict:
        return self._delete(f"/shipments/{shipment_id}/boxes/{box_id}/items/{barcode}")

    # --- SKU ---
    def get_sku_batch(self, barcodes: list) -> list:
        return self._get("/sku", {"barcodes": ",".join(barcodes)}).get("sku", [])

    def bulk_upsert_sku(self, skus: list) -> dict:
        return self._post("/sku", skus)

    def clear_sku(self) -> dict:
        return self._delete("/sku")

    # --- Users ---
    def get_users(self) -> list:
        return self._get("/users").get("users", [])

    def get_user_settings(self, username: str) -> dict:
        return self._get(f"/users/{username}").get("user", {})

    def save_user_settings(self, username: str, data: dict) -> dict:
        return self._put(f"/users/{username}", data)

    def delete_user(self, username: str) -> dict:
        return self._delete(f"/users/{username}")

    # --- App Settings ---
    def get_setting(self, key: str) -> str:
        return self._get(f"/settings/{key}").get("value", "")

    def save_setting(self, key: str, value: str) -> dict:
        return self._put(f"/settings/{key}", {"key": key, "value": value})

    # --- Window State ---
    def get_window_state(self, key: str) -> dict:
        return self._get(f"/window-state/{key}")

    def save_window_state(self, key: str, value: dict) -> dict:
        return self._put(f"/window-state/{key}", {"key": key, "value": json.dumps(value, ensure_ascii=False)})

    # --- Sessions ---
    def update_session(self, shipment_name: str, username: str) -> dict:
        return self._put("/sessions", {"shipment_name": shipment_name, "username": username})

    def cleanup_sessions(self) -> dict:
        return self._delete("/sessions/old")

    # --- Google Sheets ---
    def get_gsheets_list(self, spreadsheet_id: str = "") -> list:
        return self._get("/google-sheets/sheets", {"spreadsheet_id": spreadsheet_id}).get("sheets", [])

    def import_from_gsheets(self, data: dict) -> dict:
        return self._post("/google-sheets/import", data)

    def update_group_from_gsheets(self, group_id: int, data: dict) -> dict:
        return self._post(f"/google-sheets/update/{group_id}", data)

    # --- Moysklad ---
    def get_moysklad_settings(self) -> dict:
        return self._get("/moysklad/settings")

    def sync_moysklad(self, shipment_id: int = None) -> dict:
        return self._post("/moysklad/sync", {"shipment_id": shipment_id})

    # --- Stock ---
    def get_stock(self, barcode: str) -> int:
        return self._get(f"/stock/{barcode}").get("stock", 0)

    def get_stock_batch(self, barcodes: list) -> dict:
        return self._post("/stock/batch", {"barcodes": barcodes}).get("stocks", {})

    # --- Admin ---
    def get_db_info(self) -> dict:
        return self._get("/admin/db-info")

    def export_data(self) -> dict:
        return self._get("/admin/export")

    def import_data(self, data: dict) -> dict:
        return self._post("/admin/import", data)

    def clear_database(self) -> dict:
        return self._post("/admin/clear")

    def health_check(self) -> bool:
        try:
            resp = self.session.get(f"{self.base_url}/api/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
```

**Где разместить:** `C:\Users\voodo\Nextcloud\code\WB_packer_vscode\api_client.py`

---

## 2. Флаг `USE_API` в `config.py`

Добавить в `config.py` простой переключатель:

```python
# config.py — добавить в конец

# Режим работы: "direct" (БД напрямую) или "api" (через HTTP)
USE_API = os.environ.get("WB_PACKER_USE_API", "false").lower() == "true"
API_URL = os.environ.get("WB_PACKER_API_URL", "http://localhost:8000")
API_KEY = os.environ.get("WB_PACKER_API_KEY", "dev-key-change-me")
```

---

## 3. Фабрика `db_or_api` — единая точка доступа

Создать файл `db_or_api.py`, который в зависимости от `config.USE_API` возвращает либо функции из `database.py`, либо вызовы `api_client.py`.

```python
# db_or_api.py — единый интерфейс для БД/API
from typing import Any
import config

if config.USE_API:
    from api_client import APIClient
    _client = APIClient(config.API_URL, config.API_KEY)
else:
    import database as _db

def get_shipments(archived=False, limit=100, offset=0) -> list:
    if config.USE_API:
        return _client.get_shipments(archived, limit, offset)
    else:
        return _db.get_shipments(archived, limit, offset)

def get_shipment(shipment_id: int) -> dict:
    if config.USE_API:
        return _client.get_shipment(shipment_id)
    else:
        return _db.get_shipment(shipment_id)

# ... и так для каждой функции (~40 функций)
```

**Важно:** функции `_db.xxx()` должны возвращать данные **в том же формате**, что и API.

---

## 4. Что менять в существующих файлах

| Файл | Что менять |
|------|-----------|
| `config.py` | Добавить `USE_API`, `API_URL`, `API_KEY` |
| `main_window.py` | `import database` → `import db_or_api as db`; после `__init__` проверить `config.USE_API` и показать статус в статус-баре |
| `data_controller.py` | Весь `database.xxx()` → `db_or_api.xxx()` |
| `shipment_manager.py` | `database.xxx()` → `db_or_api.xxx()` |
| `shipment_operations.py` | `database.xxx()` → `db_or_api.xxx()` |
| `dialogs.py` | `database.xxx()` в ArchiveDialog, SettingsDialog → `db_or_api.xxx()` |
| `async_operations.py` | `database.xxx()` → `db_or_api.xxx()` |
| `db_settings_dialog.py` | Добавить вкладку "Подключение к серверу" поверх существующих настроек БД |
| `improved_moysklad_sync.py` | `database.get_moysklad_*()` → `db_or_api.xxx()` |
| `optimized_get_stock_quantity.py` | `database.get_user_settings()` → `db_or_api.get_user_settings()` |
| `get_stock_quantity_for_item.py` | Аналогично |
| `check_stock_dialog.py` | Аналогично |

**Ключевой принцип:** ни один файл не должен делать `import database` напрямую. Все через `db_or_api`.

---

## 5. Формат данных: ключевое требование

Функции в `database.py` возвращают кортежи/списки кортежей. Функции в `api_client.py` возвращают словари.

`db_or_api.py` должен **нормализовать** формат, чтобы принимающий код не замечал разницы.

### Вариант А (рекомендуемый): обернуть сырые данные в объекты моделей

```python
# db_or_api.py
from models import Shipment, ShipmentItem, Box

def get_shipments(...) -> list[Shipment]:
    if config.USE_API:
        data = _client.get_shipments(...)
        return [Shipment.from_dict(s) for s in data]
    else:
        rows = _db.get_shipments(...)
        return [Shipment.from_db_row(r) for r in rows]
```

Для этого нужно добавить методы `from_dict()` и `from_db_row()` в классы `models.py`.

### Вариант Б (проще): возвращать словари

Переписать все потребители данных (в `shipment_manager.py`, `data_controller.py`) так, чтобы они работали со словарями вместо кортежей. Это проще, но более грязно.

---

## 6. `db_settings_dialog.py` — добавить вкладку API

Диалог настроек БД (`DatabaseSettingsDialog`) получает новую вкладку:
- Поле "URL сервера" (input)
- Поле "API Key" (input)  
- Кнопка "Проверить соединение" → `api_client.health_check()`
- Кнопка "Использовать API" → установить `config.USE_API = True`
- Сохранять настройки в `config.API_URL` и `config.API_KEY` (в `config.ini` или `db_settings.json`)

Вкладка с прямыми настройками БД остаётся для fallback.

---

## 7. Статус-бар в `main_window.py`

Показывать текущий режим:

```python
if config.USE_API:
    self.statusBar().showMessage(f"Режим: API → {config.API_URL}")
else:
    self.statusBar().showMessage("Режим: прямая БД")
```

---

## 8. Порядок реализации (по файлам)

| Шаг | Файл | Что делать | Время |
|-----|------|-----------|-------|
| 1 | `api_client.py` | Написать полностью | 2-3 часа |
| 2 | `config.py` | Добавить 3 переменные | 5 мин |
| 3 | `models.py` | Добавить `from_dict()`, `from_db_row()` | 1 час |
| 4 | `db_or_api.py` | Написать фабрику-адаптер | 2 часа |
| 5 | `data_controller.py` | Заменить `database` → `db_or_api` | 1 час |
| 6 | `shipment_manager.py` | Заменить `database` → `db_or_api` | 2 часа |
| 7 | `shipment_operations.py` | Заменить `database` → `db_or_api` | 1 час |
| 8 | `dialogs.py` | Заменить `database` → `db_or_api` | 1 час |
| 9 | `async_operations.py` | Заменить `database` → `db_or_api` | 30 мин |
| 10 | `db_settings_dialog.py` | Добавить вкладку API | 2 часа |
| 11 | `main_window.py` | Статус-бар, инициализация | 30 мин |
| 12 | Прочие (`moysklad_*.py`, `stock*.py`) | Заменить `database` → `db_or_api` | 1 час |
| **Итого** | | | **~14 часов** |

---

## 9. Процесс миграции на API для пользователя

1. Развернуть API на VPS (по инструкции `VPS_START.md`)
2. В десктопе: `Настройки → Подключение к серверу`
3. Ввести URL + API Key
4. Нажать "Проверить"
5. Нажать "Использовать API"
6. Перезапустить программу

Программа продолжает работать, но все запросы к данным идут через API, а не напрямую в БД.

Для отката: снять галочку "Использовать API" → перезапустить.

---

## 10. Критические моменты

### Безопасность
- `api_client.py` передаёт API-ключ в каждом запросе (HTTPS обязателен)
- На VPS настроить firewall, nginx только с HTTPS (Let's Encrypt)

### Производительность
- `requests.Session()` с keep-alive — одно TCP-соединение на всю сессию
- Если API на том же локальном хосте — задержка <1ms
- Если API на VPS — задержка 10-50ms (терпимо для сканирования)

### Автономность
- При `USE_API = True` и потере связи с сервером — программа падает с ошибкой
- Можно добавить: локальный кэш + очередь операций (но это уже Фаза 2)
