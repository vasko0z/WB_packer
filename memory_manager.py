"""
Модуль для управления памятью и кэшами приложения WB Packer
Решает проблемы с утечками памяти и контролем размера кэшей
"""

import gc
import weakref
import logging
import threading
import time
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Структура для хранения элемента кэша"""
    data: Any
    timestamp: datetime
    access_count: int = 0
    size_estimate: int = 0  # Оценка размера в байтах

class MemoryManager:
    """Менеджер управления памятью и кэшами"""
    
    def __init__(self):
        self.caches: Dict[str, 'ManagedCache'] = {}
        self.weak_refs: Dict[str, weakref.WeakSet] = defaultdict(weakref.WeakSet)
        self.cleanup_timers: Dict[str, threading.Timer] = {}
        self.lock = threading.RLock()
        self.stats = {
            'total_allocated': 0,
            'total_freed': 0,
            'gc_collections': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def register_cache(self, cache_name: str, cache: 'ManagedCache') -> None:
        """Зарегистрировать кэш для управления"""
        with self.lock:
            self.caches[cache_name] = cache
            logger.info(f"Зарегистрирован кэш: {cache_name}")
    
    def unregister_cache(self, cache_name: str) -> None:
        """Отменить регистрацию кэша"""
        with self.lock:
            if cache_name in self.caches:
                del self.caches[cache_name]
                logger.info(f"Отменена регистрация кэша: {cache_name}")
    
    def add_weak_ref(self, category: str, obj: Any) -> None:
        """Добавить слабую ссылку на объект"""
        with self.lock:
            self.weak_refs[category].add(obj)
    
    def get_weak_refs_count(self, category: str) -> int:
        """Получить количество живых объектов в категории"""
        with self.lock:
            return len(self.weak_refs[category])
    
    def cleanup_dead_objects(self) -> Dict[str, int]:
        """Очистить мертвые объекты из всех категорий"""
        cleaned_counts = {}
        with self.lock:
            for category, weak_set in self.weak_refs.items():
                initial_count = len(weak_set)
                # Принудительно очищаем мертвые ссылки
                list(weak_set)  # Это заставляет WeakSet очиститься
                final_count = len(weak_set)
                cleaned = initial_count - final_count
                if cleaned > 0:
                    cleaned_counts[category] = cleaned
                    logger.debug(f"Очищено {cleaned} мертвых объектов из категории {category}")
        
        if cleaned_counts:
            logger.info(f"Очистка мертвых объектов завершена: {cleaned_counts}")
        
        return cleaned_counts
    
    def force_garbage_collection(self) -> Dict[str, int]:
        """Принудительная сборка мусора"""
        with self.lock:
            # Выполняем несколько циклов сборки мусора
            collections_before = [gc.get_stats()[i]['collected'] for i in range(3)]
            
            # Принудительная сборка
            gc.collect()
            gc.collect()  # Второй проход для циклических ссылок
            
            collections_after = [gc.get_stats()[i]['collected'] for i in range(3)]
            
            collected = {
                'generation_0': collections_after[0] - collections_before[0],
                'generation_1': collections_after[1] - collections_before[1],
                'generation_2': collections_after[2] - collections_before[2]
            }
            
            self.stats['gc_collections'] += 1
            
            if any(collected.values()):
                logger.info(f"Сборка мусора: {collected}")
            
            return collected
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Получить статистику использования памяти"""
        with self.lock:
            cache_stats = {}
            total_cache_size = 0
            
            for name, cache in self.caches.items():
                cache_stats[name] = cache.get_stats()
                total_cache_size += cache_stats[name].get('total_size', 0)
            
            return {
                'caches': cache_stats,
                'total_cache_size': total_cache_size,
                'weak_refs': {cat: len(refs) for cat, refs in self.weak_refs.items()},
                'manager_stats': self.stats.copy()
            }
    
    def log_memory_stats(self) -> None:
        """Залогировать статистику памяти"""
        stats = self.get_memory_stats()
        logger.info("=== Статистика памяти ===")
        logger.info(f"Общий размер кэшей: {stats['total_cache_size']} байт")
        logger.info(f"GC коллекций: {stats['manager_stats']['gc_collections']}")
        logger.info(f"Кэш хиты: {stats['manager_stats']['cache_hits']}")
        logger.info(f"Кэш промахи: {stats['manager_stats']['cache_misses']}")
        
        for category, count in stats['weak_refs'].items():
            logger.info(f"Слабые ссылки {category}: {count}")

