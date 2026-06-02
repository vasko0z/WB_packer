# AGENTS.md — Правила для агента WB Packer

**Версия:** 1.0 | **Дата:** 2026-06-02

## Общие правила
- Язык рассуждений: русский
- Кодировка: UTF-8 (без BOM)
- Shell: PowerShell 5.1 (Windows), избегать `>` / `>>` для русского текста

## Деплой
- Компиляция: `pyinstaller WB_Packer.spec --clean`
- Зависимости: PyQt6, pandas, reportlab, openpyxl, psycopg2, Pillow, gspread, google-auth

## Git
- Репозиторий: https://github.com/vasko0z/WB_packer
- При значимых изменениях — коммит: `git add .; git commit -m "тип: описание"`
- Типы: `feat`, `fix`, `refactor`, `chore`, `docs`
- После коммита — сразу `git push origin main`
- **Ежедневный push:** в конце сеанса делать push, даже если не было коммитов
- **НЕ коммитить:** БД, логи, настройки, кэши, сборки, credentials

## Система документации
- Журнал сессий: `SESSION_LOG.md` (вместо Obsidian)
- Версия: `VERSION` файл (semver), синхронизируется через `scripts/bump_version.py`
- Подробнее: `docs/PROJECT_SYSTEM.md`

## Память
- Долговременная память через MCP `superlocalmemory_*`
- **Старт сессии** → `session_init(project_path=текущая_директория)`
- **После задач/решений** → `observe` сохранять автоматически
- **При ошибках** → `recall` искать похожие решения
- `SESSION_LOG.md` — авторитетный коммитируемый источник, дублировать в SLM не нужно
