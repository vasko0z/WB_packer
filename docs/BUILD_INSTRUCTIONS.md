# Инструкция по компиляции WB_packer в EXE

## Быстрый старт

```bash
python -m PyInstaller --clean WB_packer.spec
```

После выполнения команды готовый файл будет в папке `dist\WB_packer.exe`

## Что делает spec-файл

1. **Собирает все подмодули** — автоматически собирает подмодули PyQt6, pandas, openpyxl, reportlab
2. **Собирает DLL файлы** — из PyQt6, pandas, numpy, psycopg2, SQLAlchemy, PIL, reportlab, psutil
3. **Собирает данные** — файлы ресурсов PyQt6, reportlab, папки Res, SKU, PDF, Поставки, config.ini, icon.ico
4. **Создаёт onefile EXE** — единый самораспаковывающийся исполняемый файл

## Режим компиляции

**Onefile** — единый исполняемый файл (~175 МБ), который при запуске распаковывается во временную папку.

Преимущества:
- Удобно распространять (один файл)
- Все ресурсы и DLL внутри

Недостатки:
- Медленнее первый запуск (распаковка)
- Большой размер файла

## Размер EXE файла

~175 МБ (зависит от количества включённых библиотек и версии PyQt6)

## Требования

- Python 3.13+
- PyInstaller 6.19+
- Все зависимости проекта:
  - PyQt6
  - pandas + numpy
  - openpyxl
  - reportlab
  - Pillow (PIL)
  - psycopg2-binary
  - SQLAlchemy
  - requests + urllib3
  - python-docx
  - psutil
  - cryptography

## Время компиляции

~4-5 минут на обычном ПК

## Проверка сборки

После компиляции:

1. Запустите `dist\WB_packer.exe`
2. Проверьте, что окно приложения открывается
3. Протестируйте основной функционал

## Возможные проблемы

### "No module named ..."

Добавьте модуль в `WB_packer.spec` в `hiddenimports`:

```python
hiddenimports=list(set([
    # ...
    'ваш_модуль',
]))
```

### EXE не запускается

1. Проверьте что все DLL включены — смотрите вывод PyInstaller на `WARNING: Library not found`
2. Попробуйте добавить DLL вручную в `binaries`:
   ```python
   binaries=[('путь/к.dll', '.')]
   ```

### Ресурсы не находятся

Проверьте, что пути в `get_resource_path()` используют `sys._MEIPASS` для onefile режима.

### Слишком маленький размер EXE

Проверьте, что `binaries` и `datas` заполнены в spec-файле. DLL PyQt6 должны быть включены.

---

**Последнее обновление:** 2026-04-06
**Версия инструкции:** 2.0
