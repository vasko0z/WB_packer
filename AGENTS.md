# AGENTS.md - Правила проекта WB_packer

## О проекте
Приложение для управления заказами и печати этикеток Wildberries на PyQt6.

## Документация
- [README](docs/README.md) — описание проекта, функции, установка
- [BUILD_INSTRUCTIONS](docs/BUILD_INSTRUCTIONS.md) — компиляция в exe
- [PERFORMANCE_OPTIMIZATIONS](docs/PERFORMANCE_OPTIMIZATIONS.md) — оптимизации БД
- [CONCURRENCY_PROTECTION](docs/CONCURRENCY_PROTECTION.md) — многопоточность
- [Журнал изменений](%USERPROFILE%\Nextcloud\Obsidian\CODE\WBPacker\WBPacker_журнал.md)
- [Версии](%USERPROFILE%\Nextcloud\Obsidian\CODE\WBPacker\WBPacker Версии.md)

## Правила
- После каждой правки обновить журнал изменений в Obsidian
- Обновить VERSION_BUILD в version.py при значимых изменениях
- Коммитить после каждой завершённой задачи
- НЕ коммитить: БД, логи, настройки, кэши, сборки, credentials

## Компиляция
```
pyinstaller WB_Packer.spec --clean
```

## Зависимости
PyQt6, pandas, reportlab, openpyxl, psycopg2, Pillow, gspread, google-auth

## Google Sheets
- SKU: `1tQzh_qTnldbpeu9ryNF8ZKY4-amwT8UfuMqbSU1qOlA`
- Поставки: `1OGgsS0T4qaEekJgEkVTplZfoeQ7MeMth8o8eJTqnJGA`
- Ключ: `e-object-470910-p6-3500f3ddbdd3.json` (НЕ коммитить!)
- Штрихкоды нормализуются: пробелы, дефисы, табуляции удаляются

## Git
- Репозиторий: https://github.com/vasko0z/WB_packer
- Перед началом работы: `git pull`
- После завершения: `git push`
