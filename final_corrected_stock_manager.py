"""
Финальный оптимизированный менеджер синхронизации остатков из МойСклад
Содержит только необходимые функции с оптимальным кэшированием и батчингом запросов
"""
import logging
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable

import database
from moysklad_api import MoyskladAPI
from moysklad_logger import get_moysklad_logger

logger = logging.getLogger(__name__)
moysklad_logger = get_moysklad_logger()


class FinalOptimizedStockManager:
    """Финальный оптимизированный класс для синхронизации остатков из МойСклад"""
    
    def __init__(self, cache_duration_minutes=5):
        self.api = None
        self.selected_stores = []
        self.stock_cache = {}  # Локальный кэш {barcode: {'quantity': int, 'timestamp': datetime}}
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self.lock = threading.RLock()  # Потокобезопасная блокировка
        
    def initialize_api(self, token: str, store_ids: List[str] = None):
        """Инициализация API с проверкой настроек"""
        try:
            self.api = MoyskladAPI(token)
            self.selected_stores = store_ids or []
            logger.info(f"API МойСклад инициализирован, складов выбрано: {len(self.selected_stores)}")
        except Exception as e:
            logger.error(f"Ошибка инициализации API: {e}")
            raise

    def get_cached_quantity(self, barcode: str) -> Optional[int]:
        """Получить кэшированное количество для штрихкода (сначала из локального кэша, затем из базы данных)"""
        with self.lock:
            if barcode in self.stock_cache:
                cached_data = self.stock_cache[barcode]
                if datetime.now() - cached_data['timestamp'] < self.cache_duration:
                    return cached_data['quantity']
                else:
                    # Удаляем устаревший кэш
                    del self.stock_cache[barcode]
            
            # Если нет в локальном кэше, пробуем получить из базы данных
            try:
                db_quantity = database.get_stock_cache(barcode)
                if db_quantity is not None:
                    # Сохраняем в локальный кэш на будущее
                    self.stock_cache[barcode] = {
                        'quantity': db_quantity,
                        'timestamp': datetime.now()
                    }
                    return db_quantity
            except Exception as e:
                logger.error(f"Ошибка получения кэша остатков из базы данных для штрихкода {barcode}: {e}")
            
            return None

    def set_cached_quantity(self, barcode: str, quantity: int):
        """Сохранить количество в кэш (локально и в базе данных)"""
        with self.lock:
            self.stock_cache[barcode] = {
                'quantity': quantity,
                'timestamp': datetime.now()
            }
            
            # Также сохраняем в базу данных
            try:
                database.set_stock_cache(barcode, quantity)
            except Exception as e:
                logger.error(f"Ошибка сохранения кэша остатков в базу данных для штрихкода {barcode}: {e}")

    def get_stock_for_single_item(self, ui_updater_instance, barcode: str) -> int:
        """Получить остаток для одного штрихкода"""
        try:
            logger.info(f"=== ОТЛАДКА: Получение остатка для штрихкода {barcode} ===")
            moysklad_logger.info(f"Получение остатка для штрихкода {barcode}")
            
            # Сначала пробуем получить из кэша
            cached_qty = self.get_cached_quantity(barcode)
            if cached_qty is not None:
                logger.info(f"=== ОТЛАДКА: Найдено в кэше: {cached_qty}")
                return cached_qty

            # Если в кэше нет, запрашиваем из API
            if not self.api:
                logger.warning("API МойСклад не инициализирован")
                moysklad_logger.warning("API МойСклад не инициализирован")
                return 0

            # Находим товар по штрихкоду
            logger.info(f"Поиск товара по штрихкоду {barcode}...")
            moysklad_logger.info(f"Поиск товара по штрихкоду {barcode}...")
            product = self.api._find_product_by_barcode(barcode)
            
            if not product:
                logger.warning(f"Товар с штрихкодом {barcode} не найден в МойСклад")
                moysklad_logger.warning(f"Товар с штрихкодом {barcode} не найден в МойСклад")
                self.set_cached_quantity(barcode, 0)
                return 0

            product_id = product['id']
            logger.info(f"Товар найден: {product.get('name', 'Unknown')}, ID: {product_id}")
            moysklad_logger.info(f"Товар найден: {product.get('name', 'Unknown')}, ID: {product_id}")

            # Получаем остатки для конкретного товара
            logger.info(f"Получение остатков для товара {product_id}, склады: {self.selected_stores}")
            moysklad_logger.info(f"Получение остатков для товара {product_id}, склады: {self.selected_stores}")
            stock_data = self.api.get_current_stock(
                product_ids=[product_id],
                include_zero_lines=True,
                store_ids=self.selected_stores
            )
            
            logger.info(f"=== ОТЛАДКА: Получено данных об остатках: {stock_data}")
            moysklad_logger.info(f"Получено данных об остатках: {stock_data}")

            # Обрабатываем полученные данные
            total_stock = 0
            rows_data = []
            if isinstance(stock_data, dict) and 'rows' in stock_data:
                rows_data = stock_data['rows']
            elif isinstance(stock_data, list):
                rows_data = stock_data
            else:
                logger.warning(f"Непредвиденная структура данных в stock_data: {type(stock_data)}")
                moysklad_logger.warning(f"Непредвиденная структура данных: {type(stock_data)}")
                self.set_cached_quantity(barcode, 0)
                return 0

            logger.info(f"Получено {len(rows_data)} строк остатков")
            moysklad_logger.info(f"Получено {len(rows_data)} строк остатков")
            
            for idx, row in enumerate(rows_data):
                # Проверяем, что строка относится к нужному товару
                row_product_id = None

                # assortmentId
                aid = row.get('assortmentId')
                if aid:
                    row_product_id = aid

                # Из метаданных ассортимента
                if not row_product_id:
                    assortment_meta = row.get('assortment', {}).get('meta', {})
                    href = assortment_meta.get('href', '')
                    if href:
                        row_product_id = href.split('/')[-1]

                # id в строке
                if not row_product_id:
                    row_id = row.get('id')
                    if row_id:
                        if '/' in row_id:
                            row_product_id = row_id.split('/')[-1]
                        else:
                            row_product_id = row_id

                stock = row.get('stock', 0)
                store_id = row.get('storeId')
                
                logger.info(f"=== ОТЛАДКА: Строка {idx}: product_id={row_product_id}, store_id={store_id}, stock={stock}")
                moysklad_logger.info(f"Строка {idx}: product_id={row_product_id}, store_id={store_id}, stock={stock}")

                if row_product_id == product_id:
                    # Проверяем, нужно ли фильтровать по складам
                    if not self.selected_stores or not store_id or store_id in self.selected_stores:
                        total_stock += stock
                        logger.info(f"Добавлен остаток {stock} для товара {product_id} на складе {store_id}")
                        moysklad_logger.debug(f"Добавлен остаток {stock}, текущий итог: {total_stock}")
                    else:
                        logger.info(f"Пропущена строка: склад {store_id} не в списке {self.selected_stores}")

            logger.info(f"=== ОТЛАДКА: Итоговый остаток для {barcode}: {total_stock}")
            moysklad_logger.info(f"Итоговый остаток для {barcode}: {total_stock}")
            
            # Сохраняем в кэш
            self.set_cached_quantity(barcode, total_stock)
            logger.info(f"Остаток для штрихкода {barcode}: {total_stock}")
            return total_stock

        except Exception as e:
            logger.error(f"Ошибка получения остатков для штрихкода {barcode} через API: {e}")
            # В случае ошибки, возвращаем кэшированное значение или 0
            cached_qty = self.get_cached_quantity(barcode)
            if cached_qty is not None:
                return cached_qty
            else:
                self.set_cached_quantity(barcode, 0)
                return 0

    def get_stocks_for_multiple_items(self, ui_updater_instance, barcodes: List[str], progress_callback: Optional[Callable[[int, int], None]] = None) -> Dict[str, int]:
        """
        Получить остатки для нескольких штрихкодов за один запрос
        Гарантирует, что все запрашиваемые штрихкоды будут возвращены в результате
        """
        try:
            moysklad_logger.info(f"=== НАЧАЛО ФИНАЛЬНОЙ ОПТИМИЗИРОВАННОЙ СИНХРОНИЗАЦИИ ОСТАТКОВ ===")
            moysklad_logger.info(f"Количество штрихкодов: {len(barcodes)}")
            moysklad_logger.info(f"Штрихкоды: {barcodes}")
            moysklad_logger.info(f"Выбранные склады: {self.selected_stores}")
            logger.info(f"=== ОТЛАДКА: Начало получения остатков для {len(barcodes)} штрихкодов ===")
            logger.info(f"API инициализирован: {self.api is not None}")
            logger.info(f"Выбранные склады: {self.selected_stores}")

            # Инициализируем результат с 0 для всех штрихкодов (гарантирует, что все штрихкоды будут в результате)
            result = {barcode: 0 for barcode in barcodes}

            if not self.api:
                logger.warning("API МойСклад не инициализирован")
                moysklad_logger.warning("API МойСклад не инициализирован!")
                # Обновляем прогресс до 100%, если нет API
                if progress_callback:
                    progress_callback(len(barcodes), len(barcodes))
                return result

            # Находим все товары по штрихкодам за один пакетный запрос
            logger.info(f"Поиск товаров по {len(barcodes)} штрихкодам")
            moysklad_logger.info(f"Поиск товаров по {len(barcodes)} штрихкодам...")
            products_map = self.api._find_products_by_barcodes(barcodes)
            
            logger.info(f"=== ОТЛАДКА: Найдено товаров: {len(products_map)} из {len(barcodes)}")
            logger.info(f"Products map: {products_map}")
            moysklad_logger.info(f"Найдено товаров: {len(products_map)} из {len(barcodes)}")
            moysklad_logger.info(f"Products map: {products_map}")

            # Получаем ID только существующих товаров
            product_ids = [pid for pid in products_map.values() if pid is not None]
            logger.info(f"Найдено {len(product_ids)} товаров из {len(barcodes)} штрихкодов")
            
            if len(product_ids) < len(barcodes):
                not_found = [bc for bc, pid in products_map.items() if not pid]
                logger.warning(f"Не найдены товары для штрихкодов: {not_found}")
                moysklad_logger.warning(f"Не найдены товары для штрихкодов: {not_found}")

            # Если есть найденные товары, получаем их остатки за один запрос
            if product_ids:
                logger.info(f"Получение остатков для {len(product_ids)} товаров")
                moysklad_logger.info(f"Получение остатков для {len(product_ids)} товаров: {product_ids}")
                moysklad_logger.info(f"Фильтр по складам: {self.selected_stores}")
                stock_data = self.api.get_current_stock(
                    product_ids=product_ids,
                    include_zero_lines=True,
                    store_ids=self.selected_stores
                )
                
                logger.info(f"=== ОТЛАДКА: Получено данных об остатках: {stock_data}")
                moysklad_logger.info(f"Получено данных об остатках: {stock_data}")
                
                # Обрабатываем полученные данные
                rows_data = []
                if isinstance(stock_data, dict) and 'rows' in stock_data:
                    rows_data = stock_data['rows']
                elif isinstance(stock_data, list):
                    rows_data = stock_data
                else:
                    logger.warning(f"Непредвиденная структура данных в stock_data: {type(stock_data)}")
                    # Даже если структура неожиданная, все равно возвращаем словарь с 0 для всех штрихкодов
                    if progress_callback:
                        progress_callback(len(barcodes), len(barcodes))
                    return result

                logger.info(f"Получено {len(rows_data)} строк остатков")
                moysklad_logger.info(f"Получено {len(rows_data)} строк остатков")

                # Группируем остатки по товарам
                stocks_by_product = {}
                for idx, row in enumerate(rows_data):
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

                    # Извлекаем данные об остатке
                    stock = row.get('stock', 0)
                    store_id = row.get('storeId')
                    
                    logger.info(f"=== ОТЛАДКА: Строка {idx}: product_id={product_id}, store_id={store_id}, stock={stock}")
                    logger.info(f"  Полные данные строки: {row}")
                    moysklad_logger.info(f"Строка {idx}: product_id={product_id}, store_id={store_id}, stock={stock}")

                    if product_id:
                        if product_id not in stocks_by_product:
                            stocks_by_product[product_id] = 0

                        # Проверяем, нужно ли фильтровать по складам
                        if not self.selected_stores or not store_id or store_id in self.selected_stores:
                            stocks_by_product[product_id] += stock
                            logger.info(f"Добавлен остаток {stock} для товара {product_id} на складе {store_id}")
                            moysklad_logger.debug(f"Добавлен остаток {stock} для товара {product_id} на складе {store_id}, текущий итог: {stocks_by_product[product_id]}")
                        else:
                            logger.info(f"Пропущена строка: склад {store_id} не в списке выбранных {self.selected_stores}")

                logger.info(f"=== ОТЛАДКА: stocks_by_product: {stocks_by_product}")
                moysklad_logger.info(f"Остатки по товарам: {stocks_by_product}")

                # Сопоставляем результаты с штрихкодами
                for barcode, product_id in products_map.items():
                    if product_id and product_id in stocks_by_product:
                        result[barcode] = stocks_by_product[product_id]
                        logger.info(f"=== ОТЛАДКА: Остаток для штрихкода {barcode}: {stocks_by_product[product_id]}")
                        moysklad_logger.info(f"Остаток для штрихкода {barcode} (товар {product_id}): {stocks_by_product[product_id]}")
                        # Сохраняем в кэш
                        self.set_cached_quantity(barcode, stocks_by_product[product_id])
                    elif product_id:
                        logger.info(f"Остатки для товара {product_id} не найдены в общем запросе (stock=0)")
                        moysklad_logger.warning(f"Остатки для товара {product_id} не найдены, будет 0")
                        try:
                            single_stock_data = self.api.get_current_stock(
                                product_ids=[product_id],
                                include_zero_lines=True,
                                store_ids=self.selected_stores
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
                                    # Извлекаем только основное поле 'stock' (реальный остаток)
                                    stock = single_row.get('stock', 0)
                                    
                                    # Проверяем фильтрацию по складам
                                    store_id = single_row.get('storeId')
                                    if not self.selected_stores or not store_id or store_id in self.selected_stores:
                                        single_total += stock
                            
                            result[barcode] = single_total
                            logger.info(f"Отдельный запрос дал результат для штрихкода {barcode}: {single_total}")
                            # Сохраняем в кэш
                            self.set_cached_quantity(barcode, single_total)
                        except Exception as e:
                            logger.error(f"Ошибка при отдельном получении остатков для штрихкода {barcode}: {e}")
                            result[barcode] = 0  # Устанавливаем 0 в случае ошибки
                            # Сохраняем 0 в кэш
                            self.set_cached_quantity(barcode, 0)
                    else:
                        # Если товар не найден, оставляем 0 (уже установлен в инициализации result)
                        logger.info(f"Товар для штрихкода {barcode} не найден, остаток 0")
                        # Сохраняем 0 в кэш
                        self.set_cached_quantity(barcode, 0)
            
            # Для товаров, которые не были найдены в МойСкладе, уже установлено 0 в инициализации result
            for barcode in barcodes:
                if barcode not in result:
                    result[barcode] = 0
                    logger.info(f"Штрихкод {barcode} не найден в МойСкладе, установлен остаток 0")
                    # Сохраняем 0 в кэш
                    self.set_cached_quantity(barcode, 0)
        
            moysklad_logger.info(f"РЕЗУЛЬТАТ ФИНАЛЬНОЙ ОПТИМИЗИРОВАННОЙ СИНХРОНИЗАЦИИ:")
            moysklad_logger.info(f"Обработано штрихкодов: {len(result)}")
            for barcode, quantity in result.items():
                moysklad_logger.info(f"  Штрихкод {barcode}: {quantity} ед.")
            moysklad_logger.info(f"=== КОНЕЦ ФИНАЛЬНОЙ ОПТИМИЗИРОВАННОЙ СИНХРОНИЗАЦИИ ===")
            
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

    def invalidate_cache(self):
        """Очистить весь кэш"""
        with self.lock:
            self.stock_cache.clear()
            
            # Также очищаем кэш в базе данных
            try:
                database.clear_stock_cache()
            except Exception as e:
                logger.error(f"Ошибка очистки кэша остатков в базе данных: {e}")


# Глобальный экземпляр финального оптимизированного менеджера
final_optimized_stock_manager = FinalOptimizedStockManager()


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
        cached_qty = final_optimized_stock_manager.get_cached_quantity(barcode)
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
            
            # Инициализируем API если нужно
            if final_optimized_stock_manager.api is None:
                final_optimized_stock_manager.initialize_api(user_settings['moysklad_token'], selected_stores)

            # Получаем остаток
            quantity = final_optimized_stock_manager.get_stock_for_single_item(ui_updater_instance, barcode)
            
            # Сохраняем в кэш
            final_optimized_stock_manager.set_cached_quantity(barcode, quantity)
            return quantity
        except Exception as e:
            logger.error(f"Ошибка получения остатков для штрихкода {barcode} через API: {e}")
            # В случае ошибки, возвращаем кэшированное значение или 0
            cached_qty = final_optimized_stock_manager.get_cached_quantity(barcode)
            if cached_qty is not None:
                return cached_qty
            else:
                final_optimized_stock_manager.set_cached_quantity(barcode, 0)
                return 0
    except Exception as e:
        logger.error(f"Ошибка получения остатков для штрихкода {barcode}: {e}")
        # В случае ошибки, возвращаем кэшированное значение или 0
        cached_qty = final_optimized_stock_manager.get_cached_quantity(barcode)
        if cached_qty is not None:
            return cached_qty
        else:
            final_optimized_stock_manager.set_cached_quantity(barcode, 0)
            return 0


def get_optimized_stock_quantities_force_update(ui_updater_instance, barcodes: List[str], store_ids: List[str] = None, progress_callback: Optional[Callable[[int, int], None]] = None, current_user=None) -> Dict[str, int]:
    """
    Оптимизированная функция получения остатков для нескольких штрихкодов с принудительным обновлением
    Гарантирует, что все запрашиваемые штрихкоды будут возвращены в результате
    """
    try:
        logger.info(f"=== ОТЛАДКА: Начало get_optimized_stock_quantities_force_update ===")
        logger.info(f"Количество штрихкодов: {len(barcodes)}")
        logger.info(f"Переданные store_ids: {store_ids}")
        moysklad_logger.info(f"=== НАЧАЛО get_optimized_stock_quantities_force_update ===")
        moysklad_logger.info(f"Количество штрихкодов: {len(barcodes)}")

        # Получаем глобальные настройки МойСклад
        if not database.get_moysklad_enabled():
            logger.warning("Интеграция с МойСклад отключена")
            moysklad_logger.warning("Интеграция с МойСклад отключена")
            # Если интеграция отключена, возвращаем 0 для всех штрихкодов
            result = {barcode: 0 for barcode in barcodes}
            if progress_callback:
                progress_callback(len(barcodes), len(barcodes))
            return result

        moysklad_token = database.get_moysklad_token()
        if not moysklad_token:
            logger.warning("Токен МойСклад не настроен")
            moysklad_logger.warning("Токен МойСклад не настроен")
            # Если токен не настроен, возвращаем 0 для всех штрихкодов
            result = {barcode: 0 for barcode in barcodes}
            if progress_callback:
                progress_callback(len(barcodes), len(barcodes))
            return result

        logger.info(f"Токен МойСклад: первые 10 символов '{moysklad_token[:10]}...'")
        logger.info(f"moysklad_enabled: {database.get_moysklad_enabled()}")

        # Используем переданные store_ids, если они есть, иначе получаем из глобальных настроек
        selected_stores = store_ids if store_ids is not None else []
        if not selected_stores:
            try:
                stores_str = database.get_moysklad_stores() or '[]'
                selected_stores = json.loads(stores_str)
            except json.JSONDecodeError:
                selected_stores = []

        logger.info(f"Выбранные склады: {selected_stores}")
        moysklad_logger.info(f"Выбранные склады: {selected_stores}")

        # Инициализируем API если нужно
        if final_optimized_stock_manager.api is None:
            logger.info("Инициализация API МойСклад...")
            moysklad_logger.info("Инициализация API МойСклад...")
            final_optimized_stock_manager.initialize_api(moysklad_token, selected_stores)
        else:
            logger.info("API уже инициализирован")

        # Получаем остатки для всех штрихкодов
        logger.info(f"Вызов get_stocks_for_multiple_items для {len(barcodes)} штрихкодов")
        moysklad_logger.info(f"Вызов get_stocks_for_multiple_items для {len(barcodes)} штрихкодов")
        result = final_optimized_stock_manager.get_stocks_for_multiple_items(ui_updater_instance, barcodes, progress_callback)

        logger.info(f"=== ОТЛАДКА: Результат get_stocks_for_multiple_items: {result}")
        moysklad_logger.info(f"Результат: {result}")

        # После получения данных, обновляем кэш в базе данных для каждого штрихкода
        if result:
            logger.info(f"Обновление кэша для {len(result)} штрихкодов")
            for barcode, quantity in result.items():
                database.set_stock_cache(barcode, quantity)

        return result
    except Exception as e:
        logger.error(f"Ошибка получения остатков для нескольких штрихкодов: {e}", exc_info=True)
        moysklad_logger.error(f"Ошибка получения остатков: {e}", exc_info=True)
        # В случае ошибки, возвращаем 0 для всех штрихкодов
        result = {barcode: 0 for barcode in barcodes}

        # Обновляем прогресс до 100%
        if progress_callback:
            progress_callback(len(barcodes), len(barcodes))
        
        return result


def invalidate_optimized_stock_cache():
    """Функция для очистки оптимизированного кэша остатков"""
    final_optimized_stock_manager.invalidate_cache()