"""
Модуль для асинхронных операций в приложении WB Packer
"""
import logging
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

class AsyncOperationWorker(QObject):
    """
    Рабочий класс для выполнения асинхронных операций
    """
    finished = pyqtSignal(object)      # Сигнал завершения с результатом
    error = pyqtSignal(str)            # Сигнал ошибки
    progress = pyqtSignal(int)         # Сигнал прогресса

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


class AsyncOperationsManager:
    """
    Менеджер для выполнения асинхронных операций
    """
    def __init__(self):
        self.active_threads = []  # Список активных потоков
        logger.info("Инициализация AsyncOperationsManager")

    def execute_async(self, func: Callable, callback: Optional[Callable] = None,
                      error_callback: Optional[Callable] = None,
                      progress_callback: Optional[Callable] = None,
                      *args, **kwargs):
        """
        Выполнить функцию асинхронно
        
        Args:
            func: Функция для выполнения
            callback: Функция обратного вызова при успешном завершении
            error_callback: Функция обратного вызова при ошибке
            progress_callback: Функция обратного вызова для отслеживания прогресса
            *args: Аргументы для функции
            **kwargs: Именованные аргументы для функции
        """
        # Создаем новый поток и рабочий объект
        thread = QThread()
        worker = AsyncOperationWorker(func, *args, **kwargs)

        # Сохраняем ссылки на поток и воркер для управления
        self.active_threads.append((thread, worker))

        # Переносим рабочий объект в поток
        worker.moveToThread(thread)

        # Подключаем сигналы
        thread.started.connect(worker.run)
        worker.finished.connect(lambda result: self._on_finished(result, callback, thread, worker))
        worker.error.connect(lambda error_msg: self._on_error(error_msg, error_callback, thread, worker))
        
        if progress_callback:
            worker.progress.connect(progress_callback)

        # Запускаем поток
        thread.start()
        
    def execute_batch_operations(self, operations: list, batch_callback: Optional[Callable] = None,
                                 error_callback: Optional[Callable] = None,
                                 progress_callback: Optional[Callable] = None):
        """
        Выполнить несколько операций асинхронно в пакетном режиме
        
        Args:
            operations: Список кортежей (func, args, kwargs) для выполнения
            batch_callback: Функция обратного вызова при успешном завершении всех операций
            error_callback: Функция обратного вызова при ошибке
            progress_callback: Функция обратного вызова для отслеживания прогресса (получает процент выполнения)
        """
        def batch_operation():
            results = []
            for i, (func, args, kwargs) in enumerate(operations):
                try:
                    result = func(*args, **kwargs)
                    results.append(result)
                    
                    # Отправляем прогресс, если предоставлен обратный вызов
                    if progress_callback:
                        progress = int(((i + 1) / len(operations)) * 100)
                        progress_callback(progress)
                except Exception as e:
                    logger.error(f"Ошибка в пакетной операции {i}: {e}", exc_info=True)
                    raise e
            return results

        # Выполняем пакетную операцию асинхронно
        self.execute_async(batch_operation, batch_callback, error_callback)

    def _on_finished(self, result, callback, thread, worker):
        """
        Обработка завершения операции
        Гарантированная очистка ресурсов даже при ошибке в callback
        """
        try:
            if callback:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Ошибка в callback функции: {e}", exc_info=True)
        finally:
            # Гарантированная очистка ресурсов
            self._cleanup_thread(thread, worker)

    def _on_error(self, error_msg, error_callback, thread, worker):
        """
        Обработка ошибки операции
        Гарантированная очистка ресурсов даже при ошибке в error_callback
        """
        try:
            if error_callback:
                try:
                    error_callback(error_msg)
                except Exception as e:
                    logger.error(f"Ошибка в error_callback функции: {e}", exc_info=True)
            else:
                logger.error(f"Асинхронная операция завершена с ошибкой: {error_msg}")
        finally:
            # Гарантированная очистка ресурсов
            self._cleanup_thread(thread, worker)

    def _cleanup_thread(self, thread, worker):
        """
        Очистка ресурсов потока
        Безопасное удаление потока из списка и завершение работы
        """
        try:
            # Отключаем сигналы для предотвращения повторных вызовов
            try:
                # Отключаем все подключения от worker
                for signal in [worker.finished, worker.error, worker.progress]:
                    try:
                        signal.disconnect()
                    except (TypeError, RuntimeError):
                        # Сигналы могли быть уже отключены или не подключены
                        pass
            except Exception:
                pass

            # Удаляем поток из списка активных (безопасная проверка)
            try:
                thread_worker_pair = (thread, worker)
                if thread_worker_pair in self.active_threads:
                    self.active_threads.remove(thread_worker_pair)
            except (ValueError, KeyError):
                # Элемент мог быть уже удален
                pass

            # Завершаем поток
            try:
                if thread.isRunning():
                    thread.quit()
                    # Ждем завершения потока с таймаутом (3 секунды)
                    if not thread.wait(3000):
                        logger.warning(f"Поток не завершился за 3 секунды, принудительное завершение")
            except RuntimeError:
                # Поток мог быть уже завершен
                pass
                
        except Exception as e:
            logger.error(f"Ошибка при очистке потока: {e}", exc_info=True)
        finally:
            # Очищаем worker для предотвращения утечек памяти
            try:
                worker.deleteLater()
            except Exception:
                pass

    def cancel_all_operations(self):
        """
        Отменить все активные асинхронные операции
        """
        for thread, worker in self.active_threads[:]:  # Создаем копию списка для безопасного удаления
            try:
                thread.quit()
                thread.wait(3000)  # Таймаут 3 секунды чтобы не блокировать закрытие
            except Exception as e:
                logger.error(f"Ошибка при завершении потока: {e}", exc_info=True)
        
        self.active_threads.clear()

    def is_any_operation_running(self) -> bool:
        """
        Проверить, выполняется ли в данный момент какая-либо асинхронная операция
        """
        return len(self.active_threads) > 0

    def get_active_operations_count(self) -> int:
        """
        Получить количество активных асинхронных операций
        """
        return len(self.active_threads)