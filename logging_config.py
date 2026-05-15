"""
Модуль для настройки логирования в приложении WB Packer
"""
import logging
import os
import sys
from pathlib import Path

def setup_logging():
    """
    Настраивает систему логирования для приложения
    """
    # Создаем форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )

    # Создаем консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Показываем только INFO и выше
    console_handler.setFormatter(formatter)

    # Создаем файловый обработчик - пишем логи в папку с программой
    # Определяем папку с программой
    try:
        # Пытаемся получить путь к исполняемому файлу или скрипту
        if getattr(sys, 'frozen', False):
            # Если приложение скомпилировано в exe
            app_dir = Path(sys.executable).parent
        else:
            # Если запускается как скрипт
            app_dir = Path(__file__).parent
    except:
        # Если не удалось определить, используем текущую рабочую папку
        app_dir = Path.cwd()
    
    log_file = app_dir / "log.log"

    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')  # mode='w' для перезаписи
    file_handler.setLevel(logging.DEBUG)  # Пишем всё в файл
    file_handler.setFormatter(formatter)

    # Настраиваем корневой логер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Уровень DEBUG для полной отладки

    # Добавляем обработчики
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Убираем дублирование сообщений в консоль
    root_logger.propagate = False

    # Устанавливаем уровень логирования в зависимости от настроек
    log_level = os.getenv('WB_PACKER_LOG_LEVEL', 'DEBUG')
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))

    # Устанавливаем более низкий уровень для модулей МойСклад
    moysklad_log_level = os.getenv('MOYSKLAD_LOG_LEVEL', 'INFO')
    logging.getLogger('moysklad_api').setLevel(getattr(logging, moysklad_log_level.upper(), logging.INFO))

    # Подавляем warnings от psycopg_pool (cosmetic)
    logging.getLogger('psycopg.pool').setLevel(logging.ERROR)

    logging.info(f"Логирование настроено успешно. Лог-файл: {log_file}")
    return str(log_file)

def get_logger(name):
    """
    Возвращает логгер с указанным именем
    """
    return logging.getLogger(name)