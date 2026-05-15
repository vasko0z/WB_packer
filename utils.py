# utils.py
import logging
import sys
import random
import winsound
from pathlib import Path
from config import get_resource_path
import threading
import queue
import time

# Глобальная переменная для хранения громкости (0-100)
_sound_volume = 100

# Блокировка для предотвращения одновременного воспроизведения звуков
_volume_lock = threading.Lock()

# Очередь для воспроизведения звуков (предотвращает слияние при быстром сканировании)
_sound_queue = queue.Queue()

# Флаг активности воспроизведения
_sound_playing = False
_sound_thread = None

# Минимальный интервал между звуками (мс) для предотвращения слияния
_MIN_SOUND_INTERVAL = 0.08  # 80 мс

def _sound_worker():
    """
    Рабочий поток для обработки очереди звуков.
    Воспроизводит звуки последовательно, предотвращая слияние.
    """
    global _sound_playing, _sound_thread
    
    logger = logging.getLogger(__name__)
    logger.debug("_sound_worker: поток запущен")
    
    while True:
        try:
            # Получаем задачу из очереди (блокирующе с таймаутом)
            try:
                task = _sound_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            if task is None:  # Сигнал завершения
                logger.debug("_sound_worker: получен сигнал завершения")
                break
            
            sound_path, volume = task
            logger.debug(f"_sound_worker: воспроизведение {sound_path}, громкость {volume}")
            
            # Воспроизводим звук
            _play_sound_with_volume(sound_path, volume)
            
            # Небольшая пауза между звуками для предотвращения слияния
            time.sleep(_MIN_SOUND_INTERVAL)
            
        except Exception as e:
            logger.error(f"_sound_worker: ошибка при воспроизведении: {e}", exc_info=True)
    
    _sound_playing = False
    _sound_thread = None
    logger.debug("_sound_worker: поток завершен")

def _ensure_sound_worker():
    """Убедиться, что рабочий поток запущен"""
    global _sound_playing, _sound_thread
    
    if not _sound_playing or _sound_thread is None or not _sound_thread.is_alive():
        _sound_playing = True
        _sound_thread = threading.Thread(target=_sound_worker, daemon=True)
        _sound_thread.start()

def set_sound_volume(volume):
    """
    Установить громкость звуков (0-100).
    
    Args:
        volume: Громкость от 0 до 100
    """
    global _sound_volume
    _sound_volume = max(0, min(100, volume))

def get_sound_volume():
    """Получить текущую громкость звуков."""
    return _sound_volume

def play_sound(sound_name, tone_sound=False, volume=None):
    """
    Воспроизводит звук через очередь для предотвращения слияния звуков.

    Args:
        sound_name: Имя файла звука (например, "ok.wav")
        tone_sound: Если True, воспроизводится случайный тон из tone1.wav - tone5.wav
                    вместо sound_name
        volume: Громкость от 0 до 100. Если None, используется глобальная настройка.
                Если 0, звук не воспроизводится.
    """
    logger = logging.getLogger(__name__)

    if sys.platform != "win32":
        logger.warning(f"play_sound: платформа не win32 ({sys.platform})")
        return

    # Используем переданную громкость или глобальную настройку
    if volume is None:
        volume = _sound_volume

    logger.debug(f"play_sound: sound_name={sound_name}, tone_sound={tone_sound}, volume={volume}, _sound_volume={_sound_volume}")

    # Если громкость нулевая, не воспроизводим звук
    if volume <= 0:
        logger.debug(f"play_sound: громкость {volume}, звук не воспроизводится")
        return

    # Если включен режим тонового звука и запрошен ok.wav, выбираем случайный тон
    if tone_sound and sound_name == "ok.wav":
        tone_number = random.randint(1, 5)
        sound_name = f"tone{tone_number}.wav"
        logger.debug(f"play_sound: выбран случайный тон {sound_name}")

    sound_path = get_resource_path(Path("Res") / "Sound" / sound_name)
    logger.debug(f"play_sound: полный путь к звуку: {sound_path}, существует: {sound_path.exists()}")

    if sound_path.exists():
        try:
            # Запускаем рабочий поток если нужно
            _ensure_sound_worker()
            
            # Добавляем звук в очередь для последовательного воспроизведения
            logger.debug(f"play_sound: добавление звука в очередь")
            _sound_queue.put((str(sound_path), volume))
            logger.debug(f"play_sound: звук добавлен в очередь")
        except Exception as e:
            logger.error(f"Не удалось добавить звук в очередь {sound_name}: {e}", exc_info=True)
            # Пробуем обычное воспроизведение при ошибке
            try:
                logger.debug(f"play_sound: пробуем обычное воспроизведение winsound")
                winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e2:
                logger.error(f"play_sound: обычное воспроизведение тоже не удалось: {e2}")
    else:
        logger.error(f"Файл звука не найден: {sound_path}")

