# AGENTS.md - Правила проекта WB_packer

## О проекте
Приложение для управления заказами и печати этикеток Wildberries на PyQt6.

## ВАЖНО: Обновление документации
После КАЖДОЙ СУЩЕСТВЕННОЙ правки кода необходимо:
1. Обновить журнал изменений в Obsidian: `C:\Users\Admin\Nextcloud\Obsidian\CODE\WBPacker\WBPacker_журнал.md`
2. Добавить запись с датой, описанием изменений и именами изменённых файлов
3. Обновить VERSION_BUILD в version.py при значимых изменениях

## Компиляция в exe
- Использовать PyInstaller с файлом `WB_Packer.spec`
- Команда: `pyinstaller WB_Packer.spec --clean`
- После компиляции проверить включение всех библиотек, особенно reportlab
- Версия автоматически увеличивается при каждой сборке (VERSION_BUILD в version.py)

## Важные зависимости
- PyQt6, pandas, reportlab, openpyxl, psycopg2, Pillow, gspread, google-auth
- Все критичные модули должны быть в hiddenimports спец-файла

## Google Sheets интеграция
- SKU таблица: `1tQzh_qTnldbpeu9ryNF8ZKY4-amwT8UfuMqbSU1qOlA` (Штрихкод, Артикул, Наименование)
- Поставки: `1OGgsS0T4qaEekJgEkVTplZfoeQ7MeMth8o8eJTqnJGA`
- Service account ключ: `e-object-470910-p6-3500f3ddbdd3.json` (НЕ коммитить!)
- Штрихкоды нормализуются: убираются пробелы, дефисы, табуляции
- Массовая вставка SKU через `psycopg2.extras.execute_values` (быстро)

## Git и контроль версий
- Репозиторий: https://github.com/vasko0z/WB_packer
- Коммитить после каждой завершённой задачи или значимого изменения
- Сообщения коммитов: краткие, на русском, с указанием сути изменений
- Файлы БД (*.db), логи (*.log), настройки (settings.json, db_config.json), кэши и сборки НЕ коммитить (указаны в .gitignore)
- Периодически пушить изменения на GitHub: `git push`
- Перед началом работы: `git pull` для получения последних изменений

## Структура проекта
- main.py - точка входа
- spec файлы в корне для компиляции
- Модули в корневой директории