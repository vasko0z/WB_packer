"""
Модуль для управления блокировками товаров при одновременной работе нескольких клиентов.
Предотвращает конфликты и потерю прогресса при сканировании одних и тех же товаров.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import threading

logger = logging.getLogger(__name__)


class LockManager:
    """
    Менеджер блокировок товаров.
    Использует паттерн Singleton для обеспечения единственного экземпляра.
    
    Пример использования:
        lock_mgr = LockManager.get_instance()
        
        # Попытка захватить блокировку
        success, lock_info, message = lock_mgr.try_lock(barcode, shipment_id, username)
        if success:
            # Работаем с товаром
            try:
                # ... сканирование ...
            finally:
                # Освобождаем блокировку
                lock_mgr.release(barcode, shipment_id, username)
        else:
            # Товар заблокирован другим пользователем
            show_warning(message)
    """
    
    _instance = None
    _lock = threading.Lock()  # Для потокобезопасного создания экземпляра
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Предотвращаем повторную инициализацию
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        # Локальный кэш активных блокировок (для быстрого доступа)
        self._local_locks: Dict[str, dict] = {}  # key: "{shipment_id}:{barcode}"
        self._locks_lock = threading.RLock()
        
        # Настройки
        self.default_lock_duration = 60  # секунд
        self.auto_cleanup_interval = 300  # секунд (5 минут)
        
        # Таймер для периодической очистки просроченных блокировок
        self._cleanup_timer = None
        
        self._initialized = True
        logger.info("LockManager инициализирован")
    
    @classmethod
    def get_instance(cls) -> 'LockManager':
        """Получить экземпляр LockManager (Singleton)"""
        return cls()
    
    def try_lock(self, barcode: str, shipment_id: int, username: str,
                 lock_duration_sec: int = None) -> Tuple[bool, Optional[dict], str]:
        """
        Пытается захватить блокировку на товар.
        
        Args:
            barcode: штрихкод товара
            shipment_id: ID поставки
            username: имя пользователя
            lock_duration_sec: время блокировки в секундах
        
        Returns:
            tuple: (success, lock_info, message)
        """
        from database import try_lock_item
        
        if lock_duration_sec is None:
            lock_duration_sec = self.default_lock_duration
        
        # Пытаемся захватить блокировку в БД
        success, lock_info, message = try_lock_item(
            barcode, shipment_id, username, lock_duration_sec
        )
        
        if success:
            # Обновляем локальный кэш
            with self._locks_lock:
                key = f"{shipment_id}:{barcode}"
                self._local_locks[key] = {
                    'barcode': barcode,
                    'shipment_id': shipment_id,
                    'username': username,
                    'expires_at': lock_info.get('expires_at') if lock_info else None,
                    'locked_at': datetime.now()
                }
            
            # Логирование отключено - вызывается при каждом сканировании
        else:
            logger.debug(f"Не удалось захватить блокировку: {barcode} - {message}")
        
        return success, lock_info, message
    
    def release(self, barcode: str, shipment_id: int, username: str = None) -> bool:
        """
        Освобождает блокировку товара.
        
        Args:
            barcode: штрихкод товара
            shipment_id: ID поставки
            username: имя пользователя (опционально)
        
        Returns:
            bool: True если успешно
        """
        from database import release_item_lock
        
        # Освобождаем блокировку в БД
        result = release_item_lock(barcode, shipment_id, username)
        
        if result:
            # Удаляем из локального кэша
            with self._locks_lock:
                key = f"{shipment_id}:{barcode}"
                if key in self._local_locks:
                    del self._local_locks[key]
            
            # Логирование отключено - вызывается часто
        
        return result
    
    def release_all_for_user(self, username: str, shipment_id: int = None) -> int:
        """
        Освобождает все блокировки пользователя.
        
        Args:
            username: имя пользователя
            shipment_id: ID поставки (опционально, если None - все поставки)
        
        Returns:
            int: количество освобождённых блокировок
        """
        from database import get_active_locks_for_shipment, release_item_lock
        
        released_count = 0
        
        with self._locks_lock:
            keys_to_remove = []
            
            for key, lock_info in self._local_locks.items():
                if lock_info['username'] != username:
                    continue
                
                if shipment_id is not None and lock_info['shipment_id'] != shipment_id:
                    continue
                
                # Освобождаем блокировку в БД
                if release_item_lock(lock_info['barcode'], lock_info['shipment_id'], username):
                    keys_to_remove.append(key)
                    released_count += 1
            
            # Удаляем из локального кэша
            for key in keys_to_remove:
                del self._local_locks[key]
        
        logger.info(f"Освобождено {released_count} блокировок пользователя {username}")
        return released_count
    
    def is_locked_by_other(self, barcode: str, shipment_id: int, username: str) -> bool:
        """
        Проверяет, заблокирован ли товар другим пользователем.
        
        Args:
            barcode: штрихкод товара
            shipment_id: ID поставки
            username: имя текущего пользователя
        
        Returns:
            bool: True если заблокирован другим
        """
        from database import get_item_lock_info
        
        lock_info = get_item_lock_info(barcode, shipment_id)
        
        if lock_info is None:
            return False
        
        # Проверяем, не истекла ли блокировка
        try:
            expires_at = datetime.fromisoformat(lock_info['expires_at'])
            if datetime.now() > expires_at:
                # Блокировка истекла
                return False
        except (KeyError, ValueError):
            pass
        
        # Заблокировано другим пользователем
        return lock_info['username'] != username
    
    def get_lock_info(self, barcode: str, shipment_id: int) -> Optional[dict]:
        """
        Получает информацию о блокировке товара.
        
        Args:
            barcode: штрихкод товара
            shipment_id: ID поставки
        
        Returns:
            dict или None: информация о блокировке
        """
        from database import get_item_lock_info
        return get_item_lock_info(barcode, shipment_id)
    
    def get_active_locks(self, shipment_id: int, username: str = None) -> List[dict]:
        """
        Получает все активные блокировки для поставки.
        
        Args:
            shipment_id: ID поставки
            username: фильтр по пользователю (опционально)
        
        Returns:
            list: список блокировок
        """
        from database import get_active_locks_for_shipment
        return get_active_locks_for_shipment(shipment_id, username)
    
    def cleanup_expired(self) -> int:
        """
        Удаляет просроченные блокировки из БД и локального кэша.
        
        Returns:
            int: количество удалённых блокировок
        """
        from database import cleanup_expired_locks
        
        # Очищаем в БД
        db_removed = cleanup_expired_locks()
        
        # Очищаем локальный кэш
        with self._locks_lock:
            now = datetime.now()
            keys_to_remove = []
            
            for key, lock_info in self._local_locks.items():
                expires_at_str = lock_info.get('expires_at')
                if expires_at_str:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if now > expires_at:
                            keys_to_remove.append(key)
                    except ValueError:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._local_locks[key]
        
        local_removed = len(keys_to_remove)
        total_removed = db_removed if db_removed >= 0 else local_removed
        
        if total_removed > 0:
            logger.info(f"Очищено {total_removed} просроченных блокировок")
        
        return total_removed
    
    def start_auto_cleanup(self, interval_sec: int = None):
        """
        Запускает автоматическую очистку просроченных блокировок.
        
        Args:
            interval_sec: интервал очистки в секундах
        """
        from PyQt6.QtCore import QTimer
        
        if interval_sec is None:
            interval_sec = self.auto_cleanup_interval
        
        if self._cleanup_timer is not None:
            self._cleanup_timer.stop()
        
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._auto_cleanup_slot)
        self._cleanup_timer.setSingleShot(False)
        self._cleanup_timer.start(interval_sec * 1000)  # конвертируем в миллисекунды
        
        logger.info(f"Запущена автоматическая очистка блокировок (интервал {interval_sec}с)")
    
    def _auto_cleanup_slot(self):
        """Слот для таймера автоматической очистки"""
        try:
            self.cleanup_expired()
        except Exception as e:
            logger.error(f"Ошибка при автоматической очистке блокировок: {e}")
    
    def stop_auto_cleanup(self):
        """Останавливает автоматическую очистку"""
        if self._cleanup_timer is not None:
            self._cleanup_timer.stop()
            self._cleanup_timer = None
            logger.info("Автоматическая очистка блокировок остановлена")
    
    def get_local_locks_count(self) -> int:
        """Получает количество локальных блокировок"""
        with self._locks_lock:
            return len(self._local_locks)
    
    def get_lock_statistics(self) -> dict:
        """Получает статистику блокировок"""
        with self._locks_lock:
            local_count = len(self._local_locks)
            
            # Считаем блокировки по пользователям
            user_stats = {}
            for lock_info in self._local_locks.values():
                username = lock_info.get('username', 'unknown')
                if username not in user_stats:
                    user_stats[username] = 0
                user_stats[username] += 1
            
            return {
                'local_locks_count': local_count,
                'by_user': user_stats
            }


# Глобальные функции для удобства
def get_lock_manager() -> LockManager:
    """Получить экземпляр LockManager"""
    return LockManager.get_instance()


def try_lock_item(barcode: str, shipment_id: int, username: str,
                  duration: int = 60) -> Tuple[bool, Optional[dict], str]:
    """
    Попытаться захватить блокировку на товар.
    Удобная функция для быстрого использования.
    """
    return get_lock_manager().try_lock(barcode, shipment_id, username, duration)


def release_item_lock(barcode: str, shipment_id: int,
                      username: str = None) -> bool:
    """
    Освободить блокировку товара.
    Удобная функция для быстрого использования.
    """
    return get_lock_manager().release(barcode, shipment_id, username)


def is_item_locked_by_other(barcode: str, shipment_id: int,
                            username: str) -> bool:
    """
    Проверить, заблокирован ли товар другим пользователем.
    """
    return get_lock_manager().is_locked_by_other(barcode, shipment_id, username)
