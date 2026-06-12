# WB Packer API

## Быстрый старт

```bash
# 1. Клонировать
git clone <repo> && cd wb_packer_api

# 2. Настроить окружение
cp .env.example .env
# Отредактировать .env: пароль БД, API ключи

# 3. Запустить
docker compose up -d
```

## Структура

```
wb_packer_api/
├── app/
│   ├── main.py              # FastAPI приложение
│   ├── config.py            # Настройки
│   ├── database.py          # Подключение к БД
│   ├── models.py            # Pydantic модели
│   ├── routers/             # Эндпоинты
│   │   ├── shipments.py     #   /api/shipments/*
│   │   ├── boxes.py         #   /api/boxes/*
│   │   ├── items.py         #   /api/shipments/{id}/items/*
│   │   ├── sku.py           #   /api/sku/*
│   │   ├── users.py         #   /api/users/*
│   │   ├── settings.py      #   /api/settings/*
│   │   ├── sessions.py      #   /api/sessions/*
│   │   ├── google_sheets.py #   /api/google-sheets/*
│   │   ├── moysklad.py      #   /api/moysklad/*
│   │   ├── stock.py         #   /api/stock/*
│   │   └── admin.py         #   /api/admin/*
│   └── services/            # Бизнес-логика
│       ├── shipment_service.py
│       ├── google_sheets_service.py
│       └── moysklad_service.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── .env.example
└── schema.sql
```

## Эндпоинты

### Поставки
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/shipments | Список поставок |
| GET | /api/shipments/{id} | Детали поставки |
| POST | /api/shipments | Создать поставку |
| PUT | /api/shipments/{id} | Обновить поставку |
| DELETE | /api/shipments/{id} | Удалить поставку (CASCADE) |
| POST | /api/shipments/{id}/archive | Архивировать |
| POST | /api/shipments/{id}/unarchive | Разархивировать |

### Товары поставок
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/shipments/{id}/items | Товары поставки |
| PUT | /api/shipments/{id}/items/{barcode} | Обновить товар |
| POST | /api/shipments/{id}/items | Добавить товары (bulk UPSERT) |
| DELETE | /api/shipments/{id}/items/{barcode} | Удалить товар |

### Коробки (таблица `box_items`)
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/shipments/{id}/boxes | Коробки поставки |
| POST | /api/shipments/{id}/boxes | Создать коробку |
| PUT | /api/shipments/{id}/boxes/{box_id} | Обновить коробку |
| DELETE | /api/shipments/{id}/boxes/{box_id} | Удалить коробку |
| GET | /api/boxes/{box_id}/items | Товары в коробке |
| POST | /api/shipments/{id}/boxes/{box_id}/items | Добавить товары (bulk, суммирует) |
| PUT | /api/shipments/{id}/boxes/{box_id}/items/{barcode} | Установить кол-во |
| DELETE | /api/shipments/{id}/boxes/{box_id}/items/{barcode} | Убрать товар |

### SKU
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/sku | Список SKU (barcodes query) |
| POST | /api/sku | Загрузить SKU (bulk) |
| DELETE | /api/sku | Очистить SKU |

### Пользователи
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/users | Все пользователи |
| GET | /api/users/{username} | Настройки пользователя |
| PUT | /api/users/{username} | Сохранить настройки |
| DELETE | /api/users/{username} | Удалить пользователя |

### Настройки
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/settings/{key} | Получить настройку |
| PUT | /api/settings/{key} | Сохранить настройку |

### Сессии
| Метод | Путь | Описание |
|-------|------|----------|
| PUT | /api/sessions | Обновить сессию |
| DELETE | /api/sessions/old | Очистить старые |

### Google Sheets
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/google-sheets/sheets | Список листов |
| POST | /api/google-sheets/import | Импорт поставки |
| POST | /api/google-sheets/update/{group_id} | Обновить групповую |

### МойСклад
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/moysklad/settings | Настройки |
| PUT | /api/moysklad/settings | Сохранить настройки |
| POST | /api/moysklad/sync | Синхронизировать |

### Остатки (таблица `stock_cache`)
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/stock/{barcode} | Остаток по штрихкоду |
| POST | /api/stock/batch | Остатки по списку |
| PUT | /api/stock/{barcode} | Установить остаток |

### Админ
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/admin/db-info | Информация о БД |
| GET | /api/admin/export | Экспорт всех данных |
| POST | /api/admin/import | Импорт данных |
| POST | /api/admin/clear | Очистить БД |

### Здоровье
| Метод | Путь | Описание |
|-------|------|----------|
| GET | /api/health | Проверка соединения |

## Аутентификация

Все запросы (кроме /api/health) требуют заголовок:
```
X-API-Key: ваш-ключ-из-.env
```

## Развёртывание

```bash
# Продакшн (Docker)
docker compose up -d

# Без Docker
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

nginx уже настроен в docker-compose — слушает порт 80, проксирует на API.
