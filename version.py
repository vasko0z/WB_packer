"""
Модуль управления версией приложения WB_packer
Версия читается из файла VERSION (единый источник версии)
Совместимость со старым API сохранена
"""
import json
from pathlib import Path
from datetime import datetime

# --- Единый источник версии: файл VERSION ---
def _read_version_file():
    """Читает semver из VERSION файла. Возвращает (major, minor, patch)."""
    import sys
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    version_file = base / "VERSION"
    try:
        text = version_file.read_text(encoding='utf-8').strip()
        parts = text.split('.')
        return int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        return 1, 0, 1

_VERSION = _read_version_file()
VERSION_MAJOR = _VERSION[0]
VERSION_MINOR = _VERSION[1]
VERSION_PATCH = _VERSION[2]

# BUILD — остаётся в коде для совместимости; обновляется через scripts/bump_version.py
VERSION_BUILD = 17  # Сборка: исправлено обновление групповой поставки из Google Sheets (удаление товаров, UPSERT без CASCADE)


def get_version_file_path():
    """Получить путь к файлу хранения версии (не используется, оставлено для совместимости)"""
    import sys
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent
    return base_path / "version_info.json"


def get_version_info():
    """
    Получить информацию о версии
    Возвращает dict с ключами: major, minor, patch, build, build_date
    """
    return {
        "major": VERSION_MAJOR,
        "minor": VERSION_MINOR,
        "patch": VERSION_PATCH,
        "build": VERSION_BUILD,
        "build_date": None
    }


def increment_build():
    """
    Увеличить номер сборки на 1
    Вызывается при каждой компиляции (автоматически обновляет VERSION_BUILD)
    """
    global VERSION_BUILD
    VERSION_BUILD += 1

    info = get_version_info()
    info["build_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Сохраняем в файл для истории (опционально)
    version_file = get_version_file_path()
    try:
        version_file.parent.mkdir(parents=True, exist_ok=True)
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return info


def get_version_string():
    """
    Получить строку версии в формате MAJOR.MINOR.PATCH.BUILD
    """
    return f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}.{VERSION_BUILD}"


def get_full_version_string():
    """
    Получить полную строку версии с датой сборки
    """
    version = get_version_string()
    info = get_version_info()
    if info.get('build_date'):
        version += f" (от {info['build_date']})"
    return version


if __name__ == "__main__":
    # Тестовый запуск
    print(f"Версия: {get_version_string()}")
