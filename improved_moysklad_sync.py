"""
Улучшенная система синхронизации остатков из МойСклад
"""
import logging
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from PyQt6.QtCore import QObject, QThread, pyqtSignal
import database
from moysklad_api import MoyskladAPI
from get_stock_quantity_for_item import stock_cache
from moysklad_logger import get_moysklad_logger

logger = logging.getLogger(__name__)
moysklad_logger = get_moysklad_logger()

class ImprovedMoyskladSync(QObject):
    """
    Улучшенный класс для синхронизации остатков из МойСклад
    """
    # Сигналы для обновления прогресса
    progress_updated = pyqtSignal(int, int)  # текущий, общий
    progress_text_updated = pyqtSignal(str)  # текст прогресса
    sync_started = pyqtSignal()
    sync_completed = pyqtSignal(dict)  # результат синхронизации
    sync_error = pyqtSignal(str)  # ошибка синхронизации

    def __init__(self, ui_updater_instance):
        super().__init__()
        self.ui_updater_instance = ui_updater_instance
        self.api = None
        self.selected_stores = []
        self.sync_thread = None
        self.sync_worker = None

    def cleanup(self):
        """Безопасная очистка потока при закрытии приложения"""
        if self.sync_thread and self.sync_thread.isRunning():
            self.sync_thread.quit()
            self.sync_thread.wait(5000)

    def initialize_api(self):
        """Инициализация API с проверкой глобальных настроек"""
        try:
            # Получаем глобальные настройки (не зависят от пользователя)
            moysklad_enabled = database.get_moysklad_enabled()
            moysklad_token = database.get_moysklad_token()
            moysklad_stores = database.get_moysklad_stores()
            
            if not moysklad_enabled:
                raise Exception("Интеграция с МойСклад отключена")

            if not moysklad_token:
                raise Exception("Токен МойСклад не настроен")

            self.api = MoyskladAPI(moysklad_token)

            # Получаем выбранные склады
            try:
                self.selected_stores = json.loads(moysklad_stores) if moysklad_stores else []
            except json.JSONDecodeError:
                self.selected_stores = []

            logger.info(f"API МойСклад инициализирован, складов выбрано: {len(self.selected_stores)}")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации API: {e}")
            raise

    def collect_all_barcodes(self, shipments) -> List[str]:
        """Сбор всех уникальных штрихкодов из поставок"""
        all_barcodes = set()
        for shipment in shipments.values():
            all_barcodes.update(shipment.shipment_items.keys())
        return list(all_barcodes)

    def sync_stocks_async(self, shipments):
        """Асинхронная синхронизация остатков для всех поставок"""
        # Создаем отдельный поток для выполнения синхронизации
        self.sync_thread = QThread()
        self.sync_worker = SyncWorker(self, shipments)
        
        # Переносим воркер в поток
        self.sync_worker.moveToThread(self.sync_thread)
        
        # Подключаем сигналы
        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.finished.connect(self._on_sync_finished)
        self.sync_worker.error.connect(self._on_sync_error)
        self.sync_worker.progress_updated.connect(self.progress_updated)
        self.sync_worker.progress_text_updated.connect(self.progress_text_updated)
        
        # Запускаем поток
        self.sync_thread.start()
        
        # Сигнализируем начало синхронизации
        self.sync_started.emit()

    def _on_sync_finished(self, result):
        """Обработка завершения синхронизации"""
        self.sync_thread.quit()
        self.sync_thread.wait()
        self.sync_completed.emit(result)

    def _on_sync_error(self, error_message):
        """Обработка ошибки синхронизации"""
        self.sync_thread.quit()
        self.sync_thread.wait()
        self.sync_error.emit(error_message)

    def perform_sync(self, shipments) -> Dict[str, int]:
        """
        Выполнение синхронизации остатков
        Возвращает словарь {barcode: quantity} для всех штрихкодов
        """
        try:
            moysklad_logger.info(f"=== НАЧАЛО СИНХРОНИЗАЦИИ ОСТАТКОВ ЧЕРЕЗ IMPROVED MOYSLAD SYNC ===")
            self.initialize_api()
            
            # Собираем все штрихкоды
            all_barcodes = self.collect_all_barcodes(shipments)
            logger.info(f"Собрано {len(all_barcodes)} уникальных штрихкодов для синхронизации")
            moysklad_logger.info(f"Собрано {len(all_barcodes)} уникальных штрихкодов для синхронизации")
            
            if not all_barcodes:
                logger.info("Нет штрихкодов для синхронизации")
                return {}
            
            # ОБНУЛЯЕМ кэш перед синхронизацией - это гарантирует, что старые закешированные значения не повлияют на результат
            logger.info(f"Обнуляем кэш остатков для {len(all_barcodes)} штрихкодов перед синхронизацией")
            self._clear_cache_before_sync(all_barcodes)
            
            # Выполняем пакетную синхронизацию
            result = self._sync_barcodes_batch(all_barcodes)
            
            # Обновляем кэш в базе данных
            self._update_database_cache(result)
            
            # Обновляем локальный кэш
            self._update_local_cache(result)
            
            logger.info(f"Синхронизация завершена для {len(result)} штрихкодов")
            moysklad_logger.info(f"РЕЗУЛЬТАТ СИНХРОНИЗАЦИИ:")
            moysklad_logger.info(f"Обработано штрихкодов: {len(result)}")
            for barcode, quantity in result.items():
                moysklad_logger.info(f"  Штрихкод {barcode}: {quantity} ед.")
            moysklad_logger.info(f"=== КОНЕЦ СИНХРОНИЗАЦИИ ОСТАТКОВ ЧЕРЕЗ IMPROVED MOYSLAD SYNC ===")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при синхронизации остатков: {e}", exc_info=True)
            moysklad_logger.error(f"ОШИБКА синхронизации остатков: {e}", exc_info=True)
            raise

    def _sync_barcodes_batch(self, barcodes: List[str]) -> Dict[str, int]:
        """
        Пакетная синхронизация остатков для списка штрихкодов
        Гарантирует, что все штрихкоды будут возвращены в результате
        """
        # Инициализируем результат с нулевыми значениями для всех штрихкодов
        result = {barcode: 0 for barcode in barcodes}
        
        if not self.api:
            logger.warning("API не инициализирован, возвращаем нулевые остатки")
            return result
        
        # Выполняем пакетный запрос
        try:
            moysklad_logger.info(f"ПАКЕТНОЕ ПОЛУЧЕНИЕ ОСТАТКОВ:")
            moysklad_logger.info(f"Количество штрихкодов: {len(barcodes)}")
            moysklad_logger.info(f"Выбранные склады: {self.selected_stores}")
            batch_result = self.api.get_stocks_for_barcodes_batch(barcodes, self.selected_stores)
            
            # Обновляем результат только для тех штрихкодов, для которых получены данные
            for barcode, quantity in batch_result.items():
                if barcode in result:
                    result[barcode] = quantity
                else:
                    # Это дополнительная защита - все равно добавляем если вдруг
                    result[barcode] = quantity
            
            logger.info(f"Получено {len(batch_result)} результатов из {len(barcodes)} запрошенных штрихкодов")
            
            # Проверяем, есть ли штрихкоды, для которых не получены данные
            missing_barcodes = [bc for bc in barcodes if bc not in batch_result]
            if missing_barcodes:
                logger.info(f"Для {len(missing_barcodes)} штрихкодов не получены данные (будут 0): {missing_barcodes[:10]}...")
                moysklad_logger.info(f"Для {len(missing_barcodes)} штрихкодов не получены данные: {missing_barcodes}")
            
        except Exception as e:
            logger.error(f"Ошибка при пакетном получении остатков: {e}")
            moysklad_logger.error(f"ОШИБКА при пакетном получении остатков: {e}", exc_info=True)
            # В случае ошибки, оставляем все значения как 0
        
        return result

    def _update_database_cache(self, stock_data: Dict[str, int]):
        """Обновление кэша остатков в базе данных"""
        try:
            # Используем массовое обновление для эффективности
            database.set_multiple_stock_cache(stock_data)
        except Exception as e:
            logger.error(f"Ошибка при обновлении кэша в базе данных: {e}")
            # В случае ошибки массового обновления, используем поэлементное обновление
            for barcode, quantity in stock_data.items():
                try:
                    database.set_stock_cache(barcode, quantity)
                except Exception as item_error:
                    logger.error(f"Ошибка при обновлении кэша для штрихкода {barcode}: {item_error}")

    def _update_local_cache(self, stock_data: Dict[str, int]):
        """Обновление локального кэша остатков"""
        try:
            # Используем тот же кэш, что и в функции get_enhanced_stock_quantities_force_update
            if hasattr(get_enhanced_stock_quantities_force_update, 'enhanced_cache'):
                enhanced_cache = get_enhanced_stock_quantities_force_update.enhanced_cache
                enhanced_cache.set_cached_quantities(stock_data)
            else:
                # Если enhanced_cache не инициализирован, используем оригинальный stock_cache
                with stock_cache.lock:
                    timestamp = datetime.now()
                    for barcode, quantity in stock_data.items():
                        stock_cache.cache[barcode] = {
                            'quantity': quantity,
                            'timestamp': timestamp
                        }
        except Exception as e:
            logger.error(f"Ошибка при обновлении локального кэша: {e}")

    def _clear_cache_before_sync(self, barcodes: List[str]):
        """Обнуляем кэш остатков перед синхронизацией"""
        try:
            # Обнуляем кэш в базе данных для всех штрихкодов, участвующих в синхронизации
            zero_data = {barcode: 0 for barcode in barcodes}
            database.set_multiple_stock_cache(zero_data)
            
            # Обнуляем локальный кэш для всех штрихкодов
            # Используем тот же кэш, что и в функции get_enhanced_stock_quantities_force_update
            if hasattr(get_enhanced_stock_quantities_force_update, 'enhanced_cache'):
                enhanced_cache = get_enhanced_stock_quantities_force_update.enhanced_cache
                enhanced_cache.clear_cache_for_barcodes(barcodes)
            else:
                # Если enhanced_cache не инициализирован, используем оригинальный stock_cache
                with stock_cache.lock:
                    for barcode in barcodes:
                        stock_cache.cache[barcode] = {
                            'quantity': 0,
                            'timestamp': datetime.now()
                        }
            
            logger.info(f"Кэш обнулен для {len(barcodes)} штрихкодов перед синхронизацией")
            moysklad_logger.info(f"КЭШ ОБНУЛЕН для {len(barcodes)} штрихкодов перед синхронизацией")
            
        except Exception as e:
            logger.error(f"Ошибка при обнулении кэша перед синхронизацией: {e}")
            moysklad_logger.error(f"ОШИБКА при обнулении кэша перед синхронизацией: {e}", exc_info=True)

    def _clear_cache_before_sync(self, barcodes: List[str]):
        """Обнуляем кэш остатков перед синхронизацией"""
        try:
            # Обнуляем кэш в базе данных для всех штрихкодов, участвующих в синхронизации
            zero_data = {barcode: 0 for barcode in barcodes}
            database.set_multiple_stock_cache(zero_data)
            
            # Обнуляем локальный кэш для всех штрихкодов
            with stock_cache.lock:
                for barcode in barcodes:
                    stock_cache.cache[barcode] = {
                        'quantity': 0,
                        'timestamp': datetime.now()
                    }
            
            logger.info(f"Кэш обнулен для {len(barcodes)} штрихкодов перед синхронизацией")
            moysklad_logger.info(f"КЭШ ОБНУЛЕН для {len(barcodes)} штрихкодов перед синхронизацией")
            
        except Exception as e:
            logger.error(f"Ошибка при обнулении кэша перед синхронизацией: {e}")
            moysklad_logger.error(f"ОШИБКА при обнулении кэша перед синхронизацией: {e}", exc_info=True)


