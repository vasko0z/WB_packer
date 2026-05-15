"""
Модуль для обеспечения безопасности приложения WB Packer
Содержит функции для валидации входных данных, защиты от SQL-инъекций 
и безопасной обработки путей файлов.
"""

import re
import os
import logging
from pathlib import Path
from urllib.parse import quote
import html

logger = logging.getLogger(__name__)

class SecurityValidator:
    """Класс для валидации и санитизации входных данных"""
    
    # Регулярные выражения для различных типов валидации
    BARCODE_PATTERN = re.compile(r'^[0-9A-Za-z\-_]+$')
    USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_\-\.\@]{3,50}$')
    SHIPMENT_NAME_PATTERN = re.compile(r'^[A-Za-z0-9А-Яа-яЁё_\-\.\s]{1,100}$')
    FILENAME_PATTERN = re.compile(r'^[^<>:"/\\|?*\x00-\x1F]+$')
    
    # Потенциально опасные символы и последовательности
    DANGEROUS_CHARS = [';', '&', '|', '`', '$', '(', ')', '{', '}', '[', ']', '<', '>']
    SQL_KEYWORDS = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'EXEC', 'UNION']
    
    @classmethod
    def validate_barcode(cls, barcode: str) -> tuple[bool, str]:
        """
        Валидация штрихкода
        
        Args:
            barcode: Штрихкод для проверки
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not barcode:
            return False, "Штрихкод не может быть пустым"
            
        if not isinstance(barcode, str):
            return False, "Штрихкод должен быть строкой"
            
        barcode = barcode.strip()
        
        if len(barcode) < 1 or len(barcode) > 50:
            return False, "Штрихкод должен содержать от 1 до 50 символов"
            
        if not cls.BARCODE_PATTERN.match(barcode):
            return False, "Штрихкод содержит недопустимые символы"
            
        return True, ""
    
    @classmethod
    def validate_username(cls, username: str) -> tuple[bool, str]:
        """
        Валидация имени пользователя
        
        Args:
            username: Имя пользователя для проверки
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not username:
            return False, "Имя пользователя не может быть пустым"
            
        if not isinstance(username, str):
            return False, "Имя пользователя должно быть строкой"
            
        username = username.strip()
        
        if len(username) < 3 or len(username) > 50:
            return False, "Имя пользователя должно содержать от 3 до 50 символов"
            
        if not cls.USERNAME_PATTERN.match(username):
            return False, "Имя пользователя содержит недопустимые символы"
            
        return True, ""
    
    @classmethod
    def validate_shipment_name(cls, name: str) -> tuple[bool, str]:
        """
        Валидация названия поставки
        
        Args:
            name: Название поставки для проверки
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not name:
            return False, "Название поставки не может быть пустым"
            
        if not isinstance(name, str):
            return False, "Название поставки должно быть строкой"
            
        name = name.strip()
        
        if len(name) < 1 or len(name) > 100:
            return False, "Название поставки должно содержать от 1 до 100 символов"
            
        if not cls.SHIPMENT_NAME_PATTERN.match(name):
            return False, "Название поставки содержит недопустимые символы"
            
        return True, ""
    
    @classmethod
    def sanitize_input(cls, input_str: str, max_length: int = 1000) -> str:
        """
        Санитизация входной строки
        
        Args:
            input_str: Входная строка
            max_length: Максимальная длина строки
            
        Returns:
            Очищенная строка
        """
        if input_str is None:
            return ""
            
        if not isinstance(input_str, str):
            input_str = str(input_str)
            
        # Обрезаем до максимальной длины
        if len(input_str) > max_length:
            input_str = input_str[:max_length]
            logger.warning(f"Входная строка обрезана до {max_length} символов")
            
        # Удаляем потенциально опасные символы
        for char in cls.DANGEROUS_CHARS:
            input_str = input_str.replace(char, '')
            
        # Удаляем множественные пробелы
        input_str = re.sub(r'\s+', ' ', input_str)
        
        # Удаляем управляющие символы
        input_str = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', input_str)
        
        return input_str.strip()
    
    @classmethod
    def detect_sql_injection_attempt(cls, input_str: str) -> bool:
        """
        Обнаружение потенциальной попытки SQL-инъекции
        
        Args:
            input_str: Проверяемая строка
            
        Returns:
            True если обнаружена попытка SQL-инъекции
        """
        if not input_str:
            return False
            
        input_upper = input_str.upper()
        
        # Проверяем наличие SQL ключевых слов вне контекста параметризованных запросов
        for keyword in cls.SQL_KEYWORDS:
            if keyword in input_upper:
                # Проверяем контекст - если ключевое слово не окружено кавычками
                # и не является частью допустимого значения, считаем это подозрительным
                pattern = rf"(^|\s){keyword}(\s|$)"
                if re.search(pattern, input_upper):
                    logger.warning(f"Обнаружена потенциальная SQL-инъекция: {input_str}")
                    return True
                    
        return False
    
    @classmethod
    def escape_html(cls, text: str) -> str:
        """
        Экранирование HTML для предотвращения XSS
        
        Args:
            text: Текст для экранирования
            
        Returns:
            Экранированный текст
        """
        if not text:
            return ""
        return html.escape(text, quote=True)
    
    @classmethod
    def validate_and_sanitize_text(cls, text: str, field_name: str = "текст") -> tuple[str, str]:
        """
        Комплексная валидация и санитизация текстового поля
        
        Args:
            text: Текст для обработки
            field_name: Название поля для сообщений об ошибках
            
        Returns:
            tuple: (sanitized_text, error_message)
        """
        if text is None:
            return "", ""
            
        if not isinstance(text, str):
            text = str(text)
            
        # Проверка на SQL-инъекцию
        if cls.detect_sql_injection_attempt(text):
            return "", f"Недопустимое содержимое в поле {field_name}"
            
        # Санитизация
        sanitized = cls.sanitize_input(text)
        
        return sanitized, ""

class PathSecurity:
    """Класс для безопасной обработки путей файлов"""
    
    # Разрешенные расширения файлов
    ALLOWED_EXTENSIONS = {
        '.pdf', '.xlsx', '.xls', '.txt', '.json', '.db', '.ico', '.png', '.jpg', '.jpeg'
    }
    
    # Запрещенные имена файлов
    FORBIDDEN_NAMES = {
        '..', '.', 'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    @classmethod
    def is_safe_path(cls, base_path: str, user_path: str) -> bool:
        """
        Проверка, что путь находится внутри базовой директории
        
        Args:
            base_path: Базовая директория
            user_path: Путь, предоставляемый пользователем
            
        Returns:
            True если путь безопасен
        """
        try:
            # Преобразуем пути в абсолютные
            base_path = os.path.abspath(base_path)
            user_path = os.path.abspath(os.path.join(base_path, user_path))
            
            # Проверяем, что user_path начинается с base_path
            return user_path.startswith(base_path)
        except Exception as e:
            logger.error(f"Ошибка проверки безопасности пути: {e}")
            return False
    
    @classmethod
    def validate_filename(cls, filename: str) -> tuple[bool, str]:
        """
        Валидация имени файла
        
        Args:
            filename: Имя файла для проверки
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not filename:
            return False, "Имя файла не может быть пустым"
            
        if not isinstance(filename, str):
            return False, "Имя файла должно быть строкой"
            
        filename = filename.strip()
        
        # Проверка на запрещенные имена
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in cls.FORBIDDEN_NAMES:
            return False, f"Имя файла '{filename}' запрещено"
            
        # Проверка на допустимые символы
        if not SecurityValidator.FILENAME_PATTERN.match(filename):
            return False, "Имя файла содержит недопустимые символы"
            
        # Проверка длины
        if len(filename) > 255:
            return False, "Имя файла слишком длинное"
            
        # Проверка расширения
        _, ext = os.path.splitext(filename.lower())
        if ext and ext not in cls.ALLOWED_EXTENSIONS:
            return False, f"Расширение файла '{ext}' не разрешено"
            
        return True, ""
    
    @classmethod
    def safe_join_path(cls, base_path: str, *paths) -> str:
        """
        Безопасное объединение путей с проверкой
        
        Args:
            base_path: Базовая директория
            *paths: Дополнительные части пути
            
        Returns:
            Безопасный путь или None при ошибке
        """
        try:
            # Объединяем все части пути
            full_path = os.path.join(base_path, *paths)
            
            # Проверяем безопасность пути
            if not cls.is_safe_path(base_path, full_path):
                logger.warning(f"Попытка доступа к небезопасному пути: {full_path}")
                return None
                
            return os.path.normpath(full_path)
        except Exception as e:
            logger.error(f"Ошибка при объединении путей: {e}")
            return None
    
    @classmethod
    def get_safe_app_directory(cls) -> Path:
        """
        Получение безопасной директории приложения
        
        Returns:
            Path к безопасной директории
        """
        try:
            # Используем Documents пользователя
            documents_dir = Path.home() / "Documents" / "WB_Packer"
            documents_dir.mkdir(parents=True, exist_ok=True)
            return documents_dir
        except Exception as e:
            logger.error(f"Ошибка создания директории приложения: {e}")
            # В крайнем случае используем временную директорию
            import tempfile
            return Path(tempfile.gettempdir()) / "WB_Packer"