class ManagedCache:
    """Управляемый кэш с контролем размера и временем жизни"""
    
    def __init__(self, 
                 name: str,
                 max_size: int = 1000,
                 ttl_seconds: int = 300,
                 max_memory_mb: int = 50,
                 cleanup_interval: int = 60):
        """
        Args:
            name: Имя кэша
            max_size: Максимальное количество элементов
            ttl_seconds: Время жизни в секундах
            max_memory_mb: Максимальный размер памяти в МБ
            cleanup_interval: Интервал очистки в секундах
        """
        self.name = name
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cleanup_interval = cleanup_interval
        
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self.access_order = []  # Для LRU
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired_removals': 0,
            'manual_cleanups': 0,
            'total_size': 0
        }
        
        # Регистрируем кэш в менеджере памяти
        memory_manager.register_cache(name, self)
        
        # Запускаем периодическую очистку
        self._start_cleanup_timer()
    
    def _start_cleanup_timer(self) -> None:
        """Запустить таймер периодической очистки"""
        if self.cleanup_interval > 0:
            timer = threading.Timer(self.cleanup_interval, self._periodic_cleanup)
            timer.daemon = True
            timer.start()
            memory_manager.cleanup_timers[self.name] = timer
    
    def _periodic_cleanup(self) -> None:
        """Периодическая очистка кэша"""
        try:
            self.cleanup_expired()
            self._trim_to_size_limit()
            self._trim_to_memory_limit()
        except Exception as e:
            logger.error(f"Ошибка при периодической очистке кэша {self.name}: {e}")
        finally:
            # Перезапускаем таймер
            self._start_cleanup_timer()
    
    def _estimate_size(self, data: Any) -> int:
        """Оценить размер данных в байтах"""
        try:
            # Простая оценка размера для разных типов данных
            if isinstance(data, str):
                return len(data.encode('utf-8'))
            elif isinstance(data, (int, float)):
                return 8  # Предполагаем 64-битные числа
            elif isinstance(data, (list, tuple)):
                return sum(self._estimate_size(item) for item in data) + 24  # Накладные расходы
            elif isinstance(data, dict):
                return sum(self._estimate_size(k) + self._estimate_size(v) for k, v in data.items()) + 48
            elif hasattr(data, '__sizeof__'):
                return data.__sizeof__()
            else:
                return 32  # Дефолтный размер для объектов
        except (AttributeError, TypeError):
            return 64
    
    def put(self, key: str, data: Any) -> None:
        """Добавить данные в кэш"""
        with self.lock:
            # Удаляем старую запись если она существует
            if key in self.cache:
                old_entry = self.cache[key]
                self.stats['total_size'] -= old_entry.size_estimate
                del self.cache[key]
            
            # Создаем новую запись
            size_estimate = self._estimate_size(data)
            entry = CacheEntry(
                data=data,
                timestamp=datetime.now(),
                size_estimate=size_estimate
            )
            
            self.cache[key] = entry
            self.stats['total_size'] += size_estimate
            
            # Проверяем лимиты и очищаем при необходимости
            self._trim_to_size_limit()
            self._trim_to_memory_limit()
    
    def get(self, key: str) -> Optional[Any]:
        """Получить данные из кэша"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                
                # Проверяем время жизни
                if datetime.now() - entry.timestamp < self.ttl:
                    entry.access_count += 1
                    self.stats['hits'] += 1
                    
                    # Перемещаем в конец для LRU
                    self.cache.move_to_end(key)
                    
                    # Обновляем статистику менеджера памяти
                    memory_manager.stats['cache_hits'] += 1
                    
                    return entry.data
                else:
                    # Удаляем просроченный элемент
                    self.stats['total_size'] -= entry.size_estimate
                    del self.cache[key]
                    self.stats['expired_removals'] += 1
            
            self.stats['misses'] += 1
            memory_manager.stats['cache_misses'] += 1
            return None
    
    def invalidate(self, key: str) -> None:
        """Удалить конкретный элемент из кэша"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                self.stats['total_size'] -= entry.size_estimate
                del self.cache[key]
    
    def clear(self) -> None:
        """Очистить весь кэш"""
        with self.lock:
            cleared_size = self.stats['total_size']
            self.cache.clear()
            self.stats['total_size'] = 0
            self.stats['manual_cleanups'] += 1
            logger.info(f"Кэш {self.name} очищен. Освобождено {cleared_size} байт")
    
    def cleanup_expired(self) -> int:
        """Удалить просроченные элементы"""
        with self.lock:
            now = datetime.now()
            expired_keys = []
            
            for key, entry in self.cache.items():
                if now - entry.timestamp >= self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                entry = self.cache[key]
                self.stats['total_size'] -= entry.size_estimate
                del self.cache[key]
                self.stats['expired_removals'] += 1
            
            if expired_keys:
                logger.debug(f"Удалено {len(expired_keys)} просроченных элементов из кэша {self.name}")
            
            return len(expired_keys)
    
    def _trim_to_size_limit(self) -> None:
        """Обрезать кэш до лимита по количеству элементов"""
        with self.lock:
            while len(self.cache) > self.max_size:
                # Удаляем наименее используемые элементы
                key, entry = self.cache.popitem(last=False)
                self.stats['total_size'] -= entry.size_estimate
                self.stats['evictions'] += 1
    
    def _trim_to_memory_limit(self) -> None:
        """Обрезать кэш до лимита по памяти"""
        with self.lock:
            while self.stats['total_size'] > self.max_memory_bytes and self.cache:
                key, entry = self.cache.popitem(last=False)
                self.stats['total_size'] -= entry.size_estimate
                self.stats['evictions'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'name': self.name,
                'size': len(self.cache),
                'max_size': self.max_size,
                'total_size_bytes': self.stats['total_size'],
                'total_size_mb': round(self.stats['total_size'] / (1024 * 1024), 2),
                'max_memory_mb': self.max_memory_bytes / (1024 * 1024),
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate': round(hit_rate, 2),
                'evictions': self.stats['evictions'],
                'expired_removals': self.stats['expired_removals'],
                'manual_cleanups': self.stats['manual_cleanups']
            }

