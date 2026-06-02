# AGENTS.md - Правила проекта WB_packer

## Документация
- [README](docs/README.md) — описание проекта, функции, установка
- [BUILD_INSTRUCTIONS](docs/BUILD_INSTRUCTIONS.md) — компиляция в exe
- [PERFORMANCE_OPTIMIZATIONS](docs/PERFORMANCE_OPTIMIZATIONS.md) — оптимизации БД
- [CONCURRENCY_PROTECTION](docs/CONCURRENCY_PROTECTION.md) — многопоточность
- [Журнал изменений](%USERPROFILE%\Nextcloud\Obsidian\CODE\WBPacker\WBPacker_журнал.md)
- [Версии](%USERPROFILE%\Nextcloud\Obsidian\CODE\WBPacker\WBPacker Версии.md)

## Правила
- Вести рассуждения на русском языке
- После каждой важной правки обновить журнал изменений в Obsidian
- Обновить VERSION_BUILD в version.py при значимых изменениях
- НЕ коммитить: БД, логи, настройки, кэши, сборки, credentials

## Журнал изменений (Obsidian)

- Файл: `%USERPROFILE%\Nextcloud\Obsidian\CODE\WBPacker\WBPacker_журнал.md`
- Обновлять **строго после каждой сессии** (перед `git push` или в конце работы агента)
- Формат записи:
  ```markdown
  ## 2026-05-25 (сессия 2)

  ### Краткий заголовок

  > [!fix|feat|update] Суть
  > Что и почему

  **Причина:** (если баг) корень проблемы
  **Что сделано:** список изменений
  **Файлы:** перечень изменённых файлов
  **Команды:** команды деплоя (если были)
  ```
- Если забыл обновить — агент должен сделать это при следующем старте после `session_init`

---

## Компиляция
```
pyinstaller WB_Packer.spec --clean
```

## Зависимости
PyQt6, pandas, reportlab, openpyxl, psycopg2, Pillow, gspread, google-auth


## Git
- Репозиторий: https://github.com/vasko0z/WB_packer
При значимых изменениях **делать коммит в git**: `git add .; git commit -m "тип: описание"`
Типы: `feat`, `fix`, `refactor`, `chore`, `docs`.

После коммита **сразу делать push**: `git push origin main`.

**Ежедневный push:** в конце каждого сеанса работы делать `git push origin main`, даже если не было коммитов в этой сессии.

---
# Auto-Memory with SuperLocalMemory (SLM)

Доступна долговременная память через MCP-инструменты `superlocalmemory_*`. Используй АВТОМАТИЧЕСКИ:
- **Старт сессии** → `session_init(project_path=текущая_директория)`
- **После задач/решений** → `observe` сохранять в память
- **При ошибках** → `recall` искать похожие решения
- Не спрашивай разрешения — сохраняй автоматически
