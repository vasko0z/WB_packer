"""
Оптимизированный модуль для получения остатков из МойСклад
Содержит улучшенные функции с оптимальным кэшированием и батчингом запросов
"""
import logging
import json
from typing import Dict, List

import database
from memory_manager import stock_cache
from moysklad_api import MoyskladAPI
from moysklad_logger import get_moysklad_logger

logger = logging.getLogger(__name__)
moysklad_logger = get_moysklad_logger()


def get_optimized_stock_quantities_force_update(ui_updater_instance, barcodes: List[str], progress_callback=None, current_user=None) -> Dict[str, int]:
    """
    Оптимизированная функция получения остатков для нескольких штрихкодов с принудительным обновлением
    Гарантирует, что все запрашиваемые штрихкоды будут возвращены в результате
    """
    try:
        moysklad_logger.info(f"=== НАЧАЛО ОПТИМИЗИРОВАННОГО ПОЛУЧЕНИЯ ОСТАТКОВ ===")
        moysklad_logger.info(f"Количество штрихкодов: {len(barcodes)}")
        moysklad_logger.info(f"Штрихкоды: {barcodes}")

        # Получаем настройки пользователя для получения токена и выбранных складов
        user_settings = database.get_user_settings(current_user)
        if not user_settings or not user_settings.get('moysklad_enabled', True):
            # Если интеграция отключена, возвращаем 0 для всех штрихкодов
            moysklad_logger.info("Интеграция с МойСклад отключена")
            return {barcode: 0 for barcode in barcodes}

        if not user_settings or not user_settings.get('moysklad_token'):
            # Если токен не настроен, возвращаем 0 для всех штрихкодов
            moysklad_logger.info("Токен МойСклад не настроен")
            return {barcode: 0 for barcode in barcodes}

        # Создаем API
        api = MoyskladAPI(user_settings['moysklad_token'])

        # Получаем выбранные склады
        selected_stores = []
        try:
            stores_str = user_settings.get('moysklad_stores', '[]')
            selected_stores = json.loads(stores_str)
        except json.JSONDecodeError:
            selected_stores = []
        
        # Инициализируем результат с нулями для всех штрихкодов
        result = {barcode: 0 for barcode in barcodes}
        
        moysklad_logger.info(f"Выбранные склады: {selected_stores}")
        
        if barcodes:
            # Обновляем прогресс
            if progress_callback:
                progress_callback(0, len(barcodes))
            
            # Находим все товары по штрихкодам за один запрос
            logger.info(f"Поиск товаров по {len(barcodes)} штрихкодам")
            products_map = api._find_products_by_barcodes(barcodes)
            
            # Получаем ID только существующих товаров
            product_ids = [pid for pid in products_map.values() if pid is not None]
            logger.info(f"Найдено {len(product_ids)} товаров из {len(barcodes)} штрихкодов")
            
            # Если есть найденные товары, получаем их остатки за один запрос
            if product_ids:
                logger.info(f"Получение остатков для {len(product_ids)} товаров")
                stock_data = api.get_current_stock(
                    product_ids=product_ids,
                    include_zero_lines=True,
                    store_ids=selected_stores
                )
                
                # Обрабатываем полученные данные
                rows_data = []
                if isinstance(stock_data, dict) and 'rows' in stock_data:
                    rows_data = stock_data['rows']
                elif isinstance(stock_data, list):
                    rows_data = stock_data
                else:
                    logger.warning(f"Непредвиденная структура данных в stock_data: {type(stock_data)}")
                
                logger.info(f"Получено {len(rows_data)} строк остатков")
                
                # Группируем остатки по товарам
                stocks_by_product = {}
                for row in rows_data:
                    # Извлекаем ID товара из строки
                    product_id = None
                    
                    # assortmentId
                    aid = row.get('assortmentId')
                    if aid:
                        product_id = aid
                    
                    # Из метаданных ассортимента
                    if not product_id:
                        assortment_meta = row.get('assortment', {}).get('meta', {})
                        href = assortment_meta.get('href', '')
                        if href:
                            product_id = href.split('/')[-1]
                    
                    # id в строке
                    if not product_id:
                        row_id = row.get('id')
                        if row_id:
                            if '/' in row_id:
                                product_id = row_id.split('/')[-1]
                            else:
                                product_id = row_id
                    
                    if product_id:
                        if product_id not in stocks_by_product:
                            stocks_by_product[product_id] = 0
                        
                        # Извлекаем все возможные поля остатков
                        stock = row.get('stock', 0)
                        available = row.get('available', 0)
                        quantity = row.get('quantity', 0)
                        reserve = row.get('reserve', 0)
                        in_transit = row.get('inTransit', 0)

                        # Используем только 'stock' значение, как требовалось
                        actual_stock = stock
                        # Логируем все значения для анализа
                        logger.debug(f"Остатки для товара: stock={stock}, available={available}, quantity={quantity}, reserve={reserve}, inTransit={in_transit}")

                        # Проверяем, нужно ли фильтровать по складам
                        if selected_stores:
                            store_id = row.get('storeId')
                            # Добавляем остаток, только если он относится к одному из выбранных складов
                            if store_id and store_id in selected_stores:
                                stocks_by_product[product_id] += actual_stock
                                logger.debug(f"Добавлен остаток {actual_stock} для товара {product_id} на складе {store_id}, текущий итог: {stocks_by_product[product_id]}")
                        else:
                            # Если склады не указаны, добавляем все остатки
                            stocks_by_product[product_id] += actual_stock
                            logger.debug(f"Добавлен остаток {actual_stock} для товара {product_id}, текущий итог: {stocks_by_product[product_id]}")
                
                # Сопоставляем результаты с штрихкодами
                for barcode, product_id in products_map.items():
                    if product_id and product_id in stocks_by_product:
                        result[barcode] = stocks_by_product[product_id]
                        logger.info(f"Остаток для штрихкода {barcode}: {stocks_by_product[product_id]}")
                    elif product_id:
                        # Если товар найден, но остатки не получены, пробуем получить отдельно
                        logger.info(f"Остатки для товара {product_id} не найдены в общем запросе, пробуем получить отдельно")
                        try:
                            single_stock_data = api.get_current_stock(
                                product_ids=[product_id],
                                include_zero_lines=True,
                                store_ids=selected_stores
                            )
                            
                            single_total = 0
                            single_rows_data = []
                            if isinstance(single_stock_data, dict) and 'rows' in single_stock_data:
                                single_rows_data = single_stock_data['rows']
                            elif isinstance(single_stock_data, list):
                                single_rows_data = single_stock_data
                            
                            for single_row in single_rows_data:
                                # Извлекаем ID товара из строки
                                single_product_id = None
                                
                                # assortmentId
                                aid = single_row.get('assortmentId')
                                if aid:
                                    single_product_id = aid
                                
                                # Из метаданных ассортимента
                                if not single_product_id:
                                    ass_meta = single_row.get('assortment', {}).get('meta', {})
                                    href = ass_meta.get('href', '')
                                    if href:
                                        single_product_id = href.split('/')[-1]
                                
                                # id в строке
                                if not single_product_id:
                                    row_id = single_row.get('id')
                                    if row_id:
                                        if '/' in row_id:
                                            single_product_id = row_id.split('/')[-1]
                                        else:
                                            single_product_id = row_id
                                
                                if single_product_id == product_id:
                                    # Извлекаем остатки
                                    stock = single_row.get('stock', 0)
                                    available = single_row.get('available', 0)
                                    quantity = single_row.get('quantity', 0)
                                    reserve = single_row.get('reserve', 0)
                                    in_transit = single_row.get('inTransit', 0)
                                    
                                    # Используем сумму всех значений
                                    actual_stock = stock + available + quantity + reserve + in_transit
                                    # Но также учитываем максимальное значение
                                    if actual_stock == 0:
                                        actual_stock = max(stock, available, quantity, reserve, in_transit)
                                    
                                    # Проверяем фильтрацию по складам
                                    if selected_stores:
                                        store_id = single_row.get('storeId')
                                        if store_id and store_id in selected_stores:
                                            single_total += actual_stock
                                    else:
                                        single_total += actual_stock
                            
                            result[barcode] = single_total
                            logger.info(f"Отдельный запрос дал результат для штрихкода {barcode}: {single_total}")
                        except Exception as e:
                            logger.error(f"Ошибка при отдельном получении остатков для штрихкода {barcode}: {e}")
                            result[barcode] = 0  # Устанавливаем 0 в случае ошибки
                    else:
                        # Если товар не найден, оставляем 0
                        logger.info(f"Товар для штрихкода {barcode} не найден, остаток 0")
            
            # Для товаров, которые не были найдены в МойСкладе, устанавливаем 0
            for barcode in barcodes:
                if barcode not in result:
                    result[barcode] = 0
                    logger.info(f"Штрихкод {barcode} не найден в МойСкладе, установлен остаток 0")
        
        # Обновляем кэш
        stock_cache.set_cached_quantities(result)
        
        moysklad_logger.info(f"РЕЗУЛЬТАТ ОПТИМИЗИРОВАННОГО ПОЛУЧЕНИЯ ОСТАТКОВ:")
        moysklad_logger.info(f"Обработано штрихкодов: {len(result)}")
        for barcode, quantity in result.items():
            moysklad_logger.info(f"  Штрихкод {barcode}: {quantity} ед.")
        moysklad_logger.info(f"=== КОНЕЦ ОПТИМИЗИРОВАННОГО ПОЛУЧЕНИЯ ОСТАТКОВ ===")
        
        # Обновляем прогресс до 100%
        if progress_callback:
            progress_callback(len(barcodes), len(barcodes))
        
        return result
    except Exception as e:
        logger.error(f"Ошибка получения остатков для нескольких товаров: {e}")
        moysklad_logger.error(f"ОШИБКА получения остатков для нескольких товаров: {e}", exc_info=True)
        # В случае ошибки, возвращаем 0 для всех штрихкодов
        result = {barcode: 0 for barcode in barcodes}
        
        # Обновляем прогресс до 100%
        if progress_callback:
            progress_callback(len(barcodes), len(barcodes))
        
        return result