class SyncWorker(QObject):
    """
    Воркер для выполнения синхронизации в отдельном потоке
    """
    finished = pyqtSignal(object)  # результат
    error = pyqtSignal(str)  # ошибка
    progress_updated = pyqtSignal(int, int)  # текущий, общий
    progress_text_updated = pyqtSignal(str)  # текст прогресса

    def __init__(self, sync_handler, shipments):
        super().__init__()
        self.sync_handler = sync_handler
        self.shipments = shipments

    def run(self):
        """Выполнение синхронизации в отдельном потоке"""
        try:
            result = self.sync_handler.perform_sync(self.shipments)
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Ошибка в асинхронной синхронизации: {e}", exc_info=True)
            self.error.emit(str(e))


from memory_manager import ManagedCache, memory_manager

class EnhancedStockCache:
    """
    Улучшенный класс кэширования остатков с TTL, групповыми операциями и контролем размера
    """
    
    def __init__(self, cache_duration_minutes=5, max_cache_size=10000):
        # Используем управляемый кэш вместо обычного словаря
        self.cache = ManagedCache(
            name="stock_cache",
            max_size=max_cache_size,
            ttl_seconds=cache_duration_minutes * 60,
            max_memory_mb=100,  # 100 МБ максимум
            cleanup_interval=300  # Очистка каждые 5 минут
        )
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self.lock = threading.RLock()  # Используем потокобезопасную блокировку
        self.bulk_cache = ManagedCache(
            name="stock_bulk_cache", 
            max_size=1000,
            ttl_seconds=cache_duration_minutes * 60,
            max_memory_mb=50
        )
        
        logger.info(f"EnhancedStockCache инициализирован с максимальным размером {max_cache_size} элементов")

    def get_cached_quantities(self, barcodes: List[str]) -> Dict[str, int]:
        """Получить кэшированные количества для списка штрихкодов"""
        result = {}
        uncached_barcodes = []
        
        # Получаем данные из управляемого кэша
        for barcode in barcodes:
            cached_data = self.cache.get(barcode)
            if cached_data is not None:
                result[barcode] = cached_data
            else:
                uncached_barcodes.append(barcode)
        
        # Если есть не кэшированные штрихкоды, пробуем получить из базы данных
        if uncached_barcodes:
            try:
                from database import get_multiple_stock_cache
                db_results = get_multiple_stock_cache(uncached_barcodes)
                
                for barcode in uncached_barcodes:
                    if barcode in db_results:
                        quantity = db_results[barcode]
                        result[barcode] = quantity
                        # Сохраняем в локальный кэш на будущее
                        self.cache.put(barcode, quantity)
                    else:
                        # Если нет в базе, возвращаем 0
                        result[barcode] = 0
                        # Но не сохраняем в кэш, чтобы не блокировать обновления
            except Exception as e:
                logger.error(f"Ошибка получения кэша остатков из базы данных: {e}")
                # В случае ошибки, возвращаем 0 для всех не кэшированных штрихкодов
                for barcode in uncached_barcodes:
                    result[barcode] = 0
        
        return result

    def set_cached_quantities(self, stock_data: Dict[str, int]):
        """Сохранить количества для нескольких штрихкодов"""
        # Сохраняем в управляемый кэш
        for barcode, quantity in stock_data.items():
            self.cache.put(barcode, quantity)
        
        # Также сохраняем в базу данных
        try:
            from database import set_multiple_stock_cache
            set_multiple_stock_cache(stock_data)
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша остатков в базу данных: {e}")
    
    def clear_cache_for_barcodes(self, barcodes: List[str]):
        """Очистить кэш для конкретных штрихкодов"""
        for barcode in barcodes:
            self.cache.invalidate(barcode)
        
        # Также очищаем bulk кэш
        self.bulk_cache.clear()
    
    def get_cache_stats(self):
        """Получить статистику кэша"""
        return {
            'main_cache': self.cache.get_stats(),
            'bulk_cache': self.bulk_cache.get_stats()
        }

    def invalidate_cache(self):
        """Очистить весь кэш"""
        self.cache.clear()
        self.bulk_cache.clear()
        
        # Также очищаем кэш в базе данных
        try:
            from database import clear_stock_cache
            clear_stock_cache()
        except Exception as e:
            logger.error(f"Ошибка очистки кэша остатков в базе данных: {e}")

    def clear_cache_for_barcodes(self, barcodes: List[str]):
        """Очистить кэш для указанных штрихкодов (установить значение 0)"""
        # Очищаем из управляемого кэша
        for barcode in barcodes:
            self.cache.invalidate(barcode)
        
        # Также обновляем в базе данных
        zero_data = {barcode: 0 for barcode in barcodes}
        try:
            from database import set_multiple_stock_cache
            set_multiple_stock_cache(zero_data)
        except Exception as e:
            logger.error(f"Ошибка обновления кэша в базе данных при очистке: {e}")


