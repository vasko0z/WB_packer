# -*- coding: utf-8 -*-
"""
Модуль управления версией приложения WB_packer
Версия вшита в код и обновляется вручную при каждой компиляции
"""
import json
from pathlib import Path
from datetime import datetime

# Версия приложения - обновляется вручную при каждой компиляции!
VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_PATCH = 0
VERSION_BUILD = 65  # Увеличивать на 1 при каждой компиляции


def get_version_file_path():
    """Получить путь к файлу хранения версии (не используется, оставлено для совместимости)"""
    import sys
    
    if getattr(sys, 'frozen', False):
        # При работе из EXE - рядом с exe-файлом
        base_path = Path(sys.executable).parent
    else:
        # При разработке - в папке проекта
        base_path = Path(__file__).parent
    
    return base_path / "version_info.json"


def get_version_info():
    """
    Получить информацию о версии
    Возвращает dict с ключами: major, minor, patch, build, build_date
    """
    # Версия вшита в код
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