def get_optimized_stock_quantity_for_item(ui_updater_instance, barcode: str, current_user=None) -> int:
    """
    Оптимизированная функция получения остатка для одного штрихкода
    """
    try:
        # Получаем настройки пользователя для проверки, включена ли интеграция
        user_settings = database.get_user_settings(current_user)
        if not user_settings or not user_settings.get('moysklad_enabled', True):
            return 0  # Если интеграция отключена, возвращаем 0

        if not user_settings or not user_settings.get('moysklad_token'):
            return 0  # Если токен не настроен, возвращаем 0

        # Сначала пробуем получить из кэша
        cached_qty = stock_cache.get_cached_quantities([barcode]).get(barcode)
        if cached_qty is not None:
            return cached_qty

        # Если в кэше нет, запрашиваем через оптимизированную функцию для одного штрихкода
        result = get_optimized_stock_quantities_force_update(ui_updater_instance, [barcode])
        quantity = result.get(barcode, 0)
        
        # Сохраняем в кэш
        stock_cache.set_cached_quantities({barcode: quantity})
        return quantity
    except Exception as e:
        logger.error(f"Ошибка получения остатков для штрихкода {barcode} через API: {e}")
        # В случае ошибки, возвращаем кэшированное значение или 0
        cached_qty = stock_cache.get_cached_quantities([barcode]).get(barcode)
        if cached_qty is not None:
            return cached_qty
        else:
            stock_cache.set_cached_quantities({barcode: 0})
            return 0


def invalidate_stock_cache():
    """Функция для очистки оптимизированного кэша остатков"""
    stock_cache.invalidate_cache()