def get_enhanced_stock_quantities_force_update(ui_updater_instance, barcodes, progress_callback=None, current_user=None):
    """
    Улучшенная функция получения остатков для нескольких штрихкодов с принудительным обновлением
    Гарантирует, что все запрашиваемые штрихкоды будут возвращены в результате
    """
    # Инициализируем улучшенный кэш, если он еще не создан
    if not hasattr(get_enhanced_stock_quantities_force_update, 'enhanced_cache'):
        get_enhanced_stock_quantities_force_update.enhanced_cache = EnhancedStockCache()

    enhanced_cache = get_enhanced_stock_quantities_force_update.enhanced_cache

    try:
        moysklad_logger.info(f"=== НАЧАЛО ПОЛУЧЕНИЯ ОСТАТКОВ ЧЕРЕЗ ENHANCED STOCK QUANTITIES FORCE UPDATE ===")
        moysklad_logger.info(f"Количество штрихкодов: {len(barcodes)}")
        moysklad_logger.info(f"Штрихкоды: {barcodes}")

        # Обнуляем кэш перед синхронизацией - это гарантирует, что старые закешированные значения не повлияют на результат
        logger.info(f"Обнуляем кэш остатков для {len(barcodes)} штрихкодов перед синхронизацией")
        enhanced_cache.clear_cache_for_barcodes(barcodes)

        logger.info(f"Кэш обнулен для {len(barcodes)} штрихкодов перед синхронизацией")
        moysklad_logger.info(f"КЭШ ОБНУЛЕН для {len(barcodes)} штрихкодов перед синхронизацией")

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
            # Выполняем пакетный запрос
            batch_result = api.get_stocks_for_barcodes_batch(barcodes, selected_stores)
            
            # Обновляем результат только для тех штрихкодов, для которых получены данные
            for barcode, quantity in batch_result.items():
                if barcode in result:
                    result[barcode] = quantity
            
            # Проверяем, есть ли штрихкоды, для которых не получены данные, и пытаемся получить их отдельно
            # Это может помочь в случае, если товары существуют, но по какой-то причине не были включены в пакетный результат
            missing_barcodes = [bc for bc in barcodes if bc not in batch_result]
            if missing_barcodes:
                logger.info(f"Для {len(missing_barcodes)} штрихкодов не получены данные через пакетный запрос, пробуем получить отдельно")
                for barcode in missing_barcodes:
                    try:
                        # Пытаемся найти товар по штрихкоду и получить его остатки
                        product = api._find_product_by_barcode(barcode)
                        if product:
                            # Если товар найден, получаем его остатки
                            product_id = product['id']
                            # Используем get_current_stock для получения остатков для конкретного товара
                            stock_data = api.get_current_stock(product_ids=[product_id], include_zero_lines=True, store_ids=selected_stores)
                            if 'rows' in stock_data:
                                total_stock = 0
                                for row in stock_data['rows']:
                                    # Проверяем, что строка относится к нужному товару и складу
                                    row_product_id = row.get('assortmentId')
                                    if row_product_id == product_id:
                                        store_id = row.get('storeId')
                                        # Если указаны конкретные склады, проверяем, что строка относится к одному из них
                                        if not selected_stores or not store_id or store_id in selected_stores:
                                            stock_val = row.get('stock', 0)
                                            available_val = row.get('available', 0)
                                            quantity_val = row.get('quantity', 0)
                                            reserve_val = row.get('reserve', 0)
                                            in_transit_val = row.get('inTransit', 0)
                                            
                                            # Используем сумму всех значений, чтобы получить полный остаток
                                            actual_stock = stock_val + available_val + quantity_val + reserve_val + in_transit_val
                                            # Но также учитываем максимальное значение, если сумма не дает результата
                                            if actual_stock == 0:
                                                actual_stock = max(stock_val, available_val, quantity_val, reserve_val, in_transit_val)
                                            
                                            total_stock += actual_stock
                            
                            # Обновляем результат для этого штрихкода
                            result[barcode] = total_stock
                            logger.info(f"Для штрихкода {barcode} получен остаток {total_stock} через отдельный запрос")
                        else:
                            logger.warning(f"Товар с штрихкодом {barcode} не найден в МойСклад")
                    except Exception as e:
                        logger.error(f"Ошибка при получении остатков отдельно для штрихкода {barcode}: {e}")
        
        # Обновляем кэш
        enhanced_cache.set_cached_quantities(result)
        
        # Обновляем кэш в базе данных
        database.set_multiple_stock_cache(result)
        
        moysklad_logger.info(f"РЕЗУЛЬТАТ ПОЛУЧЕНИЯ ОСТАТКОВ:")
        moysklad_logger.info(f"Обработано штрихкодов: {len(result)}")
        for barcode, quantity in result.items():
            moysklad_logger.info(f"  Штрихкод {barcode}: {quantity} ед.")
        moysklad_logger.info(f"=== КОНЕЦ ПОЛУЧЕНИЯ ОСТАТКОВ ЧЕРЕЗ ENHANCED STOCK QUANTITIES FORCE UPDATE ===")
        
        return result
    except Exception as e:
        logger.error(f"Ошибка получения остатков для нескольких товаров: {e}")
        moysklad_logger.error(f"ОШИБКА получения остатков для нескольких товаров: {e}", exc_info=True)
        # В случае ошибки, возвращаем 0 для всех штрихкодов
        return {barcode: 0 for barcode in barcodes}