# VPS: Быстрый старт

```bash
# 1. Зайти на VPS
ssh user@your-vps-ip

# 2. Установить Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Выйти и зайти снова

# 3. Клонировать проект
git clone https://github.com/vasko0z/WB_packer.git
cd WB_packer/wb_packer_api

# 4. Настроить
cp .env.example .env
nano .env
#   POSTGRES_PASSWORD=my-strong-password
#   API_KEYS=my-secret-api-key
#   GSHEETS_CREDENTIALS={"type":"service_account",...}
#   MOYSKLAD_TOKEN=...

# 5. Запустить
docker compose up -d

# 6. Проверить
curl http://localhost/api/health
# → {"status":"healthy"}

# 7. Настроить десктоп
#    В программе: Настройки → Подключение к серверу
#    URL: http://your-vps-ip
#    API Key: my-secret-api-key
```

## Бэкап БД

```bash
# Ручной
docker compose exec postgres pg_dump -U wb_packer wb_packer > backup.sql

# Автоматический (cron)
0 3 * * * docker compose -f /path/to/docker-compose.yml exec -T postgres pg_dump -U wb_packer wb_packer > /backups/wb_packer_$(date +\%Y\%m\%d).sql
```

## Логи

```bash
docker compose logs -f api      # API логи
docker compose logs -f postgres # БД логи
```

## Обновление

```bash
git pull
docker compose up -d --build
```

## Тестирование API

```bash
# Health
curl http://localhost/api/health

# Список поставок
curl -H "X-API-Key: my-secret-api-key" http://localhost/api/shipments

# Создать поставку
curl -X POST -H "X-API-Key: my-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"destination_name":"Тестовая поставка"}' \
  http://localhost/api/shipments
```
