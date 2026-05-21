"""
Модуль для работы с API МойСклад
"""
import requests
import threading
import json
from typing import Any, Dict, List, Optional, Union, Tuple
import logging
import time
from functools import wraps
import random
from moysklad_logger import get_moysklad_logger

logger = logging.getLogger(__name__)
moysklad_logger = get_moysklad_logger()


class MoyskladAPIError(Exception):
    """Базовый класс для ошибок Moysklad API"""
    pass


class MoyskladTimeoutError(MoyskladAPIError):
    """Ошибка таймаута"""
    pass


class MoyskladRetryError(MoyskladAPIError):
    """Ошибка после всех попыток повтора"""
    pass


class MoyskladRateLimitError(MoyskladAPIError):
    """Ошибка ограничения частоты запросов"""
    pass


class RateLimiter:
    """Rate limiter для соблюдения лимитов API МойСклад"""
    
    def __init__(self):
        self.max_requests_per_3sec = 45
        self.max_parallel_requests = 5
        self.request_timestamps = []
        self._lock = threading.Lock()
    
    def wait_if_needed(self):
        """Ждать если достигнут лимит запросов"""
        with self._lock:
            now = time.time()
            # Удаляем запросы старше 3 секунд
            self.request_timestamps = [ts for ts in self.request_timestamps if now - ts < 3]
            
            # Если достигнут лимит 45 запросов за 3 секунды
            if len(self.request_timestamps) >= self.max_requests_per_3sec:
                oldest = self.request_timestamps[0]
                wait_time = 3 - (now - oldest) + 0.1
                if wait_time > 0:
                    logger.warning(f"Достигнут лимит {self.max_requests_per_3sec} запросов за 3 сек. Ожидание {wait_time:.2f} сек")
                    time.sleep(wait_time)
            
            self.request_timestamps.append(time.time())
    
    def record_request(self):
        """Записать запрос в историю"""
        with self._lock:
            now = time.time()
            self.request_timestamps = [ts for ts in self.request_timestamps if now - ts < 3]
            self.request_timestamps.append(now)


class CircuitBreakerError(MoyskladAPIError):
    """Ошибка при размыкании circuit breaker"""
    pass


def retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0, 
                      exceptions=(requests.exceptions.RequestException,)):
    """
    Декоратор для повторных попыток с экспоненциальной задержкой
    
    Args:
        max_retries: Максимальное количество попыток
        base_delay: Базовая задержка в секундах
        max_delay: Максимальная задержка в секундах
        exceptions: Кортеж исключений для повтора
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # Экспоненциальная задержка с jitter
                        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                        logger.warning(f"Попытка {attempt + 1} провалилась: {str(e)}. Повтор через {delay:.2f} секунд")
                        time.sleep(delay)
                    else:
                        logger.error(f"Все {max_retries + 1} попыток провалились. Последняя ошибка: {str(e)}")
                        raise MoyskladRetryError(f"После {max_retries + 1} попыток: {str(e)}") from e
            
            # Этот код никогда не будет достигнут, но добавлен для ясности
            raise last_exception
        return wrapper
    return decorator

class MoyskladAPI:
    """
    Класс для работы с API МойСклад
    """
    
    def __init__(self, token: str, timeout: float = 30.0, max_retries: int = 3):
        """
        Инициализация API
        
        Args:
            token: Токен доступа к API МойСклад
            timeout: Таймаут для запросов в секундах (по умолчанию 30 секунд)
            max_retries: Максимальное количество повторных попыток (по умолчанию 3)
        """
        self.token = token
        self.base_url = "https://api.moysklad.ru/api/remap/1.2"
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json;charset=utf-8",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip"
        }
        
        # Настройки для обработки больших объемов данных
        self.batch_size = 50  # Размер пакета для массовых операций
        self.rate_limit_delay = 0.1  # Задержка между запросами для соблюдения лимитов
        
        # Rate limiter для соблюдения лимитов API
        self.rate_limiter = RateLimiter()
        
        # Статистика для мониторинга
        self.stats = {
            'requests_count': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retry_count': 0,
            'rate_limit_hits': 0,
            'total_time': 0.0
        }
        
        # Circuit breaker параметры для защиты от каскадных сбоев
        self.circuit_breaker_failures_threshold = 5  # Количество ошибок для размыкания
        self.circuit_breaker_timeout = 60  # Время ожидания в секундах
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure_time = None
        self.circuit_breaker_state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        
        # Время последнего запроса для отладки
        self._last_request_time = None

    def _check_circuit_breaker(self):
        """Проверка состояния circuit breaker"""
        if self.circuit_breaker_state == 'OPEN':
            # Проверяем, не истекло ли время ожидания
            if self.circuit_breaker_last_failure_time:
                elapsed = time.time() - self.circuit_breaker_last_failure_time
                if elapsed >= self.circuit_breaker_timeout:
                    # Переводим в полуоткрытое состояние для проверки
                    self.circuit_breaker_state = 'HALF_OPEN'
                    logger.info("Circuit breaker переведен в HALF_OPEN состояние для проверки")
                    return True
            return False
        return True

    def _record_success(self):
        """Запись успешного запроса в circuit breaker"""
        if self.circuit_breaker_state == 'HALF_OPEN':
            self.circuit_breaker_state = 'CLOSED'
            self.circuit_breaker_failures = 0
            logger.info("Circuit breaker переведен в CLOSED состояние после успешного запроса")
        elif self.circuit_breaker_state == 'CLOSED':
            # Сбрасываем счетчик ошибок при успешном запросе
            self.circuit_breaker_failures = max(0, self.circuit_breaker_failures - 1)

    def _record_failure(self):
        """Запись ошибки в circuit breaker"""
        self.circuit_breaker_failures += 1
        self.circuit_breaker_last_failure_time = time.time()
        
        if self.circuit_breaker_state == 'HALF_OPEN':
            self.circuit_breaker_state = 'OPEN'
            logger.warning(f"Circuit breaker переведен в OPEN состояние после ошибки в HALF_OPEN")
        elif self.circuit_breaker_state == 'CLOSED':
            if self.circuit_breaker_failures >= self.circuit_breaker_failures_threshold:
                self.circuit_breaker_state = 'OPEN'
                logger.warning(f"Circuit breaker переведен в OPEN состояние после {self.circuit_breaker_failures} ошибок")

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0, 
                       exceptions=(MoyskladRateLimitError, requests.exceptions.RequestException))
    def _make_request(self, method, url, **kwargs):
        """
        Внутренний метод для выполнения HTTP-запросов с логированием, таймаутами и повторными попытками
        """
        # Проверяем circuit breaker
        if not self._check_circuit_breaker():
            raise CircuitBreakerError(
                f"Circuit breaker в OPEN состоянии. Повторите через {self.circuit_breaker_timeout} секунд"
            )
        
        start_time = time.time()
        self.stats['requests_count'] += 1
        
        # Используем rate limiter для соблюдения лимитов
        self.rate_limiter.wait_if_needed()
        
        # Добавляем таймауты если они не указаны
        if 'timeout' not in kwargs:
            kwargs['timeout'] = (self.timeout, self.timeout)  # (connect_timeout, read_timeout)
        
        logger.debug(f"Выполняем {method.upper()} запрос: {url}")
        if 'params' in kwargs:
            # Логируем только общую информацию о запросе, не выводя длинные списки идентификаторов
            params = kwargs['params']
            if 'filter' in params and ('product.id=' in str(params['filter']) or 'assortmentId=' in str(params['filter'])):
                # Если в фильтре есть идентификаторы продуктов, логируем только количество
                filter_str = str(params['filter'])
                product_ids_count = filter_str.count('product.id=') + filter_str.count('assortmentId=') if isinstance(filter_str, str) else 0
                logger.debug(f"Параметры запроса: filter содержит {product_ids_count} идентификаторов продуктов")
            else:
                logger.debug(f"Параметры запроса: {params}")
        
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            self._last_request_time = time.time()

            # Обновляем статистику
            request_time = time.time() - start_time
            self.stats['total_time'] += request_time
            
            # Записываем успех в circuit breaker
            self._record_success()

            logger.debug(f"Ответ сервера: {response.status_code} (время: {request_time:.2f}s)")
            logger.debug(f"Длина тела ответа: {len(response.text)} символов")

            # Проверка на rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 3))
                self.stats['rate_limit_hits'] += 1
                logger.warning(f"Достигнут лимит запросов (429). Повтор через {retry_after} секунд")
                time.sleep(retry_after)
                # Повторяем запрос - декоратор @retry_with_backoff перехватит исключение
                raise MoyskladRateLimitError(f"Превышен лимит запросов (429), повтор через {retry_after} сек")

            # Проверка на ошибку авторизации
            if response.status_code == 401:
                self.stats['failed_requests'] += 1
                logger.error("Ошибка авторизации 401: проверьте токен МойСклад")
                self._record_failure()
                raise MoyskladAPIError("Ошибка авторизации 401: проверьте токен МойСклад")

            # Проверка на ошибки сервера
            if response.status_code >= 500:
                self.stats['failed_requests'] += 1
                logger.warning(f"Сервер вернул ошибку {response.status_code}: {response.text}")
                self._record_failure()
                raise requests.exceptions.HTTPError(f"Серверная ошибка {response.status_code}")

            # Успешный запрос
            self.stats['successful_requests'] += 1
            return response

        except requests.exceptions.Timeout as e:
            self.stats['failed_requests'] += 1
            logger.error(f"Таймаут запроса ({self.timeout} секунд) для {url}: {str(e)}")
            self._record_failure()
            raise MoyskladTimeoutError(f"Таймаут запроса: {str(e)}") from e

        except requests.exceptions.ConnectionError as e:
            self.stats['failed_requests'] += 1
            logger.error(f"Ошибка подключения к {url}: {str(e)}")
            self._record_failure()
            raise

        except requests.exceptions.RequestException as e:
            self.stats['failed_requests'] += 1
            logger.error(f"Ошибка запроса к {url}: {str(e)}")
            self._record_failure()
            raise

        except Exception as e:
            self.stats['failed_requests'] += 1
            logger.error(f"Неизвестная ошибка при запросе к {url}: {str(e)}")
            self._record_failure()
            raise
    
    def get_stats(self) -> Dict[str, Union[int, float]]:
        """
        Получить статистику использования API
        
        Returns:
            Словарь со статистикой запросов
        """
        stats_copy = self.stats.copy()
        if stats_copy['requests_count'] > 0:
            stats_copy['success_rate'] = stats_copy['successful_requests'] / stats_copy['requests_count'] * 100
            stats_copy['avg_response_time'] = stats_copy['total_time'] / stats_copy['requests_count']
        else:
            stats_copy['success_rate'] = 0.0
            stats_copy['avg_response_time'] = 0.0
        
        return stats_copy
    
    def reset_stats(self):
        """
        Сбросить статистику
        """
        self.stats = {
            'requests_count': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retry_count': 0,
            'rate_limit_hits': 0,
            'total_time': 0.0
        }
        
    def get_circuit_breaker_state(self) -> Dict[str, Any]:
        """
        Получить состояние circuit breaker
        
        Returns:
            Словарь с состоянием circuit breaker
        """
        return {
            'state': self.circuit_breaker_state,
            'failures': self.circuit_breaker_failures,
            'threshold': self.circuit_breaker_failures_threshold,
            'timeout': self.circuit_breaker_timeout,
            'last_failure_time': self.circuit_breaker_last_failure_time
        }

    def reset_circuit_breaker(self):
        """
        Сбросить circuit breaker в случае необходимости
        """
        self.circuit_breaker_state = 'CLOSED'
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure_time = None
        logger.info("Circuit breaker сброшен вручную")
    
    def _batch_process_barcodes(self, barcodes: List[str], processor_func, *args, **kwargs) -> List[Dict]:
        """
        Обработка большого количества штрихкодов пакетами
        
        Args:
            barcodes: Список штрихкодов
            processor_func: Функция для обработки пакета
            *args, **kwargs: Аргументы для processor_func
            
        Returns:
            Список результатов
        """
        results = []
        total_batches = (len(barcodes) + self.batch_size - 1) // self.batch_size
        
        logger.info(f"Начинаем обработку {len(barcodes)} штрихкодов пакетами по {self.batch_size}")
        
        for i in range(0, len(barcodes), self.batch_size):
            batch = barcodes[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            
            logger.info(f"Обработка пакета {batch_num}/{total_batches} ({len(batch)} штрихкодов)")
            
            try:
                batch_result = processor_func(batch, *args, **kwargs)
                results.extend(batch_result)
                
                # Задержка между пакетами для соблюдения rate limiting
                if i + self.batch_size < len(barcodes):
                    time.sleep(self.rate_limit_delay * 2)  # Удвоенная задержка между пакетами
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке пакета {batch_num}: {str(e)}")
                # Продолжаем обработку следующих пакетов
                continue
        
        logger.info(f"Обработка завершена. Обработано {len(results)} элементов из {len(barcodes)} штрихкодов")
        return results
    
    def _chunk_list(self, lst: List, chunk_size: int) -> List[List]:
        """
        Разделить список на чанки заданного размера
        
        Args:
            lst: Исходный список
            chunk_size: Размер чанка
            
        Returns:
            Список чанков
        """
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
    
    def get_stores(self) -> List[Dict]:
        """
        Получить список складов
        
        Returns:
            Список складов
        """
        try:
            # Пробуем получить список складов по основному эндпоинту
            url = f"{self.base_url}/entity/store"
            params = {
                'limit': 1000  # Увеличиваем лимит, чтобы получить все склады
            }
            
            # Делаем запрос с обработкой возможных ошибок
            response = self._make_request('GET', url, params=params)
            
            # Обрабатываем результат в зависимости от статуса ответа
            if response.status_code == 200:
                # Успешный запрос, обрабатываем данные
                data = response.json()
                stores = []
                
                # Проверяем структуру ответа
                if 'rows' in data:
                    # Стандартная структура с rows
                    for store in data['rows']:
                        stores.append({
                            'id': store.get('id'),
                            'name': store.get('name', ''),
                            'externalCode': store.get('externalCode', ''),
                            'archived': store.get('archived', False)
                        })
                elif isinstance(data, list):
                    # Прямой массив складов
                    for store in data:
                        stores.append({
                            'id': store.get('id'),
                            'name': store.get('name', ''),
                            'externalCode': store.get('externalCode', ''),
                            'archived': store.get('archived', False)
                        })
                elif 'meta' in data and 'rows' in data:
                    # Структура с метаинформацией
                    for store in data['rows']:
                        stores.append({
                            'id': store.get('id'),
                            'name': store.get('name', ''),
                            'externalCode': store.get('externalCode', ''),
                            'archived': store.get('archived', False)
                        })
                else:
                    # Если структура неизвестная, логируем и возвращаем пустой список
                    logger.info(f"Склады не найдены или структура ответа неизвестна: {data}")
                    return []
                
                return stores
            elif response.status_code == 400:
                logger.warning(f"Ошибка 400 при получении списка складов: неверный запрос. Пробуем без параметров. Ответ: {response.text}")
                # Пробуем запрос без параметров
                response = self._make_request('GET', url)
                response.raise_for_status()
                
                data = response.json()
                stores = []
                
                if 'rows' in data:
                    for store in data['rows']:
                        stores.append({
                            'id': store.get('id'),
                            'name': store.get('name', ''),
                            'externalCode': store.get('externalCode', ''),
                            'archived': store.get('archived', False)
                        })
                
                return stores
            elif response.status_code == 401:
                logger.error(f"Ошибка 401 при получении списка складов: неавторизованный доступ. Проверьте токен.")
                raise Exception("Неавторизованный доступ. Проверьте токен доступа к МойСклад.")
            elif response.status_code == 403:
                logger.error(f"Ошибка 403 при получении списка складов: доступ запрещен.")
                raise Exception("Доступ к списку складов запрещен. Проверьте права доступа в МойСклад.")
            elif response.status_code == 404:
                logger.info(f"Эндпоинт для получения складов не найден. Пробуем альтернативный метод через отчеты...")
                
                # Пробуем получить информацию через отчеты остатков по складам
                report_url = f"{self.base_url}/report/stock/bystore/current"
                report_response = self._make_request('GET', report_url, params={'limit': 1})
                
                if report_response.status_code == 200:
                    report_data = report_response.json()
                    stores = []
                    
                    if 'rows' in report_data:
                        for row in report_data['rows']:
                            if 'stockByStore' in row:
                                for store_info in row['stockByStore']:
                                    store_meta = store_info.get('meta', {})
                                    if store_meta:
                                        # Извлекаем ID склада из href
                                        store_href = store_meta.get('href', '')
                                        if store_href:
                                            store_id = store_href.split('/')[-1]
                                            store_name = store_info.get('name', f"Склад {store_id}")
                                            
                                            # Проверяем, не добавлен ли уже такой склад
                                            if not any(s['id'] == store_id for s in stores):
                                                stores.append({
                                                    'id': store_id,
                                                    'name': store_name,
                                                    'externalCode': '',
                                                    'archived': False
                                                })
                    
                    return stores
                else:
                    logger.error(f"Ошибка при получении складов через отчеты: {report_response.status_code} - {report_response.text}")
                    raise Exception(f"Не удалось получить список складов через отчеты: {report_response.status_code}")
            else:
                response.raise_for_status()
                
        except requests.exceptions.HTTPError as e:
            status_code = response.status_code if 'response' in locals() else "unknown"
            response_text = response.text if 'response' in locals() else "unknown response"
            logger.error(f"HTTP ошибка {status_code} при получении списка складов: {e}. Ответ: {response_text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении списка складов: {e}")
            raise
        except Exception as e:
            logger.error(f"Неизвестная ошибка при получении списка складов: {e}")
            raise
    
    def get_stock_by_stores(self, barcodes: List[str], store_ids: List[str] = None) -> Dict[str, Dict[str, int]]:
        """
        Получить остатки по складам для указанных штрихкодов

        Args:
            barcodes: Список штрихкодов для проверки
            store_ids: Список ID складов для фильтрации (если None, используются все склады)

        Returns:
            Словарь с остатками по складам {'barcode': {'store_name': quantity}}
            
        Raises:
            ValueError: Если barcodes пуст или не является списком
        """
        # Валидация входных параметров
        if not barcodes:
            raise ValueError("Параметр 'barcodes' не может быть пустым")
        
        if not isinstance(barcodes, list):
            raise ValueError(f"Параметр 'barcodes' должен быть списком, получено: {type(barcodes).__name__}")
        
        # Фильтруем пустые и невалидные штрихкоды
        valid_barcodes = [str(bc).strip() for bc in barcodes if bc and str(bc).strip()]
        
        if not valid_barcodes:
            raise ValueError("Список 'barcodes' не содержит валидных штрихкодов")
        
        if store_ids is not None and not isinstance(store_ids, list):
            raise ValueError(f"Параметр 'store_ids' должен быть списком или None, получено: {type(store_ids).__name__}")
        
        try:
            moysklad_logger.info(f"=== НАЧАЛО СИНХРОНИЗАЦИИ ОСТАТКОВ ===")
            moysklad_logger.info(f"Запрошены остатки для {len(valid_barcodes)} штрихкодов")
            logger.debug(f"Штрихкоды: {valid_barcodes}")
            logger.debug(f"Выбранные склады: {store_ids}")
            logger.info(f"Начинаем получение остатков для {len(valid_barcodes)} штрихкодов")

            # Batch-поиск товаров по штрихкодам (вместо цикла по одному)
            products_map = self._find_products_by_barcodes(valid_barcodes)
            moysklad_logger.info(f"Найдено {len(products_map)} товаров из {len(valid_barcodes)} штрихкодов")

            if not products_map:
                logger.warning("Не найдено ни одного товара для указанных штрихкодов")
                return {}

            # Формируем параметры запроса для получения остатков
            products_map = {bc: p['id'] for bc, p in products_map.items()}
            product_ids = list(products_map.values())
            logger.info(f"Найдено {len(product_ids)} товаров для получения остатков")

            # Получаем остатки по складам
            stocks_data_raw = self._get_stocks_by_product_ids(product_ids, store_ids)
            logger.debug(f"Получены данные об остатках (по product_id)")

            # Преобразуем данные из формата {product_id: [...]} в формат {barcode: [...]}
            # используя обратное сопоставление из products_map
            stocks_data = {}
            for barcode, product_id in products_map.items():
                if product_id in stocks_data_raw:
                    stocks_data[barcode] = stocks_data_raw[product_id]
                    logger.debug(f"Преобразованы остатки для штрихкода {barcode}")
                else:
                    # Если остатки не найдены для товара, пробуем получить их отдельно
                    logger.debug(f"Остатки не найдены для штрихкода {barcode}, пробуем получить отдельно")
                    try:
                        single_stock_data = self._get_stocks_by_product_ids([product_id], store_ids)
                        if product_id in single_stock_data:
                            stocks_data[barcode] = single_stock_data[product_id]
                            logger.debug(f"Остатки получены отдельно для штрихкода {barcode}")
                        else:
                            stocks_data[barcode] = {}
                    except Exception as e:
                        logger.error(f"Ошибка при получении остатков отдельно для штрихкода {barcode}: {e}")
                        stocks_data[barcode] = {}

            # Формируем результат
            result = {}
            for barcode, product_id in products_map.items():
                result[barcode] = {}
                logger.debug(f"Обрабатываем остатки для штрихкода {barcode}")

                if barcode in stocks_data:
                    logger.debug(f"Найдены остатки для штрихкода {barcode}")
                    for store_info in stocks_data[barcode]:
                        store_id = store_info.get('storeId')
                        if store_id is None:
                            store_name = store_info.get('name', '')
                            if store_name.startswith('Склад '):
                                parts = store_name.split(' ', 1)
                                if len(parts) > 1:
                                    store_id = parts[1]

                            if store_id is None:
                                store_meta = store_info.get('meta', {})
                                store_href = store_meta.get('href', '')
                                if store_href:
                                    store_id = store_href.split('/')[-1]

                        stock = store_info.get('stock', 0)
                        logger.debug(f"Склад ID: {store_id}, остаток: {stock}")

                        if store_ids is not None and len(store_ids) > 0:
                            if store_id in store_ids:
                                result[barcode][store_id] = stock
                                logger.debug(f"Добавлен остаток для склада {store_id}: {stock}")
                        else:
                            if store_id:
                                result[barcode][store_id] = stock
                            else:
                                fallback_name = store_info.get('name', f"unknown_store_{len(result[barcode])}")
                                result[barcode][fallback_name] = stock
                                logger.warning(f"Не удалось извлечь ID склада, используем имя: {fallback_name}")
                    
                    logger.debug(f"Для штрихкода {barcode} добавлены остатки: {result[barcode]}")
                else:
                    logger.warning(f"Остатки не найдены для товара {product_id} (штрихкод {barcode})")
                    result[barcode] = {}

            logger.info(f"Синхронизация завершена: обработано {len(result)} штрихкодов")
            moysklad_logger.info(f"=== КОНЕЦ СИНХРОНИЗАЦИИ ОСТАТКОВ ===")

            return result

        except Exception as e:
            moysklad_logger.error(f"ОШИБКА СИНХРОНИЗАЦИИ: {e}", exc_info=True)
            logger.error(f"Ошибка при получении остатков по складам: {e}")
            raise
    
    def _find_products_by_barcodes(self, barcodes: List[str]) -> Dict[str, Dict]:
        """
        Batch-поиск товаров по множеству штрихкодов одним запросом.
        Использует filter=barcode=BC1;barcode=BC2 для получения всех товаров сразу.
        Fallback на индивидуальный поиск для ненайденных.

        Args:
            barcodes: Список штрихкодов

        Returns:
            Dict[barcode -> product_dict]
        """
        results = {}
        if not barcodes:
            return results

        # Batch-запрос: filter=barcode=BC1;barcode=BC2;...
        # МойСклад поддерживает до 1000 значений в filter
        batch_size = 100
        remaining_barcodes = list(barcodes)

        while remaining_barcodes:
            batch = remaining_barcodes[:batch_size]
            remaining_barcodes = remaining_barcodes[batch_size:]

            # Формируем фильтр: barcode=BC1;barcode=BC2;...
            filter_parts = [f"barcode={bc}" for bc in batch]
            filter_str = ";".join(filter_parts)

            url = f"{self.base_url}/entity/product"
            params = {'filter': filter_str, 'limit': 1000}

            try:
                response = self._make_request('GET', url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    rows = data.get('rows', [])
                    for product in rows:
                        # Ищем匹配的 штрихкод в продукте
                        product_barcodes = []
                        if 'barcodes' in product:
                            for bc_obj in product['barcodes']:
                                for field_value in bc_obj.values():
                                    product_barcodes.append(str(field_value))

                        for bc in batch:
                            if bc in product_barcodes:
                                results[bc] = product
                                break
            except Exception as e:
                logger.warning(f"Batch поиск по штрихкодам не удался: {e}")

            # Для ненайденных в batch пробуем индивидуальный поиск
            for bc in batch:
                if bc not in results:
                    product = self._find_product_by_barcode(bc)
                    if product:
                        results[bc] = product

        return results

    def _find_product_by_barcode(self, barcode: str) -> Optional[Dict]:
        """
        Найти товар по штрихкоду (любой формат)

        Args:
            barcode: Штрихкод товара

        Returns:
            Информация о товаре или None если не найден
        """
        try:
            logger.debug(f"=== ПОИСК ТОВАРА ПО ШТРИХКОДУ: {barcode} ===")
            moysklad_logger.debug(f"ПОИСК ТОВАРА ПО ШТРИХКОДУ: {barcode}")

            # Проверяем, если barcode является списком, извлекаем первый элемент
            if isinstance(barcode, list):
                if len(barcode) > 0:
                    barcode = barcode[0]
                    logger.debug(f"Штрихкод был передан как список, извлекли значение: {barcode}")
                else:
                    logger.warning("Передан пустой список штрихкодов")
                    moysklad_logger.warning("Передан пустой список штрихкодов")
                    return None
            
            logger.debug(f"Начинаем поиск товара по штрихкоду: {barcode}")

            # Сначала пробуем использовать эндпоинт /entity/product/byBarcode для поиска по штрихкоду
            barcode_search_url = f"{self.base_url}/entity/product/byBarcode/{barcode}"
            try:
                response = self._make_request('GET', barcode_search_url)
                logger.debug(f"Статус ответа на запрос поиска по штрихкоду: {response.status_code}")
                logger.debug(f"Ответ от API при поиске по штрихкоду: {response.text[:500]}...")

                if response.status_code == 200:
                    product = response.json()
                    logger.debug(f"Товар найден через byBarcode {barcode}: {product.get('name', 'Unknown')}, ID: {product.get('id', 'No ID')}")
                    return product
                elif response.status_code == 404:
                    logger.debug(f"Товар с штрихкодом {barcode} не найден через byBarcode")
                else:
                    logger.warning(f"Ошибка при поиске по штрихкоду через byBarcode {barcode}: {response.status_code}")
            except Exception as e:
                logger.error(f"Исключение при поиске по штрихкоду через byBarcode {barcode}: {e}")

            # Если товар не найден через byBarcode, пробуем использовать фильтрацию по коду или артикулу
            url = f"{self.base_url}/entity/product"

            # Сначала ищем по полю 'code' (рекомендованный способ)
            code_params = {
                'filter': f'code={barcode}',
                'limit': 100
            }

            response = self._make_request('GET', url, params=code_params)
            logger.debug(f"Статус ответа на запрос по коду: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if 'rows' in data and data['rows']:
                    for idx, product in enumerate(data['rows']):
                        if product.get('code') == barcode:
                            logger.info(f"Товар найден по коду {barcode}: {product.get('name', 'Unknown')}")
                            return product
                else:
                    logger.debug(f"В ответе на запрос по коду нет поля 'rows' или пустой результат")
            elif response.status_code == 404:
                logger.debug(f"Поиск по коду {barcode} вернул 404")
            else:
                logger.warning(f"Ошибка при поиске по коду {barcode}: {response.status_code}")

            # Если не нашли по 'code', пробуем искать по артикулу (article)
            article_params = {
                'filter': f'article={barcode}',
                'limit': 100
            }

            response = self._make_request('GET', url, params=article_params)
            logger.debug(f"Статус ответа на запрос по артикулу: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Ответ по артикулу содержит {len(data.get('rows', []))} строк")
                
                if 'rows' in data:
                    for idx, product in enumerate(data['rows']):
                        logger.debug(f"  Проверяем товар {idx}: {product.get('name', 'Unknown')}, ID: {product.get('id', 'No ID')}, article: {product.get('article')}")
                        if product.get('article') == barcode:
                            logger.info(f"Товар найден по артикулу {barcode}: {product.get('name', 'Unknown')}, ID: {product.get('id', 'No ID')}")
                            logger.debug(f"Полная информация о найденном товаре: {product}")
                            return product
                else:
                    logger.warning(f"В ответе на запрос по артикулу нет поля 'rows': {data}")
            elif response.status_code == 404:
                logger.warning(f"Поиск по артикулу {barcode} вернул 404")
            else:
                logger.error(f"Ошибка при поиске по артикулу {barcode}: {response.status_code}, {response.text}")
            
            # Если не найдено по коду или артикулу, используем обычный поиск
            params = {
                'search': barcode
            }
            
            logger.info(f"Делаем search запрос: {url}?search={barcode}")
            response = self._make_request('GET', url, params=params)
            logger.info(f"Статус ответа на search запрос: {response.status_code}")
            
            # Логируем тело ответа для отладки
            logger.debug(f"Ответ от API при search запросе {barcode}: {response.text[:1000]}...")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Search запрос по штрихкоду '{barcode}' вернул {len(data.get('rows', []))} результатов")
                
                if 'rows' in data:
                    for idx, product in enumerate(data['rows']):
                        logger.debug(f"  Проверяем товар {idx}: {product.get('name', 'Unknown')}, ID: {product.get('id', 'No ID')}")
                        
                        # Проверяем совпадение штрихкода в любом поле
                        if 'barcodes' in product:
                            logger.debug(f"    У товара есть поле barcodes: {product['barcodes']}")
                            for bc_idx, bc in enumerate(product['barcodes']):
                                logger.debug(f"      Проверяем штрихкод {bc_idx}: {bc}")
                                # Проверяем все возможные поля штрихкода
                                for field_name, field_value in bc.items():
                                    logger.debug(f"        Проверяем поле {field_name}: {field_value}")
                                    if field_value == barcode:
                                        logger.info(f"Товар найден по штрихкоду {barcode} в поле {field_name}: {product.get('name', 'Unknown')}, ID: {product.get('id', 'No ID')}")
                                        logger.debug(f"Полная информация о найденном товаре: {product}")
                                        return product
                        else:
                            logger.debug(f"У товара {product.get('name', 'Unknown')} нет поля barcodes")
                else:
                    logger.warning(f"В ответе на search запрос нет поля 'rows': {data}")
                    logger.debug(f"Полная структура ответа: {data}")
            elif response.status_code == 404:
                logger.warning(f"Search запрос по штрихкоду {barcode} вернул 404 - возможно, товар не существует")
            else:
                logger.error(f"Ошибка при search запросе по штрихкоду {barcode}: {response.status_code}, {response.text}")
            
            # Попробуем альтернативный способ - получить товар напрямую, если barcode является ID
            logger.info(f"Проверяем, является ли штрихкод {barcode} ID товара")
            direct_url = f"{self.base_url}/entity/product/{barcode}"
            try:
                logger.info(f"Делаем прямой запрос по ID: {direct_url}")
                response = self._make_request('GET', direct_url)
                logger.info(f"Статус ответа на прямой запрос: {response.status_code}")
                
                # Логируем тело ответа для отладки
                logger.debug(f"Ответ от API при прямом запросе по ID {barcode}: {response.text[:1000]}...")
                
                if response.status_code == 200:
                    product = response.json()
                    logger.info(f"Товар найден напрямую по ID {barcode}: {product.get('name', 'Unknown')}")
                    logger.debug(f"Полная информация о найденном товаре: {product}")
                    return product
                elif response.status_code == 404:
                    logger.info(f"Штрихкод {barcode} не является ID существующего товара")
                else:
                    logger.error(f"Ошибка при прямом запросе по ID {barcode}: {response.status_code}, {response.text}")
            except Exception as e:
                logger.error(f"Исключение при прямом запросе по ID {barcode}: {e}")
            
            # Если товар не найден обычными методами, пробуем получить все товары и искать вручную
            # Это может быть полезно, если в настройках МойСклада штрихкоды хранятся в нестандартных полях
            logger.info(f"Пробуем получить все товары и искать штрихкод {barcode} вручную")
            moysklad_logger.info(f"Пробуем получить все товары и искать штрихкод {barcode} вручную")
            try:
                # Получаем все товары (ограничимся страницами для избежания слишком больших запросов)
                offset = 0
                limit = 100
                found_product = None
                
                while not found_product and offset < 1000:  # Ограничиваем поиск 1000 товаровми
                    browse_params = {
                        'limit': limit,
                        'offset': offset
                    }
                    browse_response = self._make_request('GET', url, params=browse_params)
                    if browse_response.status_code == 200:
                        browse_data = browse_response.json()
                        if 'rows' in browse_data:
                            for product in browse_data['rows']:
                                # Проверяем все возможные поля штрихкода
                                if 'barcodes' in product:
                                    for bc in product['barcodes']:
                                        for field_name, field_value in bc.items():
                                            if field_value == barcode:
                                                logger.info(f"Товар найден вручную по штрихкоду {barcode} в поле {field_name}: {product.get('name', 'Unknown')}, ID: {product.get('id', 'No ID')}")
                                                logger.debug(f"Полная информация о найденном товаре: {product}")
                                                moysklad_logger.info(f"Товар найден вручную по штрихкоду {barcode} в поле {field_name}: {product.get('name', 'Unknown')}, ID: {product.get('id', 'No ID')}")
                                                moysklad_logger.debug(f"Полная информация о найденном товаре: {product}")
                                                found_product = product
                                                break
                                            if found_product:
                                                break
                                        if found_product:
                                            break
                                    if found_product:
                                        break
                        else:
                            logger.warning(f"В ответе на запрос всех товаров нет поля 'rows': {browse_data}")
                            moysklad_logger.warning(f"В ответе на запрос всех товаров нет поля 'rows': {browse_data}")
                            break
                        
                        # Если в ответе нет метаданных или достигнут лимит, выходим
                        if 'meta' in browse_data and browse_data['meta'].get('size', 0) <= offset + limit:
                            break
                        offset += limit
                    else:
                        logger.warning(f"Не удалось получить все товары для ручного поиска: {browse_response.status_code}")
                        moysklad_logger.warning(f"Не удалось получить все товары для ручного поиска: {browse_response.status_code}")
                        break
                
                if found_product:
                    moysklad_logger.info(f"Товар найден: {found_product.get('name', 'Unknown')}, ID: {found_product.get('id', 'No ID')}")
                    return found_product
                else:
                    logger.warning(f"Товар с штрихкодом/артикулом {barcode} не найден ни одним из методов")
                    moysklad_logger.warning(f"Товар с штрихкодом/артикулом {barcode} не найден ни одним из методов")
                    return None
            except Exception as e:
                logger.error(f"Ошибка при ручном поиске товара по штрихкоду {barcode}: {e}")
                moysklad_logger.error(f"Ошибка при ручном поиске товара по штрихкоду {barcode}: {e}", exc_info=True)
                logger.warning(f"Товар с штрихкодом/артикулом {barcode} не найден ни одним из методов")
                moysklad_logger.warning(f"Товар с штрихкодом/артикулом {barcode} не найден ни одним из методов")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при поиске товара по штрихкоду {barcode}: {e}")
            return None
    
    def _find_products_by_barcodes(self, barcodes: List[str]) -> Dict[str, str]:
        """
        Найти несколько товаров по штрихкодам за минимальное количество запросов
        
        Args:
            barcodes: Список штрихкодов для поиска
            
        Returns:
            Словарь соответствия {barcode: product_id}
        """
        try:
            logger.info(f"Начинаем поиск товаров по {len(barcodes)} штрихкодам за оптимизированные запросы")
            logger.debug(f"Штрихкоды для поиска: {barcodes}")
            
            products_map = {}
            remaining_barcodes = barcodes[:]
            
            # Попробуем использовать массовый поиск через фильтрация по нескольким кодам
            # Разобьем на пакеты для избежания проблем с длиной URL
            batch_size = 50  # Размер пакета для поиска
            
            # Создаем копию для итерации, чтобы избежать проблем с изменением списка во время обработки
            barcodes_to_process = remaining_barcodes[:]
            for i in range(0, len(barcodes_to_process), batch_size):
                # Берем пакет из исходного списка
                batch_barcodes = barcodes_to_process[i:i + batch_size]
                logger.debug(f"Обрабатываем пакет штрихкодов {i//batch_size + 1}: {batch_barcodes}")
                
                # Сначала пробуем использовать фильтрацию по кодам (code)
                # Согласно документации, для ИЛИ-логики одного поля используется ;
                codes_filter_parts = [f'code={barcode}' for barcode in batch_barcodes]
                codes_filter_param = ';'.join(codes_filter_parts)
                
                url = f"{self.base_url}/entity/product"
                
                # ПАГИНАЦИЯ: запрашиваем все страницы
                offset = 0
                limit = 1000
                while True:
                    params = {
                        'filter': codes_filter_param,
                        'limit': limit,
                        'offset': offset
                    }
                    
                    try:
                        logger.info(f"Запрос поиска по кодам: пакет {i//batch_size+1}, offset {offset}")
                        response = self._make_request('GET', url, params=params)
                        
                        if response.status_code == 200:
                            data = response.json()
                            rows = data.get('rows', [])
                            logger.debug(f"Получено {len(rows)} товаров (всего {data.get('meta', {}).get('size', 0)})")
                            
                            for product in rows:
                                # Проверяем совпадение кода
                                if product.get('code') in batch_barcodes:
                                    barcode = product['code']
                                    products_map[barcode] = product['id']
                                    if barcode in remaining_barcodes:
                                        remaining_barcodes.remove(barcode)
                                    
                                # Проверяем все штрихкоды в товаре
                                if 'barcodes' in product:
                                    for bc_dict in product['barcodes']:
                                        for field_name, field_value in bc_dict.items():
                                            if field_value in batch_barcodes:
                                                barcode = field_value
                                                products_map[barcode] = product['id']
                                                if barcode in remaining_barcodes:
                                                    remaining_barcodes.remove(barcode)
                            
                            # Проверяем, есть ли еще данные
                            meta = data.get('meta', {})
                            total_size = meta.get('size', 0)
                            if offset + len(rows) >= total_size or not rows:
                                break
                            offset += limit
                        else:
                            if response.status_code == 401:
                                logger.error("Ошибка авторизации 401 при поиске по кодам. Проверьте токен МойСклад")
                                return {}  # Прерываем поиск, возвращаем пустой результат
                            logger.warning(f"Ошибка {response.status_code} при поиске по кодам")
                            break
                    except MoyskladAPIError as e:
                        logger.error(f"Ошибка авторизации при поиске по кодам: {e}")
                        return {}  # Прерываем поиск, возвращаем пустой результат
                    except Exception as e:
                        logger.error(f"Ошибка при поиске по кодам: {e}")
                        break

                # Попробуем поиск по артикулам (article)
                if remaining_barcodes:
                    articles_batch = [bc for bc in batch_barcodes if bc in remaining_barcodes]
                    if articles_batch:
                        # Используем ; для ИЛИ логики в артикулах тоже
                        articles_filter_parts = [f'article={barcode}' for barcode in articles_batch]
                        articles_filter_param = ';'.join(articles_filter_parts)

                        offset = 0
                        while True:
                            params = {
                                'filter': articles_filter_param,
                                'limit': limit,
                                'offset': offset
                            }

                            try:
                                logger.info(f"Запрос поиска по артикулам: пакет {i//batch_size+1}, offset {offset}")
                                response = self._make_request('GET', url, params=params)

                                if response.status_code == 200:
                                    data = response.json()
                                    rows = data.get('rows', [])
                                    
                                    for product in rows:
                                        if product.get('article') in articles_batch:
                                            barcode = product['article']
                                            products_map[barcode] = product['id']
                                            if barcode in remaining_barcodes:
                                                remaining_barcodes.remove(barcode)
                                        
                                        if 'barcodes' in product:
                                            for bc_dict in product['barcodes']:
                                                for field_name, field_value in bc_dict.items():
                                                    if field_value in articles_batch:
                                                        barcode = field_value
                                                        products_map[barcode] = product['id']
                                                        if barcode in remaining_barcodes:
                                                            remaining_barcodes.remove(barcode)
                                    
                                    meta = data.get('meta', {})
                                    if offset + len(rows) >= meta.get('size', 0) or not rows:
                                        break
                                    offset += limit
                                elif response.status_code == 401:
                                    logger.error("Ошибка авторизации 401 при поиске по артикулам. Проверьте токен МойСклад")
                                    return {}  # Прерываем поиск, возвращаем пустой результат
                                else:
                                    break
                            except MoyskladAPIError as e:
                                logger.error(f"Ошибка авторизации при поиске по артикулам: {e}")
                                return {}  # Прерываем поиск, возвращаем пустой результат
                            except Exception as e:
                                logger.error(f"Ошибка при поиске по артикулам: {e}")
                                break

                
                # Если остались ненайденные штрихкоды, попробуем использовать search параметр
                if remaining_barcodes:
                    search_batch = [bc for bc in batch_barcodes if bc in remaining_barcodes]
                    logger.debug(f"Осталось {len(search_batch)} штрихкодов для поиска через search")
                    if search_batch:
                        # Пробуем поиск по одному штрихкоду из оставшихся
                        for barcode in search_batch:
                            try:
                                search_params = {
                                    'search': barcode,
                                    'limit': 100
                                }
                                logger.debug(f"Делаем search запрос для штрихкода {barcode}, параметры: {search_params}")
                                
                                response = self._make_request('GET', url, params=search_params)
                                logger.debug(f"Search ответ статус: {response.status_code}")
                                logger.debug(f"Search тело ответа: {response.text[:500]}...")

                                if response.status_code == 200:
                                    data = response.json()
                                    logger.debug(f"Получено {len(data.get('rows', []))} товаров через search для штрихкода {barcode}")
                                elif response.status_code == 401:
                                    logger.error("Ошибка авторизации 401 при search запросе. Проверьте токен МойСклад")
                                    return {}  # Прерываем поиск, возвращаем пустой результат
                                else:
                                    logger.warning(f"Search запрос вернул ошибку {response.status_code}")
                                    continue

                                if 'rows' in data:
                                    for product in data['rows']:
                                        logger.debug(f"Обрабатываем товар из search: {product.get('id')}, код: {product.get('code')}, артикул: {product.get('article')}")
                                        # Проверяем совпадение штрихкода в любом поле
                                        if 'barcodes' in product:
                                            for bc_dict in product['barcodes']:
                                                for field_name, field_value in bc_dict.items():
                                                    if field_value == barcode:
                                                        product_id = product['id']
                                                        products_map[barcode] = product_id
                                                        logger.info(f"Товар найден по штрихкоду {barcode} в поле {field_name}: {product.get('name', 'Unknown')}, ID: {product_id}")
                                                        # Удаляем найденный штрихкод из оставшихся
                                                        if barcode in remaining_barcodes:
                                                            remaining_barcodes.remove(barcode)
                                                        break
                                                    if barcode in remaining_barcodes:
                                                        break

                                        # Также проверим совпадение кода или артикула
                                        if product.get('code') == barcode and barcode in remaining_barcodes:
                                            product_id = product['id']
                                            products_map[barcode] = product_id
                                            logger.info(f"Товар найден по коду {barcode}: {product.get('name', 'Unknown')}, ID: {product_id}")
                                            remaining_barcodes.remove(barcode)
                                        elif product.get('article') == barcode and barcode in remaining_barcodes:
                                            product_id = product['id']
                                            products_map[barcode] = product_id
                                            logger.info(f"Товар найден по артикулу {barcode}: {product.get('name', 'Unknown')}, ID: {product_id}")
                                            remaining_barcodes.remove(barcode)

                                        if barcode not in remaining_barcodes:
                                            break
                                    else:
                                        logger.warning(f"В search ответе нет поля 'rows': {data}")
                            except Exception as e:
                                logger.error(f"Ошибка при поиске штрихкода {barcode} через search: {e}")
                                # Продолжаем с другими штрихкодами
                                continue
                                
            logger.info(f"Найдено {len(products_map)} товаров из {len(barcodes)} запрошенных штрихкодов")
            logger.debug(f"Словарь на��денных товаров: {products_map}")
            logger.debug(f"����������������������ставшиеся ненайденные штрихкоды: {remaining_barcodes}")
            
            return products_map
            
        except Exception as e:
            logger.error(f"Ошибка при массовом поиске товаров по штрихкодам: {e}")
            # Возвращаем частичный результат, если есть
            return {}
    
    def get_stocks_for_barcodes_batch(self, barcodes: List[str], store_ids: List[str] = None) -> Dict[str, int]:
       """
       Пакетное получение остатков для большого количества штрихкодов
       
       Args:
           barcodes: Список штрихкодов для проверки
           store_ids: Список ID складов для фильтрации (если None, используются все склады)
           
       Returns:
           Словарь с суммарными остатками {'barcode': total_quantity}
       """
       try:
           logger.info(f"Начинаем пакетное получение остатков для {len(barcodes)} штрихкодов")
           logger.debug(f"Штрихкоды: {barcodes}")
           moysklad_logger.info(f"ПАКЕТНОЕ ПОЛУЧЕНИЕ О��ТАТКОВ:")
           moysklad_logger.info(f"Количество штрихкодов: {len(barcodes)}")
           moysklad_logger.info(f"Штрихкоды: {barcodes}")
           
           # Сначала находим все товары по штрихкодам за минимальное количество запросов
           products_map = self._find_products_by_barcodes(barcodes)
           logger.info(f"Результат поиска товаров по штрихкодам: {len(products_map)} найдено из {len(barcodes)} запрошенных")
           logger.debug(f"Сопоставление штрихкодов с ID товаров: {products_map}")
           
           if not products_map:
               logger.warning("Не найдено ни одного товара для указанных штрихкодов")
               # Возвращаем словарь с 0 вместо None, чтобы не нарушать работу других частей программы
               return {barcode: 0 for barcode in barcodes}
           
           # Получаем ID товаров
           product_ids = list(products_map.values())
           logger.info(f"Найдено {len(product_ids)} товаров для получения остатков: {product_ids}")
           
           # Используем краткий отчет об остатках для получения данных по всем товарам за один запрос
           # с последующей фильтрацией по нужным ID
           stocks_result = self.get_current_stock(
               product_ids=product_ids,
               include_zero_lines=True,
               store_ids=store_ids
           )
           logger.info(f"Получены данные об остатках: {len(stocks_result.get('rows', []))} строк")
           
           # Преобразуем результат в формат {barcode: total_quantity}
           result = {barcode: 0 for barcode in barcodes}  # Инициализируем все штрихкоды значением 0
           logger.debug(f"Инициализировали результат: {result}")
           
           # Проверяем наличие строк в ответе
           rows_data = []
           if isinstance(stocks_result, dict) and 'rows' in stocks_result:
               rows_data = stocks_result['rows']
           elif isinstance(stocks_result, list):
               rows_data = stocks_result
           else:
               logger.warning(f"Непредвиденная структура данных в stocks_result: {type(stocks_result)}")
               logger.debug(f"Полученные данные: {stocks_result}")
               return {barcode: 0 for barcode in barcodes}  # Возвращаем 0 для всех штрихкодов
           
           logger.info(f"Обрабатываем {len(rows_data)} строк остатков")
           
           # Группируем остатки по товару
           stocks_by_product = {}
           
           for idx, row in enumerate(rows_data):
               if not isinstance(row, dict):
                   logger.warning(f"Строка {idx} не является словарем: {type(row)}, пропускаем")
                   continue
                   
               # Для отчета /report/stock/all/current структура немного отличается
               # Может быть как с assortment.meta.href, так и с id на верхнем уровне
               product_id = None
               
               # Попробуе�� разные варианты получения ID товара
               # Вариант 1: через assortment.meta.href
               product_meta = row.get('assortment', {}).get('meta', {})
               product_href = product_meta.get('href', '')
               if product_href:
                   product_id = product_href.split('/')[-1]  # Извлекаем ID товара из URL
               
               # Если не удалось извлечь через assortment, пробуем получить напрямую из строки отчета
               if product_id is None:
                   # В некоторых случаях в отчетах может быть напрямую assortmentId
                   product_id = row.get('assortmentId')
               
               # Также проверим вложенные объекты
               if product_id is None:
                   # Проверим, может быть это вложенный объект в assortment
                   assortment_obj = row.get('assortment', {})
                   if 'meta' in assortment_obj:
                       href = assortment_obj['meta'].get('href', '')
                       if href:
                           product_id = href.split('/')[-1]
               
               # Еще одна возможная точка получения ID - если в самой строке есть ID
               if product_id is None and 'id' in row:
                   row_id = row['id']
                   if '/' in row_id:
                       product_id = row_id.split('/')[-1]
                   else:
                       product_id = row_id
               
               # Дополнительная проверка: если все еще не нашли ID, пробуем получить из самой строки
               if product_id is None:
                   # В некоторых случаях ID может быть в поле 'id' как полный URL или просто ID
                   if 'id' in row:
                       id_value = row['id']
                       if isinstance(id_value, str):
                           if '/' in id_value:
                               # Если это URL, извлекаем ID
                               product_id = id_value.split('/')[-1]
                           else:
                               # Если это уже просто ID
                               product_id = id_value
       
               # Проверяем, нужно ли фильтровать по складам
               store_id = row.get('storeId')
               # Если указаны конкретные ID складов, проверяем, что строка относится к одному из них
               if store_ids is not None and len(store_ids) > 0:
                   # Пропускаем строку, если:
                   # 1. store_id не входит в список выбранных складов
                   # Если store_id не определен, строка будет пропущена, что корректно
                   # так как мы не можем определить, к какому складу относится остаток
                   if store_id not in store_ids:
                       # Пропускаем эту строку, так как она не относится к выбранным складам
                       continue
       
               # Логируем информацию о текущей строке
               stock = row.get('stock', 0)
               available = row.get('available', 0)
               quantity = row.get('quantity', 0)
               reserve = row.get('reserve', 0)
               in_transit = row.get('inTransit', 0)
               logger.debug(f"Строка {idx}: product_id={product_id}, store_id={store_id}, stock={stock}, available={available}, quantity={quantity}, reserve={reserve}, inTransit={in_transit}")
               
               if product_id:
                   if product_id not in stocks_by_product:
                       stocks_by_product[product_id] = 0
                   # Добавляем остаток товара, используя только 'stock' (основной остаток)
                   # Это исправляет проблему, когда в 'available' или 'reserve' были значения,
                   # но 'stock' (реальный остаток) был 0
                   stock_val = row.get('stock', 0)
                   available_val = row.get('available', 0)
                   quantity_val = row.get('quantity', 0)
                   reserve_val = row.get('reserve', 0)
                   in_transit_val = row.get('inTransit', 0)
                   
                   # Используем только 'stock' значение, как требовалось
                   actual_stock = stock_val
                   # Логируем все значения для анализа
                   logger.debug(f"Остатки для товара: stock={stock_val}, available={available_val}, quantity={quantity_val}, reserve={reserve_val}, inTransit={in_transit_val}")
                   
                   stocks_by_product[product_id] += actual_stock
                   logger.debug(f"Обновили остаток для товара {product_id}: {stocks_by_product[product_id]} (добавлено {actual_stock} из stock:{stock_val}, available:{available_val}, quantity:{quantity_val}, reserve:{reserve_val}, inTransit:{in_transit_val})")
       
           logger.info(f"Сформирован словарь остатков по товарам: {len(stocks_by_product)} уникальных товаров")
           
           # Убедимся, что для каждого найденного товара устанавливается остаток (даже если 0)
           # Это важно, потому что если API не возвращает строки для товара (например, если остатки на всех выбранных складах равны 0),
           # то в stocks_by_product не будет записи для этого товара
           for barcode, product_id in products_map.items():
               logger.debug(f"Сопоставляем штрихкод {barcode} с товаром ID {product_id}")
               
               if product_id in stocks_by_product:
                   result[barcode] = stocks_by_product[product_id]
                   logger.info(f"Остаток для штрихкода {barcode} (ID: {product_id}): {stocks_by_product[product_id]}")
               else:
                   # Если остаток для товара не найден в результатах, пробуем получить остатки другим способом
                   # Это может происходить, когда товар есть в системе, но остатки по нему не вернулись в первом запросе
                   logger.info(f"Остатки для товара {product_id} не найдены в первом запросе, пробуем альтернативный метод")
                   
                   # Используем метод _get_stocks_by_product_ids, который работает корректно
                   try:
                       single_stocks_data = self._get_stocks_by_product_ids([product_id], store_ids)
                       
                       if product_id in single_stocks_data:
                           # Подсчитываем общий остаток для этого товара
                           single_total = 0
                           for store_info in single_stocks_data[product_id]:
                               # Используем только 'stock' значение, как требовалось
                               stock = store_info.get('stock', 0)
                               # Логируем также другие значения для анализа
                               reserve = store_info.get('reserve', 0)
                               in_transit = store_info.get('inTransit', 0)
                               logger.debug(f"Остатки для товара {product_id}: stock={stock}, reserve={reserve}, inTransit={in_transit}")
                               single_total += stock
                           
                           result[barcode] = single_total
                           logger.info(f"Альтернативный метод (через _get_stocks_by_product_ids) дал результат для штрихкода {barcode}: {single_total}")
                       else:
                           # Если и через _get_stocks_by_product_ids не удалось получить остатки,
                           # пробуем через get_current_stock как резервный вариант
                           single_stock_data = self.get_current_stock(
                               product_ids=[product_id],
                               include_zero_lines=True,
                               store_ids=store_ids
                           )
                           
                           single_total = 0
                           if isinstance(single_stock_data, dict) and 'rows' in single_stock_data:
                               for single_row in single_stock_data['rows']:
                                   single_store_id = single_row.get('storeId')
                                   
                                   # Проверяем, нужно ли фильтровать по складам
                                   if store_ids is not None and len(store_ids) > 0:
                                       if single_store_id not in store_ids:
                                           continue  # Пропускаем, если склад не входит в выбранные
                                   
                                   stock_val = single_row.get('stock', 0)
                                   available_val = single_row.get('available', 0)
                                   quantity_val = single_row.get('quantity', 0)
                                   reserve_val = single_row.get('reserve', 0)
                                   in_transit_val = single_row.get('inTransit', 0)
                                   
                                   # Используем только 'stock' значение, как требовалось
                                   actual_stock = stock_val
                                   # Логируем все значения для анализа
                                   logger.debug(f"Остатки для товара: stock={stock_val}, available={available_val}, quantity={quantity_val}, reserve={reserve_val}, inTransit={in_transit_val}")
                                   
                                   single_total += actual_stock
                           
                           result[barcode] = single_total
                           logger.info(f"Резервный метод (через get_current_stock) дал результат для штрихкода {barcode}: {single_total}")
                   
                   except Exception as e:
                       logger.error(f"Ошибка при альтернативном получении остатков для {barcode}: {e}")
                       result[barcode] = 0  # Устанавливаем 0 в случае ошибки
       
           logger.info(f"Пакетное получение остатков завершено для {len(result)} штрихкодов")
           logger.debug(f"Результат: {result}")
           moysklad_logger.info(f"ПАКЕТНОЕ ПОЛУЧЕНИЕ ОСТАТКОВ ЗАВЕРШЕНО:")
           moysklad_logger.info(f"Обработано штрихкодов: {len(result)}")
           for barcode, quantity in result.items():
               moysklad_logger.info(f"  Штрихкод {barcode}: {quantity} ед.")
           return result
           
       except Exception as e:
           logger.error(f"Ошибка при пакетном получении остатков: {e}")
           moysklad_logger.error(f"ОШИБКА пакетного получения остатков: {e}", exc_info=True)
           # Возвращаем словарь с 0, чтобы не нарушать работу других частей программы
           return {barcode: 0 for barcode in barcodes}
    
    def _get_stocks_by_product_ids(self, product_ids: List[str], store_ids: List[str] = None) -> Dict[str, List[Dict]]:
        """
        Получить остатки по ID товаров
        
        Args:
            product_ids: Список ID товаров
            
        Returns:
            Словарь с остатками {'product_id': [{'name': store_name, 'stock': quantity}]}
        """
        try:
            # Запрашиваем остатки по каждому товару
            result = {}
            
            logger.info(f"Начинаем получение остатков для {len(product_ids)} товаров: {product_ids[:10]}{'...' if len(product_ids) > 10 else ''}")
            moysklad_logger.info(f"ПОЛУЧЕНИЕ ОСТАТКОВ ПО ID ТОВАРОВ:")
            moysklad_logger.info(f"Количество товаров: {len(product_ids)}")
            moysklad_logger.info(f"ID товаров: {product_ids[:10]}{'...' if len(product_ids) > 10 else ''}")
            
            # Согласно документации, можно использовать краткий отчет об остатках
            # и фильтровать по конкретным товарам
            # Используем /report/stock/bystore/current для группировки по товарам и складам
            url = f"{self.base_url}/report/stock/bystore/current"

            # Используем фильтрацию по нескольким assortmentId, но с учетом ограничения на длину URL
            # Формируем строку фильтрации для всех ID товаров, разбивая на маленькие пакеты
            if product_ids:
                # Ограничиваем количество ID в одном запросе, чтобы избежать проблем с длиной URL
                # URL имеет ограничение примерно в 8000 символов, но увеличим размер пакета для улучшения производительности
                batch_size = 50  # Размер пакета для уменьшения количества запросов
                for i in range(0, len(product_ids), batch_size):
                    batch_ids = product_ids[i:i + batch_size]
                    # Формируем фильтр по ID товаров, используя правильный формат для отчета остатков
                    # Согласно документации МойСклад: filter=assortmentId=id1;assortmentId=id2;assortmentId=id3
                    filter_parts = [f'assortmentId={pid}' for pid in batch_ids]
                    filter_param = ';'.join(filter_parts)
                    
                    params = {
                        'filter': filter_param,
                        'limit': 1000,  # Увеличиваем лимит, так как запрашиваем конкретные товары
                        'include': 'zeroLines'  # КРИТИЧЕСКИ ВАЖНО: включаем нулевые остатки
                    }
                    
                    # Добавляем фильтр по складам (запятая для OR, точка с запятой для разделения параметров)
                    if store_ids is not None and len(store_ids) > 0:
                        logger.info(f"Добавляем филтр по {len(store_ids)} складам через filter storeId")
                        logger.debug(f"Store IDs для фильтра: {store_ids}")
                        # Используем точку с запятой (;) для разделения разных параметров
                        # Согласно документации МойСклад: filter=assortmentId=id1;assortmentId=id2;storeId=store1;storeId=store2
                        store_filter_parts = [f'storeId={sid}' for sid in store_ids]
                        params['filter'] = filter_param + ';' + ';'.join(store_filter_parts)
                    
                    try:
                        logger.info(f"Делаем запрос остатков для партии из {len(batch_ids)} товаров")
                        response = self._make_request('GET', url, params=params)
                        
                        logger.debug(f"Ответ от API при запросе остатков: {response.status_code}, {response.text[:500]}...")
                        
                        response.raise_for_status()
                        
                        data = response.json()
                        
                        # Проверяем структуру ответа - в некоторых случаях data может быть массивом
                        if isinstance(data, dict) and 'rows' in data:
                            logger.info(f"Получено {len(data['rows'])} строк с остатками для партии товаров")
                            # Для отчета /report/stock/bystore/current
                            # В rows содержатся записи с assortmentId и storeId
                            for row in data['rows']:
                                # Извлекаем ID товара из поля assortmentId
                                extracted_pid = row.get('assortmentId')
                                
                                # Проверяем, соответствует ли найденный ID искомому
                                if extracted_pid and extracted_pid in product_ids:
                                    store_id = row.get('storeId')
                                    # Проверяем, нужно ли фильтровать по складам
                                    if store_ids is not None and len(store_ids) > 0:
                                        # Добавляем информацию только по указанным складам
                                        if store_id in store_ids:
                                            # Создаем структуру, как ожидается в остальной части кода
                                            # Но для отчета по складам нужно сгруппировать по товарам
                                            if extracted_pid not in result:
                                                result[extracted_pid] = []
                                            
                                            # Добавляем информацию о складе и остатке
                                            store_info = {
                                                'meta': {},  # В отчете нет метаданных склада в привычном формате
                                                'name': f"Склад {store_id or 'неизвестен'}",  # Имя склада по ID
                                                'stock': row.get('stock', 0),
                                                'reserve': row.get('reserve', 0),
                                                'inTransit': row.get('inTransit', 0)
                                            }
                                            result[extracted_pid].append(store_info)
                                    else:
                                        # Если склады не указаны, добавляем все
                                        if extracted_pid not in result:
                                            result[extracted_pid] = []
                                        
                                        # Добавляем информацию о складе и остатке
                                        store_info = {
                                            'meta': {},  # В отчете нет метаданных склада в привычном формате
                                            'name': f"Склад {store_id or 'неизвестен'}",  # Имя склада по ID
                                            'stock': row.get('stock', 0),
                                            'reserve': row.get('reserve', 0),
                                            'inTransit': row.get('inTransit', 0)
                                        }
                                        result[extracted_pid].append(store_info)
                        elif isinstance(data, list):
                            # Если data - это сразу массив строк (rows), обрабатываем его напрямую
                            logger.info(f"Получено {len(data)} строк с остатками для партии товаров (структура без 'rows')")
                            for row in data:
                                # Извлекаем ID товара из поля assortmentId
                                extracted_pid = row.get('assortmentId')
                                
                                # Проверяем, соответствует ли найденный ID искомому
                                if extracted_pid and extracted_pid in product_ids:
                                    # Создаем структуру, как ожидается в остальной части кода
                                    if extracted_pid not in result:
                                        result[extracted_pid] = []
                                    
                                    store_id = row.get('storeId')
                                    # Проверяем, нужно ли фильтровать по складам
                                    if store_ids is not None and len(store_ids) > 0:
                                        # Добавляем информацию только по указанным складам
                                        if store_id in store_ids:
                                            # Добавляем информацию о складе и остатке
                                            store_info = {
                                                'meta': {},  # В отчете нет метаданных склада в привычном формате
                                                'name': f"Склад {store_id or 'неизвестен'}",  # Имя склада по ID
                                                'stock': row.get('stock', 0),
                                                'reserve': row.get('reserve', 0),
                                                'inTransit': row.get('inTransit', 0)
                                            }
                                            result[extracted_pid].append(store_info)
                                    else:
                                        # Если склады не указаны, добавляем все
                                        # Добавляем информацию о складе и остатке
                                        store_info = {
                                            'meta': {},  # В отчете нет метаданных склада в привычном формате
                                            'name': f"Склад {store_id or 'неизвестен'}",  # Имя склада по ID
                                            'stock': row.get('stock', 0),
                                            'reserve': row.get('reserve', 0),
                                            'inTransit': row.get('inTransit', 0)
                                        }
                                        result[extracted_pid].append(store_info)
                        else:
                            logger.warning(f"В ответе на запрос остатков не найдено поле 'rows' и это не массив: {data}")
                            logger.debug(f"Ответ не содержит rows и не является массивом: {data}")
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Ошибка при получении остатков для партии товаров {batch_ids}: {e}")
                        # Продолжаем с другими партиями
                        continue
            
            # Для товаров, по которым не были получены остатки, пробуем получить их по одному
            # Это поможет в случаях, когда товары есть, но по ним нет остатков на складах
            for pid in product_ids:
                if pid not in result:
                    logger.info(f"Для товара {pid} не были получены остатки, пробуем получить отдельно")
                    try:
                        # Делаем отдельный запрос для конкретного товара
                        filter_param = f'assortmentId={pid}'
                        params = {
                            'filter': filter_param,
                            'limit': 1000,
                            'include': 'zeroLines'  # Включаем нулевые остатки
                        }
                        
                        # Добавляем фильтр storeId, если указаны склады
                        if store_ids is not None and len(store_ids) > 0:
                            logger.debug(f"Добавляем storeId фильтр в отдельный запрос для товара {pid}")
                            params['filter'] = filter_param + f";storeId={','.join(store_ids)}"
                        response = self._make_request('GET', url, params=params)
                        response.raise_for_status()
                        data = response.json()
                        
                        if isinstance(data, dict) and 'rows' in data:
                            individual_result = []
                            for row in data['rows']:
                                extracted_pid = row.get('assortmentId')
                                if extracted_pid == pid:
                                    store_id = row.get('storeId')
                                    # Проверяем, нужно ли фильтровать по складам
                                    if store_ids is not None and len(store_ids) > 0:
                                        if store_id in store_ids:
                                            store_info = {
                                                'meta': {},
                                                'name': f"Склад {store_id or 'неизвестен'}",
                                                'stock': row.get('stock', 0),
                                                'reserve': row.get('reserve', 0),
                                                'inTransit': row.get('inTransit', 0)
                                            }
                                            individual_result.append(store_info)
                                    else:
                                        # Если склады не указаны, добавляем все
                                        store_info = {
                                            'meta': {},
                                            'name': f"Склад {store_id or 'неизвестен'}",
                                            'stock': row.get('stock', 0),
                                            'reserve': row.get('reserve', 0),
                                            'inTransit': row.get('inTransit', 0)
                                        }
                                        individual_result.append(store_info)
                            if individual_result:
                                result[pid] = individual_result
                                logger.info(f"Остатки для товара {pid} получены отдельно: {len(individual_result)} записей")
                            else:
                                # Если остатков нет, все равно добавляем пустой список
                                result[pid] = []
                                logger.info(f"Для товара {pid} остатки отсутствуют, добавлен пустой список")
                        elif isinstance(data, list):
                            individual_result = []
                            for row in data:
                                extracted_pid = row.get('assortmentId')
                                if extracted_pid == pid:
                                    store_id = row.get('storeId')
                                    # Проверяем, нужно ли фильтровать по складам
                                    if store_ids is not None and len(store_ids) > 0:
                                        if store_id in store_ids:
                                            store_info = {
                                                'meta': {},
                                                'name': f"Склад {store_id or 'неизвестен'}",
                                                'stock': row.get('stock', 0),
                                                'reserve': row.get('reserve', 0),
                                                'inTransit': row.get('inTransit', 0)
                                            }
                                            individual_result.append(store_info)
                                    else:
                                        # Если склады не указаны, добавляем все
                                        store_info = {
                                            'meta': {},
                                            'name': f"Склад {store_id or 'неизвестен'}",
                                            'stock': row.get('stock', 0),
                                            'reserve': row.get('reserve', 0),
                                            'inTransit': row.get('inTransit', 0)
                                        }
                                        individual_result.append(store_info)
                            if individual_result:
                                result[pid] = individual_result
                                logger.info(f"Остатки для товара {pid} получены отдельно: {len(individual_result)} записей")
                            else:
                                # Если остатков нет, все равно добавляем пустой список
                                result[pid] = []
                                logger.info(f"Для товара {pid} остатки отсутствуют, добавлен пустой список")
                    except Exception as e:
                        logger.error(f"Ошибка при получении остатков отдельно для товара {pid}: {e}")
                        # Даже при ошибке добавляем пустой список, чтобы показать, что товар был обработан
                        result[pid] = []
                        logger.info(f"Для товара {pid} добавлен пустой список из-за ошибки")
                        moysklad_logger.error(f"Ошибка получения остатков для товара {pid}: {e}", exc_info=True)
            
            logger.info(f"Возвращаем результат для {len(result)} товаров из {len(product_ids)} запрошенных")
            moysklad_logger.info(f"Результат получения остатков по ID:")
            moysklad_logger.info(f"Запрошено товаров: {len(product_ids)}")
            moysklad_logger.info(f"Получено данных для: {len(result)} товаров")
            for pid, stores in result.items():
                moysklad_logger.info(f"  Товар {pid}: {len(stores)} записей остатков")
                for store_info in stores:
                    moysklad_logger.info(f"    Склад: {store_info.get('name', 'N/A')}, остаток: {store_info.get('stock', 0)}")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении остатков по ID товаров: {e}")
            moysklad_logger.error(f"ОШИБКА получения остатков по ID товаров: {e}", exc_info=True)
            raise
    
    def get_total_stock(self, barcodes: List[str], store_ids: List[str] = None) -> Dict[str, int]:
        """
        Получить суммарные остатки для указанных штрихкодов
        
        Args:
            barcodes: Список штрихкодов для проверки
            store_ids: Список ID складов для фильтрации (если None, используются все склады)
            
        Returns:
            Словарь с суммарными остатками {'barcode': total_quantity}
        """
        try:
            stocks_by_stores = self.get_stock_by_stores(barcodes, store_ids)
            result = {}
            
            for barcode, stores in stocks_by_stores.items():
                if store_ids:
                    # Суммируем только остатки по указанным складам
                    # Учитываем остатки, где ID склада входит в список выбранных
                    total = sum(quantity for store_id, quantity in stores.items() if store_id in store_ids)
                else:
                    # Суммируем все остатки, как раньше
                    total = sum(stores.values())
                result[barcode] = total
            
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении суммарных остатков: {e}")
            raise
    
    def get_current_stock(self, product_ids: List[str] = None,
                         include_zero_lines: bool = False, stock_type: str = 'stock', store_ids: List[str] = None) -> Dict:
        """
        Получить текущие остатки с возможностью фильтрации

        Args:
            product_ids: Список ID товаров для фильтрации
            include_zero_lines: Включать ли нулевые остатки
            stock_type: Тип остатка ('stock', 'freeStock', 'quantity', 'reserve', 'inTransit')

        Returns:
            Словарь с данными об остатках
        """
        try:
            logger.info(f"=== НАЧИНАЕМ ПОЛУЧЕНИЕ ТЕКУЩИХ ОСТАТКОВ ===")
            logger.info(f"Количество запрашиваемых товаров: {len(product_ids) if product_ids else 0}")
            logger.info(f"Product IDs: {product_ids}")
            logger.info(f"Фильтр по складам: {store_ids}")
            logger.info(f"Включать нулевые остатки: {include_zero_lines}")
            moysklad_logger.info(f"=== НАЧИНАЕМ ПОЛУЧЕНИЕ ТЕКУЩИХ ОСТАТКОВ ===")
            moysklad_logger.info(f"Количество товаров: {len(product_ids) if product_ids else 0}")
            moysklad_logger.info(f"Product IDs: {product_ids}")
            moysklad_logger.info(f"Фильтр по складам: {store_ids}")

            # Используем /report/stock/bystore/current для группировки по товарам и складам
            url = f"{self.base_url}/report/stock/bystore/current"
            logger.info(f"URL запроса: {url}")

            params = {
                'limit': 1000,
                'stockType': stock_type
            }

            # Добавляем параметр для включения нулевых остатков, если нужно
            if include_zero_lines:
                params['include'] = 'zeroLines'
                logger.info("Включены нулевые остатки (include=zeroLines)")
            
            # Фильтрация по товарам
            if product_ids is not None and len(product_ids) > 0:
                logger.info(f"Запрашиваем остатки для {len(product_ids)} товаров")
                # Ограничиваем количество ID в одном запросе
                batch_size = 50
                all_results = {'rows': []}  # Инициализируем как пустой результат
                 
                for i in range(0, len(product_ids), batch_size):
                    batch_ids = product_ids[i:i + batch_size]
                    logger.info(f"Обрабатываем пакет {i//batch_size + 1}, товаров в пакете: {len(batch_ids)}")
                    logger.info(f"IDs в пакете: {batch_ids}")

                    # Для отчета /report/stock/bystore/current используем правильный параметр фильтрации
                    # Согласно документации МойСклад: filter=assortmentId=id1;assortmentId=id2;assortmentId=id3
                    filter_parts = [f'assortmentId={pid}' for pid in batch_ids]
                    params['filter'] = ';'.join(filter_parts)
                    
                    logger.info(f"Фильтр assortmentId: {params['filter']}")

                    # Добавляем фильтр по складам
                    if store_ids is not None and len(store_ids) > 0:
                        logger.info(f"Добавляем фильтр по {len(store_ids)} складам через filter storeId")
                        logger.info(f"Store IDs для фильтра: {store_ids}")
                        # Используем точку с запятой (;) для разделения разных параметров
                        # Согласно документации МойСклад: filter=assortmentId=id1;assortmentId=id2;storeId=store1;storeId=store2
                        store_filter_parts = [f'storeId={sid}' for sid in store_ids]
                        params['filter'] = params['filter'] + ';' + ';'.join(store_filter_parts)
                        logger.info(f"Итоговый фильтр: {params['filter']}")
                    else:
                        logger.info("Фильтр по складам не применяется (store_ids пуст или None)")

                    logger.info(f"Делаем запрос остатков с фильтром по {len(batch_ids)} товарам")
                    logger.info(f"Параметры запроса: {params}")
                    moysklad_logger.info(f"Запрос остатков: фильтр={params['filter']}")
                    response = self._make_request('GET', url, params=params.copy())
                    logger.info(f"Ответ на запрос остатков: статус {response.status_code}, длина тела: {len(response.text)}")
                    
                    # Проверяем структуру ответа перед логированием
                    try:
                        response_json = response.json()
                        if isinstance(response_json, dict):
                            moysklad_logger.info(f"Ответ API: статус {response.status_code}, строк: {len(response_json.get('rows', []))}")
                        elif isinstance(response_json, list):
                            moysklad_logger.info(f"Ответ API: статус {response.status_code}, строк: {len(response_json)} (список)")
                        else:
                            moysklad_logger.warning(f"Ответ API: неожиданный тип {type(response_json)}")
                    except Exception as e:
                        moysklad_logger.warning(f"Не удалось распарсить ответ API: {e}")

                    data = response.json()
                    logger.info(f"Получены данные: {type(data)}")
                    logger.debug(f"Полученные данные: {data}")

                    # Обработка ответа в зависимости от его структуры
                    if isinstance(data, dict) and 'rows' in data:
                        rows_data = data['rows']
                    elif isinstance(data, list):
                        # API вернул список напрямую
                        rows_data = data
                    else:
                        logger.warning(f"Непредвиденная структура ответа: {type(data)}")
                        rows_data = []
                    
                    if isinstance(data, dict) and 'rows' in data:
                        rows_count = len(data['rows'])
                        logger.info(f"Получено {rows_count} строк остатков в пакете {i//batch_size + 1}")
                        moysklad_logger.info(f"Получено {rows_count} строк остатков")

                        # Выводим первые 10 строк для отладки
                        for idx, row in enumerate(data['rows'][:10]):
                            product_id = row.get('assortmentId')
                            store_id = row.get('storeId')
                            stock = row.get('stock', 0)
                            logger.info(f"  Строка {idx}: product_id={product_id}, store_id={store_id}, stock={stock}")
                    elif isinstance(data, list):
                        rows_count = len(data)
                        logger.info(f"Получено {rows_count} строк остатков (список) в пакете {i//batch_size + 1}")
                        moysklad_logger.info(f"Получено {rows_count} строк остатков (список)")
                        
                        # Выводим первые 10 строк для отладки
                        for idx, row in enumerate(data[:10]):
                            product_id = row.get('assortmentId') if isinstance(row, dict) else 'N/A'
                            store_id = row.get('storeId') if isinstance(row, dict) else 'N/A'
                            stock = row.get('stock', 0) if isinstance(row, dict) else 0
                            logger.info(f"  Строка {idx}: product_id={product_id}, store_id={store_id}, stock={stock}")

                        # Фильтруем строки по складам, если указаны store_ids
                        added_count = 0
                        skipped_count = 0
                        for row in rows_data:
                            # Проверяем, нужно ли фильтровать по складам
                            if store_ids is not None and len(store_ids) > 0:
                                store_id = row.get('storeId') if isinstance(row, dict) else None
                                if store_id:
                                    if store_id in store_ids:
                                        all_results['rows'].append(row)
                                        added_count += 1
                                    else:
                                        skipped_count += 1
                                        if skipped_count <= 5:  # Показываем только первые 5 пропущенных
                                            logger.info(f"  Пропущена строка: склад {store_id} не в списке {store_ids}")
                                else:
                                    logger.debug(f"Строка пропущена: store_id отсутствует или равен None")
                            else:
                                # Если store_ids не указаны или пустые, добавляем все строки
                                all_results['rows'].append(row)

                        logger.info(f"Добавлено {added_count} строк, пропущено {skipped_count} строк")

                        # Подробное логирование каждой строки
                        for idx, row in enumerate(rows_data):
                            if not isinstance(row, dict):
                                logger.debug(f"  Строка {idx}: не dict, пропускаем")
                                continue
                            logger.debug(f"  Строка {idx}: {type(row)}, содержимое: {str(row)[:300]}...")

                            # Проверяем структуру строки
                            product_info = row.get('assortment', {})
                            product_id = row.get('assortmentId')
                            if not product_id and 'meta' in product_info:
                                href = product_info['meta'].get('href', '')
                                if href:
                                    product_id = href.split('/')[-1]

                            # Проверим другие возможные поля ID
                            if not product_id:
                                # Проверим в самой строке
                                if 'id' in row:
                                    row_id = row['id']
                                    if '/' in row_id:
                                        product_id = row_id.split('/')[-1]
                                    else:
                                        product_id = row_id

                            stock = row.get('stock', 0)
                            available = row.get('available', 0)
                            quantity = row.get('quantity', 0)
                            reserve = row.get('reserve', 0)
                            in_transit = row.get('inTransit', 0)
                            
                            logger.info(f"    Строка {idx}: ID={product_id}, stock={stock}, available={available}, quantity={quantity}, reserve={reserve}, inTransit={in_transit}")
                    elif isinstance(data, list):
                        # Если ответ - список, обрабатываем как список строк
                        logger.info(f"Получено {len(data)} строк остатков в виде списка в пакете {i//batch_size + 1}")
                        
                        # Фильтруем строки по складам, если указаны store_ids
                        for row in data:
                            if isinstance(row, dict):
                                # Проверяем, нужно ли фильтровать по складам
                                if store_ids is not None and len(store_ids) > 0:
                                    store_id = row.get('storeId')
                                    # Добавляем строку, если store_id находится в списке выбранных складов
                                    if store_id in store_ids:
                                        all_results['rows'].append(row)
                                else:
                                    # Если store_ids не указаны или пустые, добавляем все строки
                                    all_results['rows'].append(row)
                        
                        # Подробное логирование каждой строки
                        for idx, row in enumerate(data):
                            if isinstance(row, dict):
                                logger.debug(f"  Строка {idx}: {type(row)}, содержимое: {str(row)[:300]}...")
                                
                                product_info = row.get('assortment', {})
                                product_id = row.get('assortmentId')
                                if not product_id and 'meta' in product_info:
                                    href = product_info['meta'].get('href', '')
                                    if href:
                                        product_id = href.split('/')[-1]
                                
                                # Проверим другие возможные поля ID
                                if not product_id:
                                    # Проверим в самой строке
                                    if 'id' in row:
                                        row_id = row['id']
                                        if '/' in row_id:
                                            product_id = row_id.split('/')[-1]
                                        else:
                                            product_id = row_id
                                
                                stock = row.get('stock', 0)
                                available = row.get('available', 0)
                                quantity = row.get('quantity', 0)
                                reserve = row.get('reserve', 0)
                                in_transit = row.get('inTransit', 0)
                                
                                logger.info(f"    Строка {idx}: ID={product_id}, stock={stock}, available={available}, quantity={quantity}, reserve={reserve}, inTransit={in_transit}")
                    else:
                        # Если в ответе нет 'rows' и это не список, но это словарь с другой структурой
                        if isinstance(data, dict) and len(data) > 0:
                            logger.warning(f"Ответ не содержит 'rows', но содержит данные: {list(data.keys())[:5]}")
                            logger.debug(f"Полная структура данных: {data}")
                        else:
                            logger.warning(f"Ответ не содержит 'rows', не является словарем или списком: {type(data)}, данные: {str(data)[:500]}")
                
                logger.info(f"=== ВСЕГО ПОЛУЧЕНО {len(all_results['rows'])} СТРОК ОСТАТКОВ ДЛЯ {len(product_ids)} ТОВАРОВ ===")
                
                # Дополнительная проверка: для каждого товара из запроса ищем остатки в полученных данных
                if product_ids:
                    logger.info("=== ДЕТАЛЬНЫЙ АНАЛИЗ НАЛИЧИЯ ОСТАТКОВ ДЛЯ КАЖДОГО ТОВАРА ===")
                    for pid in product_ids:
                        found_rows_for_pid = []
                        total_stock_for_product = 0
                        for idx, row in enumerate(all_results['rows']):
                            # Проверяем все возможные поля для ID товара
                            possible_ids = []
                            
                            # assortmentId
                            aid = row.get('assortmentId')
                            if aid:
                                possible_ids.append(aid)
                            
                            # Из meta в assortment
                            assortment_meta = row.get('assortment', {})
                            if 'meta' in assortment_meta:
                                href = assortment_meta['meta'].get('href', '')
                                if href:
                                    extracted_id = href.split('/')[-1]
                                    possible_ids.append(extracted_id)
                            
                            # id прямо в строке
                            row_id = row.get('id')
                            if row_id:
                                if '/' in row_id:
                                    row_id = row_id.split('/')[-1]
                                possible_ids.append(row_id)
                            
                            # Проверим также возможные вложенные поля
                            if 'assortment' in row:
                                ass_meta = row['assortment'].get('meta', {})
                                if 'href' in ass_meta:
                                    href = ass_meta['href']
                                    if href:
                                        extracted_id = href.split('/')[-1]
                                        possible_ids.append(extracted_id)
                            
                            if pid in possible_ids:
                                found_rows_for_pid.append(idx)
                                stock = row.get('stock', 0)
                                available = row.get('available', 0)
                                quantity = row.get('quantity', 0)
                                reserve = row.get('reserve', 0)
                                in_transit = row.get('inTransit', 0)
                                
                                # Используем только 'stock' значение, как требовалось
                                actual_stock = stock
                                # Логируем все значения для анализа
                                logger.debug(f"Остатки для товара: stock={stock}, available={available}, quantity={quantity}, reserve={reserve}, inTransit={in_transit}")
                                
                                total_stock_for_product += actual_stock
                                
                                store_id = row.get('storeId', 'unknown')
                                logger.info(f"  Товар {pid} найден в строке {idx}: storeId={store_id}, stock={stock}, available={available}, quantity={quantity}, reserve={reserve}, inTransit={in_transit}, actual_stock={actual_stock}, cumulative_total={total_stock_for_product}")
                        
                        if not found_rows_for_pid:
                            # logger.warning(f"  Товар {pid} не найден в полученных данных остатков")
                            # Убираем предупреждение, так как это нормальная ситуация для товаров с нулевым остатком
                            pass
                        else:
                            logger.info(f"  Товар {pid}: найдено {len(found_rows_for_pid)} строк остатков, общий остаток: {total_stock_for_product}")
                
                return all_results
            else:
                logger.info("Запрашиваем все остатки без фильтрации по товарам")
                response = self._make_request('GET', url, params=params)
                logger.info(f"Ответ на общий запрос остатков: статус {response.status_code}, длина тела: {len(response.text)}")
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Получены общие остатки, тип данных: {type(data)}, {'rows count: ' + str(len(data.get('rows', []))) if isinstance(data, dict) else 'не словарь'}")
                logger.debug(f"Данные общего отчета: {data}")
                
                # Обработка общего ответа в зависимости от его структуры
                if isinstance(data, dict) and 'rows' in data:
                    logger.info(f"Количество строк в общем отчете: {len(data['rows'])}")
                    
                    # Фильтруе�� по складам, если указаны store_ids
                    if store_ids is not None and len(store_ids) > 0:
                        filtered_rows = []
                        for row in data['rows']:
                            store_id = row.get('storeId')
                            # Добавляем строку, если store_id находится в списке выбранных складов
                            if store_id in store_ids:
                                filtered_rows.append(row)
                        data['rows'] = filtered_rows
                        logger.info(f"После фильтрации по складам осталось {len(filtered_rows)} строк")
                    
                    return data
                elif isinstance(data, list):
                    logger.info(f"Общий отчет в виде списка, количество элементов: {len(data)}")
                    
                    # Фильтруем по складам, если указаны store_ids
                    if store_ids is not None and len(store_ids) > 0:
                        filtered_rows = []
                        for row in data:
                            if isinstance(row, dict):
                                store_id = row.get('storeId')
                                # Добавляем строку, если store_id находится в списке выбранных складов
                                if store_id in store_ids:
                                    filtered_rows.append(row)
                        data = filtered_rows
                        logger.info(f"После фильтрации по складам осталось {len(filtered_rows)} строк")
                    
                    return {'rows': data}
                else:
                    logger.warning(f"Общий отчет не содержит 'rows' и не является списком: {type(data)}")
                    return {'rows': []}
        except Exception as e:
            logger.error(f"Ошибка при получении текущих остатков: {e}")
            raise
    
    def get_stock_with_changed_since(self, changed_since: str, include_zero_lines: bool = True) -> Dict:
        """
        Получить остатки, которые изменились с определенного момента времени
        
        Args:
            changed_since: Дата и вр��мя в формате "гггг-мм-дд чч-мм-с��"
            include_zero_lines: Включать ли нулевые остатки (по умолчанию True для changedSince)
        
        Returns:
            Словарь с данными об остатках
        """
        try:
            url = f"{self.base_url}/report/stock/all/current"
            
            params = {
                'limit': 1000,
                'changedSince': changed_since
            }
            
            # При использовании changedSince нулевые остатки включаются автоматически,
            # но добавим параметр для явного указания
            if include_zero_lines:
                params['include'] = 'zeroLines'
            
            response = self._make_request('GET', url, params=params)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Ошибка при получении измененных остатков: {e}")
            raise
    
    def get_stock_by_stores_extended(self, product_ids: List[str] = None, store_ids: List[str] = None,
                                   include_zero_lines: bool = False, stock_type: str = 'stock') -> Dict:
        """
        Расширенный метод получения остатков по складам с дополнительными параметрами
        
        Args:
            product_ids: Список ID товаров для фильтрации
            store_ids: Список ID складов для фильтрации
            include_zero_lines: Включать ли нулевые остатки
            stock_type: Тип остатка ('stock', 'freeStock', 'quantity', 'reserve', 'inTransit')
        
        Returns:
            Словарь с данными об остатках по складам
        """
        try:
            url = f"{self.base_url}/report/stock/bystore/current"
            
            params = {
                'limit': 1000,
                'stockType': stock_type
            }
            
            # Добавляем параметр для включения нулевых остатков, если нужно
            if include_zero_lines:
                params['include'] = 'zeroLines'
            
            # Если не заданы product_ids, возвращаем все остатки
            if product_ids is None or len(product_ids) == 0:
                response = self._make_request('GET', url, params=params)
                response.raise_for_status()
                
                result = response.json()
                # Фильтруем по складам, если указаны
                if store_ids is not None and len(store_ids) > 0:
                    filtered_rows = []
                    if 'rows' in result:
                        for row in result['rows']:
                            store_id = row.get('storeId')
                            # Добавляем строку, если store_id находится в списке выбранных складов
                            if store_id in store_ids:
                                filtered_rows.append(row)
                        result['rows'] = filtered_rows
                return result
            
            # Ограничиваем количество идентификаторов в одном запросе
            # Также учитываем ограничения на длину URL (обычно около 8000 символов)
            MAX_IDS_PER_REQUEST = 50  # Количество ID в одном запросе
            
            all_results = {'rows': []}
            
            # Разбиваем список ID на части
            for i in range(0, len(product_ids), MAX_IDS_PER_REQUEST):
                batch_ids = product_ids[i:i + MAX_IDS_PER_REQUEST]
                
                # Используем правильную фильтрацию по assortmentId для эндпоинта /report/stock/bystore/current
                batch_filter_parts = [f'assortmentId={pid}' for pid in batch_ids]
                batch_filter = ';'.join(batch_filter_parts)
                
                # Создаем копию параметров для текущего запроса
                batch_params = params.copy()
                batch_params['filter'] = batch_filter
                
                try:
                    response = self._make_request('GET', url, params=batch_params)
                    response.raise_for_status()
                    
                    data = response.json()
                    if 'rows' in data:
                        all_results['rows'].extend(data['rows'])
                except Exception as e:
                    logger.warning(f"Ошибка при получении остатков для пакета товаров {i//MAX_IDS_PER_REQUEST + 1}: {e}")
                    # Продолжаем с другими пакетами
                    continue
            
            # Фильтруем по складам, если указаны
            if store_ids is not None and len(store_ids) > 0:
                filtered_rows = []
                for row in all_results['rows']:
                    store_id = row.get('storeId')
                    # Проверяем, что это остатки для одного из нужных товаров
                    row_product_id = row.get('assortmentId')
                    if row_product_id in (product_ids if product_ids else [row_product_id]):
                        if store_id and store_id in store_ids:
                            filtered_rows.append(row)
                all_results['rows'] = filtered_rows
            else:
                # Если склады не указаны, но указаны товары, фильтруем только по товарам
                if product_ids:
                    filtered_rows = []
                    for row in all_results['rows']:
                        row_product_id = row.get('assortmentId')
                        if row_product_id and row_product_id in product_ids:
                            filtered_rows.append(row)
                    all_results['rows'] = filtered_rows
            
            return all_results
        except Exception as e:
            logger.error(f"Ошибка при получении остатков по складам (расширенный): {e}")
            raise
    
    def get_stock_by_stores_enhanced(self, barcodes: List[str], store_ids: List[str] = None) -> Dict[str, Dict[str, int]]:
        """
        Улучшенный метод получения остатков с поддержкой больших объемов данных
        
        Args:
            barcodes: Список штрихкодов для проверки
            store_ids: Список ID складов для фильтрации (если None, используются все склады)
            
        Returns:
            Словарь с остатками по складам {'barcode': {'store_name': quantity}}
        """
        # Для больших объемов используем пакетную обработку
        if len(barcodes) > self.batch_size:
            logger.info(f"Обнаружено большое количество штрихкодов ({len(barcodes)}). Используется пакетная обработка.")
            return self._get_stock_batched(barcodes, store_ids)
        
        # Стандартная обработка для небольших объемов
        return self.get_stock_by_stores(barcodes, store_ids)
    
    def _get_stock_batched(self, barcodes: List[str], store_ids: List[str] = None) -> Dict[str, Dict[str, int]]:
        """
        Пакетная обработка остатков для больших объемов
        """
        def process_batch(batch_barcodes, store_ids_param):
            batch_result = {}
            products_map = {}
            
            # Получаем товары для пакета
            for barcode in batch_barcodes:
                if isinstance(barcode, list):
                    if len(barcode) > 0:
                        barcode = barcode[0]
                    else:
                        continue
                
                product = self._find_product_by_barcode(str(barcode))
                if product:
                    products_map[str(barcode)] = product['id']
            
            if products_map:
                # Получаем остатки для товаров пакета
                stock_data = self._get_stock_for_products(list(products_map.values()), store_ids_param)
                
                # Преобразуем обратно к штрихкодам
                for barcode, product_id in products_map.items():
                    if product_id in stock_data:
                        batch_result[barcode] = stock_data[product_id]
            
            return batch_result
        
        # Используем пакетную обработку
        batches_results = self._batch_process_barcodes(barcodes, process_batch, store_ids)
        
        # Объединяем результаты
        final_result = {}
        for batch_result in batches_results:
            final_result.update(batch_result)
        
        return final_result