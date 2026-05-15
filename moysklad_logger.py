"""
Модуль для настройки специального логирования операций с МойСклад
"""
import logging
from pathlib import Path


def setup_moysklad_logger():
    """
    Настраивает специальный логгер для операций с МойСклад
    """
    # Создаем логгер для МойСклад
    logger = logging.getLogger('moysklad_sync')
    logger.setLevel(logging.DEBUG)
    
    # Убедимся, что у логгера нет дублирующих обработчиков
    if logger.handlers:
        logger.handlers.clear()
    
    # Создаем форматтер для специального лога МойСклад
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # Создаем консольный обработчик для МойСклад лога
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    
    # Добавляем обработчик к логгеру
    logger.addHandler(console_handler)
    
    # Предотвращаем дублирование в родительских логгерах
    logger.propagate = False
    
    logger.info("="*80)
    logger.info("ЛОГИРОВАНИЕ ОПЕРАЦИЙ С МОЙСКЛАД НАСТРОЕНО")
    logger.info("="*80)
    
    return logger


# Глобальный логгер МойСклад для использования в других модулях
moysklad_logger = setup_moysklad_logger()


def get_moysklad_logger():
    """
    Возвращает специальный логгер для МойСклад
    """
    return moysklad_logger