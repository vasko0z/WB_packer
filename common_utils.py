"""
Общие утилиты для приложения WB Packer
"""
import logging
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)


def validate_box_number(box_number: str, existing_numbers: List[str]) -> Tuple[bool, str]:
    """
    Проверить корректность номера коробки

    Args:
        box_number: Номер коробки для проверки
        existing_numbers: Список существующих номеров коробок

    Returns:
        Кортеж (успешно ли, сообщение об ошибке)
    """
    if not box_number:
        return False, "Номер коробки не может быть пустым!"

    if box_number in existing_numbers:
        return False, f"Коробка с номером «{box_number}» уже существует!"

    try:
        num = int(box_number)
        if num <= 0:
            return False, "Номер коробки должен быть положительным числом!"
    except ValueError:
        return False, "Номер коробки должен быть целым числом!"

    return True, ""


def format_box_id(box_number: int) -> str:
    """
    Форматировать ID коробки

    Args:
        box_number: Номер коробки

    Returns:
        Форматированный ID коробки
    """
    return f"Коробка-{box_number}"


def get_box_items_count(box_items: Dict[str, int]) -> int:
    """
    Получить общее количество товаров в коробке

    Args:
        box_items: Словарь товаров коробки

    Returns:
        Общее количество товаров
    """
    return sum(box_items.values())
