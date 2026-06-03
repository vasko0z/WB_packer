"""
Функция для получения остатков из МойСклад (оптимизированная версия с кэшированием)
"""
import logging
import json

import database
from memory_manager import stock_cache

# Попытаемся импортировать API МойСклад
try:
    from moysklad_api import MoyskladAPI
    MOYSKLAD_API_AVAILABLE = True
except ImportError:
    MOYSKLAD_API_AVAILABLE = False
    MoyskladAPI = None

logger = logging.getLogger(__name__)


def get_stock_quantity_for_item(ui_updater_instance, barcode, current_user=None):
    """
    Получить остаток товара на складе из МойСклад (оптимизированная версия с кэшированием в базе данных)
    """
    # Используем метод get_stock_by_stores, который показал себя эффективным
    from moysklad_api import MoyskladAPI
    import database

    # Получаем настройки пользователя для проверки, включена ли интеграция
    user_settings = database.get_user_settings(current_user)
    if not user_settings or not user_settings.get('moysklad_enabled', True):
        return 0  # Если интеграция отключена, возвращаем 0

    if not user_settings or not user_settings.get('moysklad_token'):
        return 0  # Если токен не настроен, возвращаем 0

    # Сначала пробуем получить из кэша
    cached_qty = stock_cache.get_cached_quantity(barcode)
    if cached_qty is not None:
        return cached_qty

    # Если в кэше нет, запрашиваем из API
    try:
        # Создаем API
        api = MoyskladAPI(user_settings['moysklad_token'])

        # Получаем выбранные склады
        selected_stores = []
        try:
            stores_str = user_settings.get('moysklad_stores', '[]')
            selected_stores = json.loads(stores_str)
        except json.JSONDecodeError:
            selected_stores = []
        
        # Используем оптимизированную функцию получения остатков из нового модуля
        from optimized_get_stock_quantity import get_optimized_stock_quantity_for_item as optimized_func
        # Вызываем оптимизированную функцию для получения остатка для одного штрихкода
        quantity = optimized_func(ui_updater_instance, barcode)
        
        # Сохраняем в кэш
        stock_cache.set_cached_quantity(barcode, quantity)
        return quantity
    except Exception as e:
        logger.error(f"Ошибка получения остатков для штрихкода {barcode} через API: {e}")
        # В случае ошибки, возвращаем кэшированное значение или 0
        cached_qty = stock_cache.get_cached_quantity(barcode)
        if cached_qty is not None:
            return cached_qty
        else:
            stock_cache.set_cached_quantity(barcode, 0)
            return 0

def invalidate_stock_cache():
   """Функция для очистки кэша остатков (вызывается при необходимости обновления)"""
   stock_cache.invalidate_cache()

def get_multiple_stock_quantities(ui_updater_instance, barcodes, current_user=None):
   """
   Получить остатки для нескольких штрихкодов за один запрос
   """
   # Используем оптимизированную версию из нового модуля
   from optimized_get_stock_quantity import get_optimized_stock_quantities_force_update
   # Обновляем кэш при каждом вызове, чтобы получить актуальные данные
   # Получаем настройки пользователя для получения выбранных складов
   user_settings = database.get_user_settings(current_user)
   selected_stores = []
   if user_settings:
       try:
           stores_str = user_settings.get('moysklad_stores', '[]')
           selected_stores = json.loads(stores_str)
       except json.JSONDecodeError:
           selected_stores = []

   return get_optimized_stock_quantities_force_update(ui_updater_instance, barcodes, store_ids=selected_stores, current_user=current_user)

def get_multiple_stock_quantities_force_update(ui_updater_instance, barcodes, progress_callback=None, current_user=None):
   """
   Получить остатки для нескольких штрихкодов за один запрос с принудительным обновлением
   Гарантирует, что все запрашиваемые штрихкоды будут возвращены в результате
   """
   # Используем оптимизированную версию из нового модуля
   from optimized_get_stock_quantity import get_optimized_stock_quantities_force_update
   # Принудительно обновляем кэш, чтобы получить актуальные данные
   # Получаем настройки пользователя для получения выбранных складов
   user_settings = database.get_user_settings(current_user)
   selected_stores = []
   if user_settings:
       try:
           stores_str = user_settings.get('moysklad_stores', '[]')
           selected_stores = json.loads(stores_str)
       except json.JSONDecodeError:
           selected_stores = []

   # Вызываем оптимизированную функцию синхронизации
   result = get_optimized_stock_quantities_force_update(ui_updater_instance, barcodes, progress_callback=progress_callback, current_user=current_user)

   # После получения данных, обновляем кэш в базе данных
   if result:
       database.set_multiple_stock_cache(result)

   return result