# Глобальный экземпляр менеджера памяти
memory_manager = MemoryManager()

# Удобные функции для внешнего использования
def get_memory_stats():
    """Получить статистику памяти"""
    return memory_manager.get_memory_stats()

def log_memory_statistics():
    """Залогировать статистику памяти"""
    memory_manager.log_memory_stats()

def force_cleanup():
    """Принудительная очистка памяти"""
    # Очищаем мертвые объекты
    dead_objects = memory_manager.cleanup_dead_objects()
    
    # Принудительная сборка мусора
    gc_stats = memory_manager.force_garbage_collection()
    
    return {
        'dead_objects_cleaned': dead_objects,
        'garbage_collected': gc_stats
    }

def create_managed_cache(name: str, **kwargs) -> ManagedCache:
    """Создать управляемый кэш"""
    return ManagedCache(name, **kwargs)

# Декоратор для автоматического управления памятью функций
def memory_managed(cleanup_interval: int = 300):
    """Декоратор для функций, требующих управления памятью"""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Периодическая очистка памяти
                if not hasattr(wrapper, '_last_cleanup'):
                    wrapper._last_cleanup = datetime.now()
                
                if (datetime.now() - wrapper._last_cleanup).seconds > cleanup_interval:
                    force_cleanup()
                    wrapper._last_cleanup = datetime.now()
        return wrapper
    return decorator