# Создаем глобальные экземпляры для удобства использования
validator = SecurityValidator()
path_security = PathSecurity()

# Удобные функции для внешнего использования
def validate_user_input(input_data: dict) -> dict:
    """
    Валидация всех пользовательских входных данных
    
    Args:
        input_data: Словарь с пользовательскими данными
        
    Returns:
        Словарь с валидированными данными
    """
    validated_data = {}
    errors = []
    
    for key, value in input_data.items():
        if key == 'barcode':
            is_valid, error = validator.validate_barcode(value)
            if is_valid:
                validated_data[key] = validator.sanitize_input(value)
            else:
                errors.append(f"barcode: {error}")
                
        elif key == 'username':
            is_valid, error = validator.validate_username(value)
            if is_valid:
                validated_data[key] = validator.sanitize_input(value)
            else:
                errors.append(f"username: {error}")
                
        elif key == 'shipment_name':
            is_valid, error = validator.validate_shipment_name(value)
            if is_valid:
                validated_data[key] = validator.sanitize_input(value)
            else:
                errors.append(f"shipment_name: {error}")
                
        else:
            # Для других полей применяем базовую санитизацию
            sanitized = validator.sanitize_input(str(value) if value is not None else "")
            if sanitized:
                validated_data[key] = sanitized
    
    if errors:
        logger.warning(f"Ошибки валидации: {', '.join(errors)}")
    
    return validated_data, errors

def safe_file_operation(operation_func, *args, **kwargs):
    """
    Обертка для безопасных файловых операций
    
    Args:
        operation_func: Функция для выполнения
        *args: Аргументы функции
        **kwargs: Именованные аргументы
        
    Returns:
        Результат выполнения функции или None при ошибке
    """
    try:
        return operation_func(*args, **kwargs)
    except PermissionError:
        logger.error("Недостаточно прав для выполнения файловой операции")
        return None
    except FileNotFoundError:
        logger.error("Файл не найден")
        return None
    except OSError as e:
        logger.error(f"Ошибка файловой системы: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при файловой операции: {e}")
        return None