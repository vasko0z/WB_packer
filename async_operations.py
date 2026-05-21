"""
Модуль для асинхронных операций в приложении WB Packer
Использует QThreadPool для переиспользования потоков
"""
import logging
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class _WorkerSignals(QObject):
    """Сигналы для QRunnable worker"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)


class _AsyncWorker(QRunnable):
    """
    Worker для выполнения функции в пуле потоков
    """
    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = _WorkerSignals()
        # Позволяет автоудаление после завершения
        self.setAutoDelete(True)

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            logger.error(f"Ошибка в асинхронной операции: {e}", exc_info=True)
            self.signals.error.emit(str(e))


class AsyncOperationsManager:
    """
    Менеджер асинхронных операций на базе QThreadPool
    """
    def __init__(self, max_threads: int = 4):
        self._thread_pool = QThreadPool.globalInstance()
        self._thread_pool.setMaxThreadCount(max_threads)
        self._active_count = 0
        logger.info(f"Инициализация AsyncOperationsManager (max_threads={max_threads})")

    def execute_async(self, func: Callable, callback: Optional[Callable] = None,
                      error_callback: Optional[Callable] = None,
                      progress_callback: Optional[Callable] = None,
                      *args, **kwargs):
        """
        Выполнить функцию асинхронно через пул потоков
        """
        worker = _AsyncWorker(func, *args, **kwargs)
        self._active_count += 1

        worker.signals.finished.connect(
            lambda result: self._on_finished(result, callback)
        )
        worker.signals.finished.connect(
            lambda result: self._decrement_active()
        )
        worker.signals.error.connect(
            lambda error_msg: self._on_error(error_msg, error_callback)
        )
        worker.signals.error.connect(
            lambda error_msg: self._decrement_active()
        )

        if progress_callback:
            worker.signals.progress.connect(progress_callback)

        self._thread_pool.start(worker)

    def execute_batch_operations(self, operations: list, batch_callback: Optional[Callable] = None,
                                 error_callback: Optional[Callable] = None,
                                 progress_callback: Optional[Callable] = None):
        """
        Выполнить несколько операций асинхронно в пакетном режиме
        """
        def batch_operation():
            results = []
            for i, (func, args, kwargs) in enumerate(operations):
                try:
                    result = func(*args, **kwargs)
                    results.append(result)
                    if progress_callback:
                        progress = int(((i + 1) / len(operations)) * 100)
                        progress_callback(progress)
                except Exception as e:
                    logger.error(f"Ошибка в пакетной операции {i}: {e}", exc_info=True)
                    raise e
            return results

        self.execute_async(batch_operation, batch_callback, error_callback)

    def _on_finished(self, result, callback):
        try:
            if callback:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Ошибка в callback функции: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Ошибка в _on_finished: {e}", exc_info=True)

    def _on_error(self, error_msg, error_callback):
        try:
            if error_callback:
                try:
                    error_callback(error_msg)
                except Exception as e:
                    logger.error(f"Ошибка в error_callback функции: {e}", exc_info=True)
            else:
                logger.error(f"Асинхронная операция завершена с ошибкой: {error_msg}")
        except Exception as e:
            logger.error(f"Ошибка в _on_error: {e}", exc_info=True)

    def _decrement_active(self):
        self._active_count = max(0, self._active_count - 1)

    def cancel_all_operations(self):
        """
        Отменить все активные операции (ожидает завершения текущих)
        """
        self._thread_pool.clear()
        self._thread_pool.waitForDone()
        self._active_count = 0

    def is_any_operation_running(self) -> bool:
        return self._active_count > 0

    def get_active_operations_count(self) -> int:
        return self._active_count