def _play_sound_with_volume(sound_path, volume):
    """
    Воспроизводит звук с указанной громкостью (0-100).
    Использует Windows API для временного изменения громкости.
    Воспроизведение происходит асинхронно в отдельном потоке.
    """
    logger = logging.getLogger(__name__)
    import ctypes
    import time

    logger.debug(f"_play_sound_with_volume: sound_path={sound_path}, volume={volume}")

    # Запускаем воспроизведение в отдельном потоке для неблокирующего выполнения
    def _play_in_thread():
        with _volume_lock:
            # Загружаем библиотеку Windows
            dll = ctypes.windll.winmm

            # Получаем текущую громкость волнового выхода для восстановления
            vol = ctypes.c_uint()
            result = dll.waveOutGetVolume(None, ctypes.byref(vol))

            logger.debug(f"_play_sound_with_volume (thread): waveOutGetVolume result={result}, vol.value={vol.value}")

            if result != 0:
                # Если не удалось получить громкость, используем обычное воспроизведение
                logger.warning(f"_play_sound_with_volume (thread): waveOutGetVolume вернул ошибку {result}, используем winsound")
                winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return

            original_vol = vol.value

            # Максимальная громкость (0xFFFF для каждого канала)
            MAX_VOLUME = 0xFFFF

            # Вычисляем новую громкость с учётом процента от максимума
            new_vol_level = int(MAX_VOLUME * (volume / 100))

            # Устанавливаем новую громкость (оба канала одинаково)
            new_vol = (new_vol_level << 16) | new_vol_level
            logger.debug(f"_play_sound_with_volume (thread): устанавливаем громкость new_vol={new_vol} ({volume}%)")
            dll.waveOutSetVolume(None, new_vol)

            try:
                # Воспроизводим звук асинхронно (не блокируем поток)
                logger.debug(f"_play_sound_with_volume (thread): вызываем winsound.PlaySound SND_ASYNC")
                winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                logger.debug(f"_play_sound_with_volume (thread): звук запущен асинхронно")
            finally:
                # Ждем немного перед восстановлением громкости (примерная длительность короткого звука)
                time.sleep(0.15)
                # Всегда восстанавливаем исходную громкость
                logger.debug(f"_play_sound_with_volume (thread): восстанавливаем громкость original_vol={original_vol}")
                dll.waveOutSetVolume(None, original_vol)

    # Запускаем в отдельном потоке
    thread = threading.Thread(target=_play_in_thread, daemon=True)
    thread.start()

def get_local_user_file():
    documents = Path.home() / "Documents"
    documents.mkdir(exist_ok=True)
    return documents / "current_user.txt"

def save_local_user(username):
    try:
        with open(get_local_user_file(), "w", encoding="utf-8") as f:
            f.write(username)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Не удалось сохранить локального пользователя: {e}")

def load_local_user():
    try:
        user_file = get_local_user_file()
        if user_file.exists():
            with open(user_file, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Не удалось загрузить локального пользователя: {e}")
    return None