"""
Модуль для асинхронных операций в приложении WB Packer
"""
import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from typing import Callable, Any

logger = logging.getLogger(__name__)

class Worker(QObject):
    """
    Рабочий класс для выполнения задач в отдельном потоке
    """
    finished = pyqtSignal(object)  # Сигнал завершения с результатом
    error = pyqtSignal(str)        # Сигнал ошибки
    progress = pyqtSignal(int)     # Сигнал прогресса

    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """
        Выполнение функции в отдельном потоке
        """
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Ошибка в асинхронной операции: {e}", exc_info=True)
            self.error.emit(str(e))

class AsyncWorker:
    """
    Класс для выполнения асинхронных операций
    """
    def __init__(self):
        self.thread = None
        self.worker = None

    def execute(self, func: Callable, callback: Callable = None, error_callback: Callable = None, *args, **kwargs):
        """
        Выполнить функцию асинхронно
        
        Args:
            func: Функция для выполнения
            callback: Функция обратного вызова при успешном завершении
            error_callback: Функция обратного вызова при ошибке
            *args: Аргументы для функции
            **kwargs: Именованные аргументы для функции
        """
        # Завершаем предыдущий поток, если он существует
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

        # Создаем новый поток и рабочий объект
        self.thread = QThread()
        self.worker = Worker(func, *args, **kwargs)

        # Переносим рабочий объект в поток
        self.worker.moveToThread(self.thread)

        # Подключаем сигналы
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        
        # Сохраняем обратные вызовы
        self.callback = callback
        self.error_callback = error_callback

        # Запускаем поток
        self.thread.start()

    def _on_finished(self, result):
        """
        Обработка завершения операции
        """
        try:
            if self.callback:
                self.callback(result)
        except Exception as e:
            logger.error(f"Ошибка в callback функции: {e}", exc_info=True)
        
        self._cleanup()

    def _on_error(self, error_msg):
        """
        Обработка ошибки операции
        """
        try:
            if self.error_callback:
                self.error_callback(error_msg)
            else:
                logger.error(f"Асинхронная операция завершена с ошибкой: {error_msg}")
        except Exception as e:
            logger.error(f"Ошибка в error_callback функции: {e}", exc_info=True)
        
        self._cleanup()

    def _cleanup(self):
        """
        Очистка ресурсов
        """
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
        self.worker = None
        self.callback = None
        self.error_callback = None

    def is_running(self) -> bool:
        """
        Проверить, выполняется ли в данный момент асинхронная операция
        """
        return self.thread is not None and self.thread.isRunning()