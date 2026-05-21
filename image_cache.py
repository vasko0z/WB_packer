"""
Кэш изображений для оптимизации работы с QPixmap
"""
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QSize
from pathlib import Path
from typing import Dict, Optional, Tuple
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)

_DEFAULT_MAX_CACHE_SIZE = 500  # Максимум элементов в каждом кэше


class ImageCache:
    """LRU-кэш для хранения и повторного использования изображений"""
    
    _instance: Optional['ImageCache'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'ImageCache':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, max_size: int = _DEFAULT_MAX_CACHE_SIZE):
        if not self._initialized:
            self._max_size = max_size
            self._pixmap_cache: OrderedDict[str, QPixmap] = OrderedDict()
            self._icon_cache: OrderedDict[str, QIcon] = OrderedDict()
            self._initialized = True
            logger.debug(f"ImageCache инициализирован (max_size={max_size})")
    
    @classmethod
    def get_instance(cls) -> 'ImageCache':
        """Получить экземпляр кэша"""
        return cls()
    
    def clear(self):
        """Очистить все кэши"""
        self._pixmap_cache.clear()
        self._icon_cache.clear()
        logger.debug("ImageCache очищен")
    
    def _evict_lru(self, cache: OrderedDict, max_size: int) -> None:
        """Удаляет наименее используемые элементы если кэш переполнен"""
        while len(cache) > max_size:
            cache.popitem(last=False)
    
    def get_pixmap(
        self, 
        path: Path, 
        size: Tuple[int, int] = (20, 20),
        keep_aspect_ratio: bool = True,
        smooth_transform: bool = True
    ) -> QPixmap:
        """
        Получить QPixmap из LRU-кэша или загрузить и закэшировать
        """
        cache_key = f"{str(path)}_{size[0]}x{size[1]}_{keep_aspect_ratio}"
        
        # Проверяем кэш (move_to_end для LRU)
        if cache_key in self._pixmap_cache:
            self._pixmap_cache.move_to_end(cache_key)
            return self._pixmap_cache[cache_key]
        
        # Загружаем изображение
        try:
            pixmap = QPixmap(str(path))
            
            if pixmap.isNull():
                logger.warning(f"Не удалось загрузить изображение: {path}")
                empty_pixmap = QPixmap(size[0], size[1])
                empty_pixmap.fill(Qt.GlobalColor.transparent)
                self._pixmap_cache[cache_key] = empty_pixmap
                self._evict_lru(self._pixmap_cache, self._max_size)
                return empty_pixmap
            
            aspect_ratio = Qt.AspectRatioMode.KeepAspectRatio if keep_aspect_ratio else Qt.AspectRatioMode.IgnoreAspectRatio
            transform_mode = Qt.TransformationMode.SmoothTransformation if smooth_transform else Qt.TransformationMode.FastTransformation
            
            scaled_pixmap = pixmap.scaled(size[0], size[1], aspect_ratio, transform_mode)
            
            self._pixmap_cache[cache_key] = scaled_pixmap
            self._evict_lru(self._pixmap_cache, self._max_size)
            
            return scaled_pixmap
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке pixmap {path}: {e}")
            empty_pixmap = QPixmap(size[0], size[1])
            empty_pixmap.fill(Qt.GlobalColor.transparent)
            self._pixmap_cache[cache_key] = empty_pixmap
            self._evict_lru(self._pixmap_cache, self._max_size)
            return empty_pixmap
    
    def get_icon(
        self,
        path: Path,
        size: Tuple[int, int] = (20, 20)
    ) -> QIcon:
        """
        Получить QIcon из LRU-кэша или загрузить и закэшировать
        """
        cache_key = f"{str(path)}_{size[0]}x{size[1]}"
        
        if cache_key in self._icon_cache:
            self._icon_cache.move_to_end(cache_key)
            return self._icon_cache[cache_key]
        
        pixmap = self.get_pixmap(path, size)
        icon = QIcon(pixmap)
        
        self._icon_cache[cache_key] = icon
        self._evict_lru(self._icon_cache, self._max_size)
        
        return icon
    
    def preload_images(self, images: Dict[str, Tuple[Path, Tuple[int, int]]]):
        """
        Предварительно загрузить изображения в кэш
        
        Args:
            images: Словарь {имя: (путь, размер)}
        """
        logger.info(f"Предварительная загрузка {len(images)} изображений")
        for name, (path, size) in images.items():
            self.get_pixmap(path, size)
            logger.debug(f"Загружено: {name}")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Получить статистику кэша"""
        return {
            'pixmaps': len(self._pixmap_cache),
            'icons': len(self._icon_cache),
        }


# Глобальный экземпляр кэша
_image_cache: Optional[ImageCache] = None


def get_image_cache() -> ImageCache:
    """Получить глобальный экземпляр кэша изображений"""
    global _image_cache
    if _image_cache is None:
        _image_cache = ImageCache()
    return _image_cache


def clear_image_cache():
    """Очистить кэш изображений"""
    cache = get_image_cache()
    cache.clear()


def get_cached_pixmap(path: Path, size: Tuple[int, int] = (20, 20)) -> QPixmap:
    """Получить pixmap из кэша"""
    cache = get_image_cache()
    return cache.get_pixmap(path, size)


def get_cached_icon(path: Path, size: Tuple[int, int] = (20, 20)) -> QIcon:
    """Получить иконку из кэша"""
    cache = get_image_cache()
    return cache.get_icon(path, size)
