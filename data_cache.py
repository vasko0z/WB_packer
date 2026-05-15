"""
Модуль для кэширования часто запрашиваемых данных и оптимизации производительности
"""

import time
import logging
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)

class LRUCache:
    """LRU (Least Recently Used) кэш с ограничением по размеру и времени жизни"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        """
        Args:
            max_size: Максимальное количество элементов в кэше
            ttl: Время жизни элементов в секундах
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        with self.lock:
            if key in self.cache:
                item_time, value = self.cache[key]
                # Проверяем время жизни
                if time.time() - item_time < self.ttl:
                    # Перемещаем элемент в конец (помечаем как недавно использованный)
                    self.cache.move_to_end(key)
                    self.hits += 1
                    return value
                else:
                    # Удаляем просроченный элемент
                    del self.cache[key]
                    self.misses += 1
                    return None
            else:
                self.misses += 1
                return None
    
    def put(self, key: str, value: Any) -> None:
        """Добавить значение в кэш"""
        with self.lock:
            # Если ключ уже существует, удаляем его (для перемещения в конец)
            if key in self.cache:
                del self.cache[key]
            # Добавляем новое значение
            self.cache[key] = (time.time(), value)
            # Удаляем самые старые элементы, если превышен размер
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
    
    def invalidate(self, key: str) -> None:
        """Удалить элемент из кэша"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
    
    def clear(self) -> None:
        """Очистить весь кэш"""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': round(hit_rate, 2),
            'ttl': self.ttl
        }

class DataCacheManager:
    """Менеджер кэширования данных приложения. Использует паттерн Singleton."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            # Разные кэши для разных типов данных
            self.user_settings_cache = LRUCache(max_size=100, ttl=600)  # 10 минут
            self.shipment_data_cache = LRUCache(max_size=200, ttl=300)  # 5 минут
            self.moysklad_cache = LRUCache(max_size=500, ttl=1800)     # 30 минут
            self.common_data_cache = LRUCache(max_size=1000, ttl=3600) # 1 час
            self.cache_lock = threading.RLock()
            self.cache_stats = {}
            self._initialized = True
    
    def cache_user_settings(self, username: str, settings: Dict[str, Any]) -> None:
        """Кэшировать настройки пользователя"""
        key = f"user_settings:{username}"
        self.user_settings_cache.put(key, settings)
        logger.debug(f"Кэшированы настройки пользователя: {username}")
    
    def get_user_settings(self, username: str) -> Optional[Dict[str, Any]]:
        """Получить кэшированные настройки пользователя"""
        key = f"user_settings:{username}"
        return self.user_settings_cache.get(key)
    
    def cache_shipment_data(self, shipment_id: str, data: Dict[str, Any]) -> None:
        """Кэшировать данные поставки"""
        key = f"shipment:{shipment_id}"
        self.shipment_data_cache.put(key, data)
        logger.debug(f"Кэшированы данные поставки: {shipment_id}")
    
    def get_shipment_data(self, shipment_id: str) -> Optional[Dict[str, Any]]:
        """Получить кэшированные данные поставки"""
        key = f"shipment:{shipment_id}"
        return self.shipment_data_cache.get(key)
    
    def cache_moysklad_data(self, key_suffix: str, data: Any) -> None:
        """Кэшировать данные из МойСклад"""
        key = f"moysklad:{key_suffix}"
        self.moysklad_cache.put(key, data)
        logger.debug(f"Кэшированы данные МойСклад: {key_suffix}")
    
    def get_moysklad_data(self, key_suffix: str) -> Any:
        """Получить кэшированные данные из МойСклад"""
        key = f"moysklad:{key_suffix}"
        return self.moysklad_cache.get(key)
    
    def cache_common_data(self, key: str, data: Any) -> None:
        """Кэшировать общие данные"""
        self.common_data_cache.put(key, data)
        logger.debug(f"Кэшированы общие данные: {key}")
    
    def get_common_data(self, key: str) -> Any:
        """Получить кэшированные общие данные"""
        return self.common_data_cache.get(key)
    
    def invalidate_user_cache(self, username: str) -> None:
        """Инвалидировать кэш пользователя"""
        key = f"user_settings:{username}"
        self.user_settings_cache.invalidate(key)
        logger.debug(f"Инвалидирован кэш пользователя: {username}")
    
    def invalidate_shipment_cache(self, shipment_id: str) -> None:
        """Инвалидировать кэш поставки"""
        key = f"shipment:{shipment_id}"
        self.shipment_data_cache.invalidate(key)
        logger.debug(f"Инвалидирован кэш поставки: {shipment_id}")
    
    def invalidate_moysklad_cache(self, key_suffix: str = None) -> None:
        """Инвалидировать кэш МойСклад (частично или полностью)"""
        if key_suffix:
            key = f"moysklad:{key_suffix}"
            self.moysklad_cache.invalidate(key)
            logger.debug(f"Инвалидирован кэш МойСклад: {key_suffix}")
        else:
            self.moysklad_cache.clear()
            logger.debug("Полностью очищен кэш МойСклад")
    
    def clear_all_caches(self) -> None:
        """Очистить все кэши"""
        with self.cache_lock:
            self.user_settings_cache.clear()
            self.shipment_data_cache.clear()
            self.moysklad_cache.clear()
            self.common_data_cache.clear()
            logger.info("Все кэши очищены")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Получить статистику всех кэшей"""
        return {
            'user_settings': self.user_settings_cache.get_stats(),
            'shipment_data': self.shipment_data_cache.get_stats(),
            'moysklad': self.moysklad_cache.get_stats(),
            'common_data': self.common_data_cache.get_stats()
        }
    
    def log_cache_stats(self) -> None:
        """Залогировать статистику кэшей"""
        stats = self.get_cache_statistics()
        logger.info("=== Статистика кэшей ===")
        for cache_name, cache_stats in stats.items():
            logger.info(f"{cache_name}: "
                       f"Размер={cache_stats['size']}/{cache_stats['max_size']}, "
                       f"Хиты={cache_stats['hits']}, "
                       f"Промахи={cache_stats['misses']}, "
                       f"Процент попаданий={cache_stats['hit_rate']}%")

# Декоратор для автоматического кэширования функций
def cached(cache_manager: DataCacheManager, cache_type: str = 'common', ttl: int = None):
    """
    Декоратор для кэширования результатов функций
    
    Args:
        cache_manager: Экземпляр DataCacheManager
        cache_type: Тип кэша ('user', 'shipment', 'moysklad', 'common')
        ttl: Время жизни кэша (переопределяет значение по умолчанию)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Создаем ключ кэша из имени функции и аргументов
            cache_key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            
            # Выбираем нужный кэш
            if cache_type == 'user':
                cache = cache_manager.user_settings_cache
            elif cache_type == 'shipment':
                cache = cache_manager.shipment_data_cache
            elif cache_type == 'moysklad':
                cache = cache_manager.moysklad_cache
            else:
                cache = cache_manager.common_data_cache
            
            # Устанавливаем TTL если указан
            if ttl is not None:
                original_ttl = cache.ttl
                cache.ttl = ttl
            
            try:
                # Проверяем кэш
                result = cache.get(cache_key)
                if result is not None:
                    logger.debug(f"Кэш попал для {func.__name__}")
                    return result
                
                # Выполняем функцию и кэшируем результат
                result = func(*args, **kwargs)
                cache.put(cache_key, result)
                logger.debug(f"Результат {func.__name__} закэширован")
                return result
                
            finally:
                # Восстанавливаем оригинальный TTL
                if ttl is not None:
                    cache.ttl = original_ttl
                    
        return wrapper
    return decorator


# Удобные функции для внешнего использования (используют Singleton)
def get_cache_manager():
    """Получить экземпляр DataCacheManager (Singleton)"""
    return DataCacheManager()


def get_cache_stats():
    """Получить статистику всех кэшей"""
    return DataCacheManager().get_cache_statistics()


def log_cache_statistics():
    """Залогировать статистику кэшей"""
    DataCacheManager().log_cache_stats()


def clear_all_caches():
    """Очистить все кэши"""
    DataCacheManager().clear_all_caches()


def invalidate_user_cache(username: str):
    """Инвалидировать кэш пользователя"""
    DataCacheManager().invalidate_user_cache(username)


def invalidate_shipment_cache(shipment_id: str):
    """Инвалидировать кэш поставки"""
    DataCacheManager().invalidate_shipment_cache(shipment_id)


def invalidate_moysklad_cache(key_suffix: str = None):
    """Инвалидировать кэш МойСклад"""
    DataCacheManager().invalidate_moysklad_cache(key_suffix)