# Контекстный менеджер для временных данных
class TemporaryDataManager:
    """Менеджер временных данных с автоматической очисткой"""
    
    def __init__(self, category: str = "temporary"):
        self.category = category
        self.objects = set()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
    
    def register_object(self, obj: Any) -> None:
        """Зарегистрировать временный объект"""
        self.objects.add(obj)
        memory_manager.add_weak_ref(self.category, obj)
    
    def cleanup(self) -> None:
        """Очистить временные данные"""
        count = len(self.objects)
        self.objects.clear()
        logger.debug(f"Очищено {count} временных объектов категории {self.category}")

# Автоматическая очистка при завершении программы
import atexit
atexit.register(lambda: memory_manager.force_garbage_collection())


class StockCache:
    """
    Единый класс кэширования остатков с TTL, групповыми операциями и контролем размера.
    Заменяет старые StockCache, OptimizedStockCache и EnhancedStockCache.
    """

    def __init__(self, cache_duration_minutes=5, max_cache_size=10000):
        self.cache = ManagedCache(
            name="stock_cache",
            max_size=max_cache_size,
            ttl_seconds=cache_duration_minutes * 60,
            max_memory_mb=100,
            cleanup_interval=300
        )
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self.lock = threading.RLock()
        self.bulk_cache = ManagedCache(
            name="stock_bulk_cache",
            max_size=1000,
            ttl_seconds=cache_duration_minutes * 60,
            max_memory_mb=50
        )

    def get_cached_quantity(self, barcode: str) -> Optional[int]:
        """Получить кэшированное количество для одного штрихкода"""
        return self.cache.get(barcode)

    def get_cached_quantities(self, barcodes: List[str]) -> Dict[str, int]:
        """Получить кэшированные количества для списка штрихкодов"""
        result = {}
        uncached_barcodes = []

        for barcode in barcodes:
            cached_data = self.cache.get(barcode)
            if cached_data is not None:
                result[barcode] = cached_data
            else:
                uncached_barcodes.append(barcode)

        if uncached_barcodes:
            try:
                from database import get_multiple_stock_cache
                db_results = get_multiple_stock_cache(uncached_barcodes)

                for barcode in uncached_barcodes:
                    if barcode in db_results:
                        quantity = db_results[barcode]
                        result[barcode] = quantity
                        self.cache.put(barcode, quantity)
                    else:
                        result[barcode] = 0
            except Exception as e:
                logger.error(f"Ошибка получения кэша остатков из базы данных: {e}")
                for barcode in uncached_barcodes:
                    result[barcode] = 0

        return result

    def set_cached_quantity(self, barcode: str, quantity: int):
        """Сохранить количество для одного штрихкода"""
        self.cache.put(barcode, quantity)
        try:
            from database import set_stock_cache
            set_stock_cache(barcode, quantity)
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша в базу данных: {e}")

    def set_cached_quantities(self, stock_data: Dict[str, int]):
        """Сохранить количества для нескольких штрихкодов"""
        for barcode, quantity in stock_data.items():
            self.cache.put(barcode, quantity)

        try:
            from database import set_multiple_stock_cache
            set_multiple_stock_cache(stock_data)
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша остатков в базу данных: {e}")

    def invalidate_cache(self):
        """Очистить весь кэш"""
        self.cache.clear()
        self.bulk_cache.clear()
        try:
            from database import clear_stock_cache
            clear_stock_cache()
        except Exception as e:
            logger.error(f"Ошибка очистки кэша остатков в базе данных: {e}")

    def clear_cache_for_barcodes(self, barcodes: List[str]):
        """Очистить кэш для указанных штрихкодов"""
        for barcode in barcodes:
            self.cache.invalidate(barcode)

        zero_data = {barcode: 0 for barcode in barcodes}
        try:
            from database import set_multiple_stock_cache
            set_multiple_stock_cache(zero_data)
        except Exception as e:
            logger.error(f"Ошибка обновления кэша в базе данных при очистке: {e}")

    def get_cache_stats(self):
        """Получить статистику кэша"""
        return {
            'main_cache': self.cache.get_stats(),
            'bulk_cache': self.bulk_cache.get_stats()
        }


# Единый глобальный экземпляр кэша остатков
stock_cache = StockCache()