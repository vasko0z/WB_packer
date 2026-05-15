# db_discovery.py
"""
Модуль для автоматического обнаружения сервера PostgreSQL в локальной сети
"""
import socket
import logging
import time
import os
from typing import Optional, List, Dict
import ipaddress
import concurrent.futures
import json
from pathlib import Path

# Пытаемся использовать psycopg3 (совместим с Python 3.14+), иначе psycopg2
psycopg = None
psycopg2 = None
PSYCOPG_VERSION = 0
try:
    import psycopg
    PSYCOPG_VERSION = 3
    logger.info("db_discovery: используется psycopg3")
except ImportError:
    try:
        import psycopg2
        PSYCOPG_VERSION = 2
        logger.info("db_discovery: используется psycopg2")
    except ImportError:
        logger.warning("db_discovery: psycopg2/psycopg3 не установлены")

logger = logging.getLogger(__name__)

class PostgreSQLDiscovery:
    """Класс для автоматического обнаружения сервера PostgreSQL в сети"""

    DEFAULT_PORT = 5432
    DEFAULT_DATABASE = "wb_packer"
    DEFAULT_USER = "wb_packer_user"
    # Пароль загружается из переменной окружения или используется значение по умолчанию
    DEFAULT_PASSWORD = os.environ.get("WB_PACKER_DB_PASSWORD", "DWV8ns27")
    TIMEOUT = 0.3  # Еще более уменьшенный таймаут подключения в секундах
    CONFIG_FILE = Path(__file__).parent / "db_config.json"
    
    def __init__(self, port: int = DEFAULT_PORT, database: str = DEFAULT_DATABASE, 
                 user: str = DEFAULT_USER, password: str = DEFAULT_PASSWORD):
        """
        Инициализация поиска PostgreSQL сервера
        
        Args:
            port: Порт PostgreSQL (по умолчанию 5432)
            database: Имя базы данных
            user: Имя пользователя
            password: Пароль
        """
        self.port = port
        self.database = database
        self.user = user
        self.password = password
    
    def get_local_network_ranges(self) -> List[str]:
        """
        Получить диапазоны локальной сети для сканирования
        
        Returns:
            Список подсетей в формате CIDR (например, '192.168.1.0/24')
        """
        networks = []
        try:
            # Получаем имя хоста
            hostname = socket.gethostname()
            # Получаем все IP-адреса хоста
            local_ips = socket.gethostbyname_ex(hostname)[2]
            
            for ip in local_ips:
                try:
                    # Пропускаем localhost
                    if ip.startswith('127.'):
                        continue
                    
                    # Создаем объект IP-адреса
                    ip_obj = ipaddress.IPv4Address(ip)
                    
                    # Предполагаем маску /24 для локальной сети
                    network = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                    networks.append(str(network))
                    
                except (ValueError, ipaddress.AddressValueError) as e:
                    logger.warning(f"Не удалось обработать IP {ip}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Ошибка получения локальных сетей: {e}")
        
        return networks
    
    def test_connection(self, host: str) -> bool:
        """
        Проверить подключение к PostgreSQL серверу
        Используем те же параметры, что и основное подключение

        Args:
            host: IP-адрес или имя хоста

        Returns:
            True если подключение успешно, иначе False
        """
        if PSYCOPG_VERSION == 0:
            logger.warning(f"PostgreSQL клиент не установлен, проверка {host}:{self.port} невозможна")
            return False
            
        try:
            # Пробуем подключение с реальными параметрами
            if PSYCOPG_VERSION == 3:
                conn = psycopg.connect(
                    host=host,
                    port=self.port,
                    dbname=self.database,
                    user=self.user,
                    password=self.password,
                    connect_timeout=2,
                    sslmode='disable'
                )
                conn.close()
            else:
                conn = psycopg2.connect(
                    host=host,
                    port=self.port,
                    dbname=self.database,
                    user=self.user,
                    password=self.password,
                    connect_timeout=2,
                    sslmode='disable',
                    client_encoding='UTF8'
                )
                conn.close()
            logger.info(f"✓ Успешное подключение к PostgreSQL на {host}:{self.port}")
            return True
        except Exception as e:
            error_msg = str(e).lower()
            # Ошибки, которые всё равно подтверждают наличие PostgreSQL
            auth_errors = ['authentication failed', 'password authentication failed',
                          'no pg_hba.conf entry', 'fe_sendauth', 'fatal']
            db_errors = ['does not exist', 'нет такой базы', 'database']

            if any(err in error_msg for err in auth_errors):
                logger.info(f"✓ Найден PostgreSQL сервер (ошибка аутентификации): {host}:{self.port}")
                return True
            if any(err in error_msg for err in db_errors):
                logger.info(f"✓ Найден PostgreSQL сервер (база не существует): {host}:{self.port}")
                return True

            logger.debug(f"✗ Не удалось подключиться к {host}:{self.port} - {e}")
            return False

    def check_port_open(self, host: str) -> bool:
        """
        Быстрая проверка открытости порта PostgreSQL
        
        Args:
            host: IP-адрес для проверки
            
        Returns:
            True если порт открыт, иначе False
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.TIMEOUT)
            result = sock.connect_ex((host, self.port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"Ошибка проверки порта на {host}: {e}")
            return False
    
    def get_smart_scan_order(self, network: str) -> List[str]:
        """
        Получить оптимизированный порядок сканирования адресов
        Сначала проверяем наиболее вероятные адреса
            
        Args:
            network: Сеть в формате CIDR
                
        Returns:
            Список IP-адресов в порядке приоритета
        """
        try:
            network_obj = ipaddress.IPv4Network(network)
            base_ip = str(network_obj.network_address).rsplit('.', 1)[0]
                
            # Приоритетные адреса (обычно роутеры, серверы, популярные адреса)
            priority_addresses = [
                f"{base_ip}.1",      # Обычно роутер/сервер
                f"{base_ip}.100",    # Часто используется для серверов
                f"{base_ip}.168",    # Ваш текущий сервер
                f"{base_ip}.254",    # Альтернативный адрес роутера
                f"{base_ip}.10",     # Часто используемый адрес
                f"{base_ip}.20",     # Резервный адрес
                f"{base_ip}.30",     # Резервный адрес
            ]
                
            # Фильтруем недопустимые адреса
            valid_priority = [addr for addr in priority_addresses 
                            if ipaddress.IPv4Address(addr) in network_obj]
                
            # Остальные адреса
            all_hosts = [str(host) for host in network_obj.hosts()]
            remaining = [addr for addr in all_hosts if addr not in valid_priority]
                
            # Возвращаем сначала приоритетные, затем остальные
            return valid_priority + remaining
                
        except Exception as e:
            logger.warning(f"Ошибка при создании умного порядка сканирования: {e}")
            # Возвращаем стандартный порядок
            network_obj = ipaddress.IPv4Network(network)
            return [str(host) for host in network_obj.hosts()]
        
    def scan_network_smart(self, network: str, max_workers: int = 10) -> Optional[str]:
        """
        Интеллектуальное сканирование сети - останавливается при первом найденном сервере
            
        Args:
            network: Сеть в формате CIDR
            max_workers: Максимальное количество одновременных потоков
                
        Returns:
            IP-адрес найденного сервера или None
        """
        try:
            # Получаем оптимизированный порядок адресов
            scan_order = self.get_smart_scan_order(network)
            logger.info(f"Умное сканирование сети {network} ({len(scan_order)} адресов)...")
                    
            # Ограничиваем сканирование только первыми 50 адресами для скорости
            limited_scan = scan_order[:50]
            logger.info(f"Сканируем только первые 50 наиболее вероятных адресов...")
                    
            found_server = None
            port_found_server = None  # Сервер с открытым портом но без полной аутентификации
                    
            # Используем многопоточность для быстрого сканирования
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Сначала быстро проверяем открытость порта
                future_to_host = {executor.submit(self.check_port_open, host): host for host in limited_scan}
                        
                for future in concurrent.futures.as_completed(future_to_host):
                    if found_server:  # Если уже нашли сервер, прекращаем
                        break
                            
                    host = future_to_host[future]
                    try:
                        if future.result():
                            logger.info(f"Найден открытый порт PostgreSQL на {host}")
                            port_found_server = host  # Сохраняем сервер с открытым портом
                            # Проверяем, действительно ли это PostgreSQL сервер
                            if self.test_connection(host):
                                logger.info(f"✓ Найден PostgreSQL сервер: {host}")
                                found_server = host
                                break
                    except Exception as e:
                        logger.debug(f"Ошибка при проверке {host}: {e}")
                        continue
                    
            # Если ничего не найдено в первых 50, ищем в следующих 50
            if not found_server and len(scan_order) > 50:
                next_batch = scan_order[50:100]
                if next_batch:
                    logger.info(f"Сканируем следующие 50 адресов...")
                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                        future_to_host = {executor.submit(self.check_port_open, host): host for host in next_batch}
                                
                        for future in concurrent.futures.as_completed(future_to_host):
                            if found_server:  # Если уже нашли сервер, прекращаем
                                break
                                    
                            host = future_to_host[future]
                            try:
                                if future.result():
                                    logger.info(f"Найден открытый порт PostgreSQL на {host}")
                                    port_found_server = host  # Сохраняем сервер с открытым портом
                                    if self.test_connection(host):
                                        logger.info(f"✓ Найден PostgreSQL сервер: {host}")
                                        found_server = host
                                        break
                            except Exception as e:
                                logger.debug(f"Ошибка при проверке {host}: {e}")
                                continue
                    
            # Если не нашли полноценный сервер но нашли сервер с открытым портом, используем его
            if not found_server and port_found_server:
                logger.info(f"Используем сервер с открытым портом: {port_found_server}")
                return port_found_server
                    
            return found_server
                    
        except Exception as e:
            logger.error(f"Ошибка умного сканирования сети {network}: {e}")
            return None
    
    def verify_postgresql_servers(self, hosts: List[str]) -> List[str]:
        """
        Проверить, что найденные хосты действительно являются PostgreSQL серверами
        
        Args:
            hosts: Список IP-адресов для проверки
            
        Returns:
            Список проверенных IP-адресов PostgreSQL серверов
        """
        verified = []
        
        logger.info(f"Проверка {len(hosts)} потенциальных серверов PostgreSQL...")
        
        for host in hosts:
            if self.test_connection(host):
                verified.append(host)
        
        return verified
    
    def discover(self) -> Optional[str]:
        """
        Автоматически найти PostgreSQL сервер в локальной сети
        
        Returns:
            IP-адрес найденного сервера или None
        """
        logger.info("Начало автоматического поиска PostgreSQL сервера...")
        
        # 1. Сначала проверяем сохраненный адрес с повторными попытками
        saved_host = self.load_saved_host()
        if saved_host:
            logger.info(f"Проверка сохраненного адреса: {saved_host}")
            # Пробуем подключиться несколько раз с небольшими задержками
            for attempt in range(3):
                if self.test_connection(saved_host):
                    logger.info(f"✓ Используется сохраненный адрес: {saved_host}")
                    return saved_host
                elif attempt < 2:  # Не последняя попытка
                    logger.debug(f"Попытка {attempt + 1} подключения к {saved_host} не удалась, повтор через 0.5 сек...")
                    time.sleep(0.5)  # Небольшая задержка перед повторной попыткой
                
            logger.warning(f"Сохраненный адрес {saved_host} недоступен после 3 попыток, запуск поиска...")
        
        # 2. Получаем локальные сети
        networks = self.get_local_network_ranges()
        if not networks:
            logger.error("Не удалось определить локальные сети для сканирования")
            return None
        
        logger.info(f"Найдены локальные сети для сканирования: {networks}")
        
        # 3. Сканируем все локальные сети с умным подходом
        for network in networks:
            found_host = self.scan_network_smart(network)
            if found_host:
                logger.info(f"✓ Найден и подтвержден PostgreSQL сервер: {found_host}")
                # Сохраняем найденный адрес
                self.save_host(found_host)
                return found_host
        
        logger.warning("Автопоиск не удался, используется адрес по умолчанию: 89.169.3.41")
        return "89.169.3.41"
    
    def save_host(self, host: str):
        """
        Сохранить найденный адрес сервера в файл конфигурации
        
        Args:
            host: IP-адрес сервера
        """
        try:
            config = {
                'host': host,
                'port': self.port,
                'database': self.database,
                'user': self.user
            }
            
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Конфигурация сохранена в {self.CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
    
    def load_saved_host(self) -> Optional[str]:
        """
        Загрузить сохраненный адрес сервера из файла
        
        Returns:
            IP-адрес сервера или None
        """
        try:
            if not self.CONFIG_FILE.exists():
                return None
            
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            return config.get('host')
        except Exception as e:
            logger.debug(f"Не удалось загрузить сохраненную конфигурацию: {e}")
            return None
    
    def get_all_servers(self) -> List[Dict[str, str]]:
        """
        Найти все доступные PostgreSQL серверы в сети
        
        Returns:
            Список серверов с информацией
        """
        servers = []
        
        networks = self.get_local_network_ranges()
        for network in networks:
            # Для полного сканирования используем старый метод
            found_hosts = self.scan_network_full(network)
            verified_hosts = self.verify_postgresql_servers(found_hosts)
            
            for host in verified_hosts:
                servers.append({
                    'host': host,
                    'port': self.port,
                    'database': self.database
                })
        
        return servers
    
    def scan_network_full(self, network: str, max_workers: int = 20) -> List[str]:
        """
        Полное сканирование сети (для get_all_servers)
        
        Args:
            network: Сеть в формате CIDR
            max_workers: Максимальное количество одновременных потоков
            
        Returns:
            Список IP-адресов с открытым портом PostgreSQL
        """
        found_hosts = []
        
        try:
            network_obj = ipaddress.IPv4Network(network)
            hosts = list(network_obj.hosts())
            
            logger.info(f"Полное сканирование сети {network} ({len(hosts)} адресов)...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_host = {executor.submit(self.check_port_open, str(host)): host for host in hosts}
                
                for future in concurrent.futures.as_completed(future_to_host):
                    host = future_to_host[future]
                    try:
                        if future.result():
                            host_str = str(host)
                            logger.info(f"Найден открытый порт PostgreSQL на {host_str}")
                            found_hosts.append(host_str)
                    except Exception as e:
                        logger.debug(f"Ошибка при проверке {host}: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка полного сканирования сети {network}: {e}")
        
        return found_hosts


def auto_discover_postgresql() -> Optional[str]:
    """
    Вспомогательная функция для автоматического поиска PostgreSQL сервера
    
    Returns:
        IP-адрес найденного сервера или None
    """
    discovery = PostgreSQLDiscovery()
    return discovery.discover()


if __name__ == "__main__":
    # Настройка логирования для тестирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запуск поиска
    host = auto_discover_postgresql()
    if host:
        print(f"\n✓ PostgreSQL сервер найден: {host}")
    else:
        print("\n✗ PostgreSQL сервер не найден")
