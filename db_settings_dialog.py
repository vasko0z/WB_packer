# db_settings_dialog.py
import os
import json
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QMessageBox, QComboBox, QFormLayout, QGroupBox,
    QListWidget, QListWidgetItem, QFrame, QScrollArea, QWidget, QGridLayout,
    QDateEdit, QPlainTextEdit, QTreeWidgetItem, QTabWidget, QTreeWidget, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QFont, QBrush, QColor

import database
from db_connection import get_db_type
import config
import themes
from image_check_box import ImageCheckBox
from logging_config import get_logger

# Создаем логгер для этого модуля
logger = get_logger(__name__)


class DatabaseSettingsDialog(QDialog):
    """
    Диалог настроек базы данных
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Настройки базы данных")
        self.setModal(True)
        self.resize(800, 600)

        # Получаем текущую тему из родительского окна
        if parent and hasattr(parent, 'current_theme'):
            self.current_theme = parent.current_theme
        else:
            self.current_theme = config.DEFAULT_THEME

        # Загружаем путь к папке бэкапов из настроек пользователяя
        self.backup_folder_path = self.load_backup_folder_path()

        layout = QVBoxLayout()

        # Создаем вкладки
        self.tabs = QTabWidget()

        # Вкладка "Настройки подключения"
        self.connection_tab = self.create_connection_tab()
        self.tabs.addTab(self.connection_tab, "Подключение")

        # Вкладка "Информация о базе данных"
        self.info_tab = self.create_info_tab()
        self.tabs.addTab(self.info_tab, "Информация о базе")

        # Вкладка "Бэкап и восстановление"
        self.backup_tab = self.create_backup_tab()
        self.tabs.addTab(self.backup_tab, "Бэкап и восстановление")

        # Вкладка "Очистка"
        self.cleanup_tab = self.create_cleanup_tab()
        self.tabs.addTab(self.cleanup_tab, "Очистка")

        layout.addWidget(self.tabs)

        # Кнопки
        buttons_layout = QHBoxLayout()

        self.save_btn = QPushButton("Сохранить и применить")
        self.save_btn.clicked.connect(self.save_and_apply_settings)
        buttons_layout.addWidget(self.save_btn)

        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.refresh_all)
        buttons_layout.addWidget(self.refresh_btn)

        buttons_layout.addStretch()

        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.close)
        buttons_layout.addWidget(close_button)

        layout.addLayout(buttons_layout)

        self.setLayout(layout)

        # Загружаем начальные данные
        self.refresh_all()

        # Применяем тему
        self.apply_theme()
    
    def load_backup_folder_path(self):
        """Загружает путь к папке бэкапов из файла настроек"""
        try:
            # Используем безопасную обработку путей
            from security_utils import path_security
            
            # Определяем путь к файлу настроек
            settings_dir = os.path.join(os.path.expanduser("~"), ".wb_packer")
            settings_file = os.path.join(settings_dir, "backup_settings.json")
            
            # Проверяем безопасность пути
            if not path_security.is_safe_path(settings_dir, settings_file):
                logger.warning("Небезопасный путь к файлу настроек")
                return os.path.join(os.path.expanduser("~"), "Documents", "WB_Packer_Backups")
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    path = settings.get('backup_folder_path', '')
                    # Проверяем безопасность загруженного пути
                    if path and os.path.exists(path):
                        return path
        except Exception as e:
            logger.error(f"Ошибка при загрузке пути к папке бэкапов: {e}")
        
        # Возвращаем путь по умолчанию, если не удалось загрузить
        return os.path.join(os.path.expanduser("~"), "Documents", "WB_Packer_Backups")
    
    def save_backup_folder_path(self, path):
        """Сохраняет путь к папке бэкапов в файл настроек"""
        try:
            # Используем безопасную обработку путей
            from security_utils import path_security, validator
            
            # Валидация пути
            if path:
                path = validator.sanitize_input(path)
                # Проверяем безопасность пути
                if not path_security.is_safe_path(os.path.expanduser("~"), path):
                    logger.warning("Небезопасный путь к папке бэкапов")
                    return
            
            # Создаем директорию для настроек, если она не существует
            settings_dir = os.path.join(os.path.expanduser("~"), ".wb_packer")
            os.makedirs(settings_dir, exist_ok=True)
            
            # Определяем путь к файлу настроек
            settings_file = os.path.join(settings_dir, "backup_settings.json")
            
            # Проверяем безопасность пути к файлу настроек
            if not path_security.is_safe_path(settings_dir, settings_file):
                logger.warning("Небезопасный путь к файлу настроек")
                return
            
            # Загружаем существующие настройки, если файл существует
            settings = {}
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            
            # Обновляем путь к папке бэкапов
            settings['backup_folder_path'] = path
            
            # Сохраняем настройки в файл
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Ошибка при сохранении пути к папке бэкапов: {e}")

    def create_connection_tab(self):
        """Создает вкладку с настройками подключения к базе данных"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Группа для выбора типа базы данных
        db_type_group = QGroupBox("Тип базы данных")
        db_type_layout = QVBoxLayout()

        self.db_type_combo = QComboBox()
        self.db_type_combo.addItem("PostgreSQL (сетевая)", "postgresql")
        self.db_type_combo.addItem("SQLite (локальная)", "sqlite")
        
        # Устанавливаем текущее значение
        current_db_type = config.DATABASE_TYPE
        for i in range(self.db_type_combo.count()):
            if self.db_type_combo.itemData(i) == current_db_type:
                self.db_type_combo.setCurrentIndex(i)
                break
        
        db_type_layout.addWidget(QLabel("Выберите тип подключения к базе данных:"))
        db_type_layout.addWidget(self.db_type_combo)
        
        db_type_info = QLabel(
            "• <b>PostgreSQL</b> - сетевая база данных, используется по умолчанию.\n"
            "• <b>SQLite</b> - локальная база данных, используется как резервный вариант\n"
            "  при недоступности PostgreSQL или для автономной работы."
        )
        db_type_info.setWordWrap(True)
        db_type_info.setStyleSheet("color: #666; font-size: 11px;")
        db_type_layout.addWidget(db_type_info)
        
        db_type_group.setLayout(db_type_layout)
        layout.addWidget(db_type_group)

        # Группа для настроек PostgreSQL
        self.postgresql_group = QGroupBox("Настройки PostgreSQL")
        postgresql_layout = QFormLayout()

        self.pg_host_input = QLineEdit()
        self.pg_host_input.setText(config.POSTGRESQL_HOST or "")
        self.pg_host_input.setPlaceholderText("Например: 192.168.1.158")
        postgresql_layout.addRow("Сервер:", self.pg_host_input)

        self.pg_port_input = QSpinBox()
        self.pg_port_input.setRange(1, 65535)
        self.pg_port_input.setValue(config.POSTGRESQL_PORT)
        postgresql_layout.addRow("Порт:", self.pg_port_input)

        self.pg_database_input = QLineEdit()
        self.pg_database_input.setText(config.POSTGRESQL_DATABASE)
        postgresql_layout.addRow("База данных:", self.pg_database_input)

        self.pg_user_input = QLineEdit()
        self.pg_user_input.setText(config.POSTGRESQL_USER)
        postgresql_layout.addRow("Пользователь:", self.pg_user_input)

        self.pg_password_input = QLineEdit()
        self.pg_password_input.setText(config.POSTGRESQL_PASSWORD)
        self.pg_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        postgresql_layout.addRow("Пароль:", self.pg_password_input)

        self.pg_auto_discover = ImageCheckBox("Автоматическое обнаружение сервера")
        self.pg_auto_discover.setChecked(config.POSTGRESQL_HOST is None)
        self.pg_auto_discover.setStyleSheet("QCheckBox::indicator { width: 0; height: 0; }")
        postgresql_layout.addRow(self.pg_auto_discover)

        self.postgresql_group.setLayout(postgresql_layout)
        layout.addWidget(self.postgresql_group)

        # Группа для настроек SQLite
        self.sqlite_group = QGroupBox("Настройки SQLite")
        sqlite_layout = QFormLayout()

        self.sqlite_path_input = QLineEdit()
        self.sqlite_path_input.setText(config.get_sqlite_database_path())
        self.sqlite_path_input.setReadOnly(True)
        
        sqlite_path_layout = QHBoxLayout()
        sqlite_path_layout.addWidget(self.sqlite_path_input)
        
        self.sqlite_browse_btn = QPushButton("Обзор...")
        self.sqlite_browse_btn.clicked.connect(self.browse_sqlite_path)
        sqlite_path_layout.addWidget(self.sqlite_browse_btn)
        
        sqlite_layout.addRow("Файл базы данных:", sqlite_path_layout)

        sqlite_info = QLabel(
            "SQLite база данных хранится в одном файле и не требует\n"
            "подключения к серверу. Идеально для автономной работы."
        )
        sqlite_info.setWordWrap(True)
        sqlite_info.setStyleSheet("color: #666; font-size: 11px;")
        sqlite_layout.addRow(sqlite_info)

        self.sqlite_group.setLayout(sqlite_layout)
        layout.addWidget(self.sqlite_group)

        # Группа для настроек резервирования
        fallback_group = QGroupBox("Резервирование")
        fallback_layout = QVBoxLayout()

        self.fallback_checkbox = ImageCheckBox("Автоматическое переключение на SQLite при ошибке PostgreSQL")
        self.fallback_checkbox.setChecked(config.DATABASE_FALLBACK_ENABLED)
        self.fallback_checkbox.setStyleSheet("QCheckBox::indicator { width: 0; height: 0; }")
        fallback_layout.addWidget(self.fallback_checkbox)

        fallback_info = QLabel(
            "При включении этой опции, если PostgreSQL станет недоступен,\n"
            "программа автоматически переключится на SQLite."
        )
        fallback_info.setWordWrap(True)
        fallback_info.setStyleSheet("color: #666; font-size: 11px;")
        fallback_layout.addWidget(fallback_info)

        fallback_group.setLayout(fallback_layout)
        layout.addWidget(fallback_group)

        layout.addStretch()
        widget.setLayout(layout)
        
        # Обновляем видимость групп в зависимости от выбранного типа БД
        self.db_type_combo.currentIndexChanged.connect(self.on_db_type_changed)
        self.on_db_type_changed()
        
        return widget

    def on_db_type_changed(self):
        """Обработчик изменения типа базы данных"""
        db_type = self.db_type_combo.currentData()
        self.postgresql_group.setVisible(db_type == "postgresql")
        self.sqlite_group.setVisible(db_type == "sqlite")

    def browse_sqlite_path(self):
        """Выбор файла для SQLite базы данных"""
        current_path = self.sqlite_path_input.text()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Выберите файл базы данных SQLite",
            current_path,
            "SQLite Database (*.db);;All Files (*)"
        )
        if file_path:
            self.sqlite_path_input.setText(file_path)

    def save_and_apply_settings(self):
        """Сохраняет настройки и применяет их"""
        try:
            # Собираем настройки
            settings = {
                'database_type': self.db_type_combo.currentData(),
                'postgresql_host': self.pg_host_input.text() if not self.pg_auto_discover.isChecked() else None,
                'postgresql_port': self.pg_port_input.value(),
                'postgresql_database': self.pg_database_input.text(),
                'postgresql_user': self.pg_user_input.text(),
                'postgresql_password': self.pg_password_input.text(),
                'sqlite_database': self.sqlite_path_input.text(),
                'fallback_enabled': self.fallback_checkbox.isChecked()
            }

            # Сохраняем в файл
            if config.save_db_settings(settings):
                # Применяем настройки и сбрасываем подключение
                from db_connection import apply_db_settings as apply_db_connection_settings
                apply_db_connection_settings(settings)

                QMessageBox.information(
                    self,
                    "Настройки сохранены",
                    "Настройки базы данных сохранены и применены.\n"
                )

                # Закрываем диалог
                self.accept()
            else:
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    "Не удалось сохранить настройки базы данных."
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Произошла ошибка при сохранении настроек:\n{str(e)}"
            )

    def create_info_tab(self):
        """Создает вкладку с информацией о базе данных"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Группа с информацией о базе данных
        info_group = QGroupBox("Состояние базы данных")
        info_layout = QFormLayout()
        
        self.db_size_label = QLabel("...")
        info_layout.addRow("Размер базы данных:", self.db_size_label)
        
        self.last_update_label = QLabel("...")
        info_layout.addRow("Последнее обновление:", self.last_update_label)
        
        self.tables_count_label = QLabel("...")
        info_layout.addRow("Количество таблиц:", self.tables_count_label)
        
        self.records_count_label = QLabel("...")
        info_layout.addRow("Общее количество записей:", self.records_count_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Группа с информацией о подключении
        connection_group = QGroupBox("Информация о подключении")
        connection_layout = QFormLayout()

        # Отображаем тип текущей базы данных
        self.db_type_info_label = QLabel(config.DATABASE_TYPE.upper())
        connection_layout.addRow("Тип БД:", self.db_type_info_label)

        if config.DATABASE_TYPE == "sqlite":
            # Для SQLite показываем путь к файлу
            db_path = config.get_sqlite_database_path()
            self.db_path_label = QLabel(db_path)
            self.db_path_label.setWordWrap(True)
            connection_layout.addRow("Файл:", self.db_path_label)
        else:
            # Для PostgreSQL показываем информацию о сервере
            self.db_host_label = QLabel(config.get_postgresql_host() or "Определяется...")
            connection_layout.addRow("Сервер:", self.db_host_label)

            self.db_port_label = QLabel(str(config.POSTGRESQL_PORT))
            connection_layout.addRow("Порт:", self.db_port_label)

            self.db_name_label = QLabel(config.POSTGRESQL_DATABASE)
            connection_layout.addRow("База данных:", self.db_name_label)

            self.db_user_label = QLabel(config.POSTGRESQL_USER)
            connection_layout.addRow("Пользователь:", self.db_user_label)

        connection_group.setLayout(connection_layout)
        layout.addWidget(connection_group)

        # Группа для инициализации базы данных
        init_group = QGroupBox("Инициализация базы данных")
        init_layout = QVBoxLayout()

        init_info = QLabel(
            "Если в базе данных отсутствуют необходимые таблицы или произошла ошибка при их создании,\n"
            "используйте кнопку ниже для инициализации структуры базы данных.\n\n"
            "<b>Внимание!</b> Это создаст только структуру таблиц, данные не будут затронуты."
        )
        init_info.setWordWrap(True)
        init_info.setStyleSheet("color: #666; font-size: 11px;")
        init_layout.addWidget(init_info)

        self.init_db_btn = QPushButton("Инициализировать базу данных")
        self.init_db_btn.clicked.connect(self.init_database)
        init_layout.addWidget(self.init_db_btn)

        init_group.setLayout(init_layout)
        layout.addWidget(init_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_backup_tab(self):
        """Создает вкладку с функциями бэкапа"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Группа для создания бэкапа
        backup_group = QGroupBox("Создание бэкапа")
        backup_layout = QFormLayout()
        
        self.backup_name_input = QLineEdit()
        self.backup_name_input.setPlaceholderText("Введите имя бэкапа (необязательно)")
        backup_layout.addRow("Имя бэкапа:", self.backup_name_input)
        
        self.create_backup_btn = QPushButton("Создать бэкап")
        self.create_backup_btn.clicked.connect(self.create_backup)
        backup_layout.addRow(self.create_backup_btn)
        
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # Группа для настройки папки бэкапов
        backup_folder_group = QGroupBox("Папка для бэкапов")
        backup_folder_layout = QHBoxLayout()
        
        self.backup_folder_input = QLineEdit()
        # Устанавливаем сохраненную папку бэкапов
        self.backup_folder_input.setText(self.backup_folder_path)
        backup_folder_layout.addWidget(self.backup_folder_input)
        
        self.select_backup_folder_btn = QPushButton("...")
        self.select_backup_folder_btn.clicked.connect(self.select_backup_folder)
        backup_folder_layout.addWidget(self.select_backup_folder_btn)
        
        backup_folder_group.setLayout(backup_folder_layout)
        layout.addWidget(backup_folder_group)
        
        # Группа для списка бэкапов
        backups_group = QGroupBox("Сохраненные бэкапы")
        backups_layout = QVBoxLayout()
        
        # Таблица для отображения бэкапов
        self.backups_table = QTableWidget()
        self.backups_table.setColumnCount(3)
        self.backups_table.setHorizontalHeaderLabels(["Имя", "Дата создания", "Размер"])
        header = self.backups_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        backups_layout.addWidget(self.backups_table)
        
        # Кнопки действий с бэкапами
        backup_actions_layout = QHBoxLayout()
        
        self.load_backups_btn = QPushButton("Обновить список")
        self.load_backups_btn.clicked.connect(self.load_backups)
        backup_actions_layout.addWidget(self.load_backups_btn)
        
        self.restore_backup_btn = QPushButton("Восстановить")
        self.restore_backup_btn.clicked.connect(self.restore_backup)
        backup_actions_layout.addWidget(self.restore_backup_btn)
        
        self.delete_backup_btn = QPushButton("Удалить")
        self.delete_backup_btn.clicked.connect(self.delete_backup)
        backup_actions_layout.addWidget(self.delete_backup_btn)
        
        backups_layout.addLayout(backup_actions_layout)
        backups_group.setLayout(backups_layout)
        layout.addWidget(backups_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_cleanup_tab(self):
        """Создает вкладку с функциями очистки"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Группа для очистки базы данных
        cleanup_group = QGroupBox("Очистка базы данных")
        cleanup_layout = QVBoxLayout()
        
        cleanup_info_label = QLabel(
            "Внимание! Очистка базы данных удалит все данные:\n"
            "• Все поставки (включая архивированные)\n"
            "• Все пользователяи\n"
            "• Все настройки\n\n"
            "ДАННЫЕ БУДУТ БЕЗВОЗВРАТНО УТЕРЯНЫ!"
        )
        cleanup_info_label.setWordWrap(True)
        cleanup_info_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        cleanup_layout.addWidget(cleanup_info_label)
        
        self.clear_db_btn = QPushButton("Очистить всю базу данных")
        self.clear_db_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
        """)
        self.clear_db_btn.clicked.connect(self.confirm_clear_database)
        cleanup_layout.addWidget(self.clear_db_btn)
        
        cleanup_group.setLayout(cleanup_layout)
        layout.addWidget(cleanup_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def refresh_all(self):
        """Обновляет всю информацию на вкладках"""
        self.load_database_info()
        self.load_backups()
    
    def load_database_info(self):
        """Загружает информацию о базе данных"""
        try:
            from db_connection import execute_query, DatabaseConnection
            db_type = get_db_type()

            # Получаем размер базы данных
            try:
                if db_type == "sqlite":
                    # Для SQLite получаем размер файла
                    db_path = config.get_sqlite_database_path()
                    if os.path.exists(db_path):
                        size_bytes = os.path.getsize(db_path)
                        size_str = self.format_file_size(size_bytes)
                        self.db_size_label.setText(size_str)
                    else:
                        self.db_size_label.setText("Неизвестно")
                else:
                    # Для PostgreSQL
                    size_result = execute_query(
                        "SELECT pg_size_pretty(pg_database_size(current_database()))",
                        fetchone=True
                    )
                    if size_result:
                        self.db_size_label.setText(size_result[0])
                    else:
                        self.db_size_label.setText("Неизвестно")
            except Exception as e:
                self.db_size_label.setText(f"Ошибка: {str(e)}")

            # Получаем количество таблиц
            try:
                if db_type == "sqlite":
                    tables_result = execute_query(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'",
                        fetchone=True
                    )
                else:
                    tables_result = execute_query(
                        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'",
                        fetchone=True
                    )
                if tables_result:
                    self.tables_count_label.setText(str(tables_result[0]))
                else:
                    self.tables_count_label.setText("Неизвестно")
            except Exception:
                self.tables_count_label.setText("Ошибка")

            # Получаем примерное количество записей (суммируем по основным таблицам)
            total_records = 0
            tables_to_count = ['shipments', 'shipment_items', 'boxes', 'box_items', 'users']
            for table_name in tables_to_count:
                try:
                    count_result = execute_query(
                        f"SELECT COUNT(*) FROM {table_name}",
                        fetchone=True
                    )
                    if count_result:
                        total_records += count_result[0]
                except Exception:
                    # Если таблица не существует или возникла ошибка, пропускаем
                    continue

            self.records_count_label.setText(str(total_records))

            # Для даты последнего обновления используем текущее время как признак активности
            self.last_update_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        except Exception as e:
            self.db_size_label.setText(f"Ошибка: {str(e)}")
            self.tables_count_label.setText("Ошибка")
            self.records_count_label.setText("Ошибка")
            self.last_update_label.setText("Ошибка")

    def init_database(self):
        """Инициализирует базу данных (создает структуру таблиц)"""
        # Показываем диалог подтверждения
        confirm = QMessageBox.question(
            self,
            "Подтверждение инициализации",
            "Вы уверены, что хотите инициализировать базу данных?\n\n"
            "Будут созданы все необходимые таблицы и индексы.\n"
            "Существующие данные НЕ будут затронуты.\n\n"
            "Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            # Показываем индикатор выполнения
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("Инициализация базы данных")
            progress_dialog.setText("Выполняется инициализация базы данных...\nПожалуйста, подождите.")
            progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
            progress_dialog.show()

            # Вызываем функцию инициализации базы данных
            import database
            database.init_db()

            # Закрываем индикатор выполнения
            progress_dialog.close()

            # Показываем сообщение об успехе
            QMessageBox.information(
                self,
                "Инициализация завершена",
                "База данных успешно инициализирована.\n"
                "Все необходимые таблицы созданы."
            )

            # Обновляем информацию о базе данных
            self.load_database_info()

        except Exception as e:
            # Показываем сообщение об ошибке
            QMessageBox.critical(
                self,
                "Ошибка инициализации",
                f"Произошла ошибка при инициализации базы данных:\n{str(e)}"
            )
            logger.error(f"Ошибка при инициализации базы данных: {e}", exc_info=True)

    def select_backup_folder(self):
        """Выбирает папку для бэкапов"""
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку для бэкапов",
            self.backup_folder_input.text()
        )
        if folder:
            self.backup_folder_input.setText(folder)
            # Сохраняем путь к папке бэкапов
            self.backup_folder_path = folder
            self.save_backup_folder_path(folder)
    
    def create_backup(self):
        """Создает бэкап базы данных"""
        try:
            backup_name = self.backup_name_input.text().strip()
            if not backup_name:
                backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            backup_folder = self.backup_folder_input.text().strip()
            if not backup_folder:
                backup_folder = os.path.join(os.path.expanduser("~"), "Documents", "WB_Packer_Backups")
            
            # Обновляем путь к папке бэкапов
            self.backup_folder_path = backup_folder
            
            # Создаем папку, если она не существует
            os.makedirs(backup_folder, exist_ok=True)
            
            # Формируем имя файла бэкапа
            backup_filename = f"{backup_name}.json"
            backup_path = os.path.join(backup_folder, backup_filename)
            
            # Создаем резервную копию данных
            backup_data = self.export_database_data()
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)
            
            QMessageBox.information(
                self,
                "Бэкап создан",
                f"Бэкап успешно создан:\n{backup_path}"
            )
            
            # Обновляем список бэкапов
            self.load_backups()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка создания бэкапа",
                f"Не удалось создать бэкап:\n{str(e)}"
            )
    
    def export_database_data(self):
        """Экспортирует все данные из базы данных"""
        from db_connection import execute_query
        
        backup_data = {}
        
        # Экспортируем пользователяей
        users = execute_query("SELECT * FROM users", fetchall=True)
        # Преобразуем все данные в строки, чтобы избежать проблем с сериализацией
        backup_data['users'] = [tuple(str(field) if field is not None else None for field in row) for row in users] if users else []
        
        # Экспортируем настройки приложения
        app_settings = execute_query("SELECT * FROM app_settings", fetchall=True)
        backup_data['app_settings'] = [tuple(str(field) if field is not None else None for field in row) for row in app_settings] if app_settings else []
        
        # Экспортируем состояния окон
        window_states = execute_query("SELECT * FROM window_state", fetchall=True)
        backup_data['window_states'] = [tuple(str(field) if field is not None else None for field in row) for row in window_states] if window_states else []
        
        # Экспортируем поставки
        shipments = execute_query("SELECT * FROM shipments", fetchall=True)
        backup_data['shipments'] = [tuple(str(field) if field is not None else None for field in row) for row in shipments] if shipments else []
        
        # Экспортируем товары поставок
        shipment_items = execute_query("SELECT * FROM shipment_items", fetchall=True)
        backup_data['shipment_items'] = [tuple(str(field) if field is not None else None for field in row) for row in shipment_items] if shipment_items else []
        
        # Экспортируем коробки
        boxes = execute_query("SELECT * FROM boxes", fetchall=True)
        backup_data['boxes'] = [tuple(str(field) if field is not None else None for field in row) for row in boxes] if boxes else []
        
        # Экспортируем товары в коробках
        box_items = execute_query("SELECT * FROM box_items", fetchall=True)
        backup_data['box_items'] = [tuple(str(field) if field is not None else None for field in row) for row in box_items] if box_items else []
        
        # Экспортируем сессии пользователяей (если таблица существует)
        try:
            # Проверяем существование таблицы user_sessions
            execute_query("SELECT 1 FROM user_sessions LIMIT 1", fetchone=True)
            user_sessions = execute_query("SELECT * FROM user_sessions", fetchall=True)
            backup_data['user_sessions'] = [tuple(str(field) if field is not None else None for field in row) for row in user_sessions] if user_sessions else []
        except Exception as e:
            # Таблица user_sessions может не существовать
            if "отношение \"user_sessions\" не существует" not in str(e):
                logger.error(f"Ошибка при экспорте сессий пользователяей: {e}")
            backup_data['user_sessions'] = []
        
        return backup_data
    
    def load_backups(self):
        """Загружает список доступных бэкапов"""
        self.backups_table.setRowCount(0)
        
        backup_folder = self.backup_folder_input.text().strip()
        if not backup_folder:
            backup_folder = os.path.join(os.path.expanduser("~"), "Documents", "WB_Packer_Backups")
            
        # Обновляем путь к папке бэкапов
        self.backup_folder_path = backup_folder
        
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder, exist_ok=True)
            return
        
        # Ищем все JSON файлы в папке бэкапов
        backup_files = [f for f in os.listdir(backup_folder) if f.endswith('.json')]
        
        for i, filename in enumerate(backup_files):
            filepath = os.path.join(backup_folder, filename)
            file_size = os.path.getsize(filepath)
            file_size_str = self.format_file_size(file_size)
            
            # Извлекаем дату из имени файла (если формат соответствует)
            creation_date = self.extract_date_from_filename(filename)
            
            # Добавляем строку в таблицу
            self.backups_table.setRowCount(i + 1)
            
            name_item = QTableWidgetItem(filename)
            date_item = QTableWidgetItem(creation_date)
            size_item = QTableWidgetItem(file_size_str)
            
            # Запрещаем редактирование
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            # Сохраняем путь к файлу в user data
            name_item.setData(Qt.ItemDataRole.UserRole, filepath)
            
            self.backups_table.setItem(i, 0, name_item)
            self.backups_table.setItem(i, 1, date_item)
            self.backups_table.setItem(i, 2, size_item)
    
    def format_file_size(self, size_bytes):
        """Форматирует размер файла в удобочитаемый вид"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / (1024**2):.1f} MB"
        else:
            return f"{size_bytes / (1024**3):.1f} GB"
    
    def extract_date_from_filename(self, filename):
        """Извлекает дату из имени файла бэкапа"""
        try:
            # Пытаемся извлечь дату из формата backup_YYYYMMDD_HHMMSS.json
            import re
            match = re.search(r'_(\d{8})_(\d{6})', filename)
            if match:
                date_str = match.group(1)  # YYYYMMDD
                time_str = match.group(2)  # HHMMSS
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
                return formatted_date
        except (ValueError, AttributeError):
            pass
        
        # Если не удалось извлечь дату из имени файла, возвращаем дату модификации
        try:
            filepath = os.path.join(self.backup_folder_path, filename)
            timestamp = os.path.getmtime(filepath)
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, ValueError):
            return "Неизвестно"
    
    def restore_backup(self):
        """Восстанавливает базу данных из бэкапа"""
        current_row = self.backups_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите бэкап для восстановления!")
            return
        
        item = self.backups_table.item(current_row, 0)
        backup_path = item.data(Qt.ItemDataRole.UserRole)
        
        if not backup_path or not os.path.exists(backup_path):
            QMessageBox.critical(self, "Ошибка", "Файл бэкапа не найден!")
            return
        
        reply = QMessageBox.question(
            self,
            "Подтверждение восстановления",
            f"Вы уверены, что хотите восстановить базу данных из бэкапа?\n\n"
            f"Файл: {os.path.basename(backup_path)}\n\n"
            "Это заменит все текущие данные в базе!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.import_database_data(backup_path)
                QMessageBox.information(
                    self,
                    "Восстановление завершено",
                    "База данных успешно восстановлена из бэкапа!\n"
                    "Рекомендуется перезапустить приложение для корректной работы."
                )
                
                # Обновляем информацию о базе данных
                self.load_database_info()
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Ошибка восстановления",
                    f"Не удалось восстановить базу данных:\n{str(e)}"
                )
    
    def import_database_data(self, backup_path):
        """Импортирует данные в базу данных из бэкапа"""
        from db_connection import execute_query, execute_many, get_db_type

        # Определяем тип БД для правильного формата параметров
        db_type = get_db_type()
        use_postgresql = db_type != "sqlite"

        # Сначала очищаем базу данных
        if not database.clear_database():
            raise Exception("Не удалось очистить базу данных перед восстановлением")
        
        # Загружаем данные из бэкапа
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        # Восстанавливаем пользователяей
        if 'users' in backup_data and backup_data['users']:
            # Обрабатываем данные, чтобы избежать проблем с форматированием
            processed_users = []
            for user_row in backup_data['users']:
                # Пропускаем id (первое поле) при восстановлении, так как это SERIAL
                processed_row = []
                for i, value in enumerate(user_row):
                    if i == 0:  # Пропускаем id
                        continue
                    if value is None:
                        processed_row.append(None)
                    else:
                        # Преобразуем все значения в строки, чтобы избежать проблем с форматированием
                        try:
                            processed_row.append(str(value))
                        except Exception:
                            # Если не удается преобразовать в строку, используем repr()
                            processed_row.append(repr(value))
                # Удаляем лишний параметр '👤' из processed_row, если он есть
                if len(processed_row) > 14 and processed_row[1] == '👤':
                    # Удаляем второй элемент (с индексом 1), который содержит '👤'
                    processed_row.pop(1)
                processed_users.append(tuple(processed_row))
            
            try:
                # Проверяем, есть ли колонка button_colors в базе
                from db_connection import get_connection, get_db_type
                conn = get_connection()
                cursor = conn.cursor()
                db_type = get_db_type()
                if db_type == "sqlite":
                    cursor.execute("PRAGMA table_info(users)")
                    columns = [col[1] for col in cursor.fetchall()]
                else:
                    # PostgreSQL: используем information_schema
                    cursor.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'users'
                    """)
                    columns = [col[0] for col in cursor.fetchall()]
                has_button_colors = 'button_colors' in columns
                conn.close()

                if has_button_colors:
                    if use_postgresql:
                        execute_many(
                            "INSERT INTO users (username, font_size, label_font_size, theme, ok_sound, error_sound, tone_sound, "
                            "shipment_columns_width, box_columns_width, main_splitter_sizes, window_width, window_height, "
                            "button_primary_color, button_success_color, button_warning_color, button_danger_color, "
                            "moysklad_token, moysklad_stores, moysklad_enabled, shipment_locking_enabled, "
                            "article_column_visible, name_column_visible, total_qty_column_visible, stock_column_visible, hide_completed_items, "
                            "colored_buttons, cached_server_ip, button_colors) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                            "ON CONFLICT (username) DO UPDATE SET "
                            "font_size = EXCLUDED.font_size, label_font_size = EXCLUDED.label_font_size, "
                            "theme = EXCLUDED.theme, ok_sound = EXCLUDED.ok_sound, error_sound = EXCLUDED.error_sound, tone_sound = EXCLUDED.tone_sound, "
                            "shipment_columns_width = EXCLUDED.shipment_columns_width, box_columns_width = EXCLUDED.box_columns_width, "
                            "main_splitter_sizes = EXCLUDED.main_splitter_sizes, window_width = EXCLUDED.window_width, "
                            "window_height = EXCLUDED.window_height, button_primary_color = EXCLUDED.button_primary_color, "
                            "button_success_color = EXCLUDED.button_success_color, button_warning_color = EXCLUDED.button_warning_color, "
                            "button_danger_color = EXCLUDED.button_danger_color, "
                            "moysklad_token = EXCLUDED.moysklad_token, moysklad_stores = EXCLUDED.moysklad_stores, "
                            "moysklad_enabled = EXCLUDED.moysklad_enabled, shipment_locking_enabled = EXCLUDED.shipment_locking_enabled, "
                            "article_column_visible = EXCLUDED.article_column_visible, "
                            "name_column_visible = EXCLUDED.name_column_visible, "
                            "total_qty_column_visible = EXCLUDED.total_qty_column_visible, "
                            "stock_column_visible = EXCLUDED.stock_column_visible, "
                            "hide_completed_items = EXCLUDED.hide_completed_items, "
                            "colored_buttons = EXCLUDED.colored_buttons, "
                            "cached_server_ip = EXCLUDED.cached_server_ip, "
                            "button_colors = COALESCE(EXCLUDED.button_colors, '')",
                            processed_users
                        )
                    else:
                        execute_many(
                            "INSERT INTO users (username, font_size, label_font_size, theme, ok_sound, error_sound, tone_sound, "
                            "shipment_columns_width, box_columns_width, main_splitter_sizes, window_width, window_height, "
                            "button_primary_color, button_success_color, button_warning_color, button_danger_color, "
                            "moysklad_token, moysklad_stores, moysklad_enabled, shipment_locking_enabled, "
                            "article_column_visible, name_column_visible, total_qty_column_visible, stock_column_visible, hide_completed_items, "
                            "colored_buttons, cached_server_ip, button_colors) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                            "ON CONFLICT (username) DO UPDATE SET "
                            "font_size = EXCLUDED.font_size, label_font_size = EXCLUDED.label_font_size, "
                            "theme = EXCLUDED.theme, ok_sound = EXCLUDED.ok_sound, error_sound = EXCLUDED.error_sound, tone_sound = EXCLUDED.tone_sound, "
                            "shipment_columns_width = EXCLUDED.shipment_columns_width, box_columns_width = EXCLUDED.box_columns_width, "
                            "main_splitter_sizes = EXCLUDED.main_splitter_sizes, window_width = EXCLUDED.window_width, "
                            "window_height = EXCLUDED.window_height, button_primary_color = EXCLUDED.button_primary_color, "
                            "button_success_color = EXCLUDED.button_success_color, button_warning_color = EXCLUDED.button_warning_color, "
                            "button_danger_color = EXCLUDED.button_danger_color, "
                            "moysklad_token = EXCLUDED.moysklad_token, moysklad_stores = EXCLUDED.moysklad_stores, "
                            "moysklad_enabled = EXCLUDED.moysklad_enabled, shipment_locking_enabled = EXCLUDED.shipment_locking_enabled, "
                            "article_column_visible = EXCLUDED.article_column_visible, "
                            "name_column_visible = EXCLUDED.name_column_visible, "
                            "total_qty_column_visible = EXCLUDED.total_qty_column_visible, "
                            "stock_column_visible = EXCLUDED.stock_column_visible, "
                            "hide_completed_items = EXCLUDED.hide_completed_items, "
                            "colored_buttons = EXCLUDED.colored_buttons, "
                            "cached_server_ip = EXCLUDED.cached_server_ip, "
                            "button_colors = COALESCE(EXCLUDED.button_colors, '')",
                            processed_users
                        )
                else:
                    # Для старых баз без button_colors - выбираем только существующие колонки
                    # Старая схема (23 колонки): username, font_size, label_font_size, theme, ok_sound, error_sound,
                    # shipment_columns_width, box_columns_width, main_splitter_sizes, window_width, window_height,
                    # button_primary_color, button_success_color, button_warning_color, button_danger_color,
                    # moysklad_token, moysklad_stores, moysklad_enabled, shipment_locking_enabled,
                    # article_column_visible, name_column_visible, stock_column_visible, cached_server_ip
                    # Новые данные (27 значений): [0-20]=старые, [21]=total_qty_column_visible(новая), [22]=stock_column_visible,
                    # [23]=hide_completed_items(новая), [24]=colored_buttons(новая), [25]=cached_server_ip, [26]=button_colors(новая)
                    processed_users_old = []
                    for user_tuple in processed_users:
                        # Берём первые 21 значение + stock_column_visible[22] + cached_server_ip[25]
                        old_tuple = user_tuple[:21] + (user_tuple[22] if len(user_tuple) > 22 else '',) + (user_tuple[25] if len(user_tuple) > 25 else '',)
                        processed_users_old.append(old_tuple)
                    
                    if use_postgresql:
                        execute_many(
                            "INSERT INTO users (username, font_size, label_font_size, theme, ok_sound, error_sound, "
                            "shipment_columns_width, box_columns_width, main_splitter_sizes, window_width, window_height, "
                            "button_primary_color, button_success_color, button_warning_color, button_danger_color, "
                            "moysklad_token, moysklad_stores, moysklad_enabled, shipment_locking_enabled, "
                            "article_column_visible, name_column_visible, stock_column_visible, cached_server_ip) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                            "ON CONFLICT (username) DO UPDATE SET "
                            "font_size = EXCLUDED.font_size, label_font_size = EXCLUDED.label_font_size, "
                            "theme = EXCLUDED.theme, ok_sound = EXCLUDED.ok_sound, error_sound = EXCLUDED.error_sound, "
                            "shipment_columns_width = EXCLUDED.shipment_columns_width, box_columns_width = EXCLUDED.box_columns_width, "
                            "main_splitter_sizes = EXCLUDED.main_splitter_sizes, window_width = EXCLUDED.window_width, "
                            "window_height = EXCLUDED.window_height, button_primary_color = EXCLUDED.button_primary_color, "
                            "button_success_color = EXCLUDED.button_success_color, button_warning_color = EXCLUDED.button_warning_color, "
                            "button_danger_color = EXCLUDED.button_danger_color, "
                            "moysklad_token = EXCLUDED.moysklad_token, moysklad_stores = EXCLUDED.moysklad_stores, "
                            "moysklad_enabled = EXCLUDED.moysklad_enabled, shipment_locking_enabled = EXCLUDED.shipment_locking_enabled, "
                            "article_column_visible = EXCLUDED.article_column_visible, "
                            "name_column_visible = EXCLUDED.name_column_visible, "
                            "stock_column_visible = EXCLUDED.stock_column_visible, "
                            "cached_server_ip = EXCLUDED.cached_server_ip",
                            processed_users_old
                        )
                    else:
                        execute_many(
                            "INSERT INTO users (username, font_size, label_font_size, theme, ok_sound, error_sound, "
                            "shipment_columns_width, box_columns_width, main_splitter_sizes, window_width, window_height, "
                            "button_primary_color, button_success_color, button_warning_color, button_danger_color, "
                            "moysklad_token, moysklad_stores, moysklad_enabled, shipment_locking_enabled, "
                            "article_column_visible, name_column_visible, stock_column_visible, cached_server_ip) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                            "ON CONFLICT (username) DO UPDATE SET "
                            "font_size = EXCLUDED.font_size, label_font_size = EXCLUDED.label_font_size, "
                            "theme = EXCLUDED.theme, ok_sound = EXCLUDED.ok_sound, error_sound = EXCLUDED.error_sound, "
                            "shipment_columns_width = EXCLUDED.shipment_columns_width, box_columns_width = EXCLUDED.box_columns_width, "
                            "main_splitter_sizes = EXCLUDED.main_splitter_sizes, window_width = EXCLUDED.window_width, "
                            "window_height = EXCLUDED.window_height, button_primary_color = EXCLUDED.button_primary_color, "
                            "button_success_color = EXCLUDED.button_success_color, button_warning_color = EXCLUDED.button_warning_color, "
                            "button_danger_color = EXCLUDED.button_danger_color, "
                            "moysklad_token = EXCLUDED.moysklad_token, moysklad_stores = EXCLUDED.moysklad_stores, "
                            "moysklad_enabled = EXCLUDED.moysklad_enabled, shipment_locking_enabled = EXCLUDED.shipment_locking_enabled, "
                            "article_column_visible = EXCLUDED.article_column_visible, "
                            "name_column_visible = EXCLUDED.name_column_visible, "
                            "stock_column_visible = EXCLUDED.stock_column_visible, "
                            "cached_server_ip = EXCLUDED.cached_server_ip",
                            processed_users_old
                        )
            except TypeError as e:
                if "not all arguments converted during string formatting" in str(e):
                    logger.error(f"Ошибка форматирования параметров при восстановлении пользователяей: {e}")
                    logger.error(f"Список обработанных пользователяьских данных: {processed_users}")
                    raise
                else:
                    logger.error(f"Ошибка при восстановлении пользователяей: {e}")
                    raise
            except Exception as e:
                logger.error(f"Ошибка при восстановлении пользователяей: {e}")
                raise
        
        # Восстанавливаем настройки приложения
        if 'app_settings' in backup_data and backup_data['app_settings']:
            # Обрабатываем данные, чтобы избежать проблем с форматированием
            processed_app_settings = []
            for setting_row in backup_data['app_settings']:
                processed_row = []
                for value in setting_row:
                    if value is None:
                        processed_row.append(None)
                    else:
                        # Преобразуем все значения в строки, чтобы избежать проблем с форматированием
                        try:
                            processed_row.append(str(value))
                        except Exception:
                            # Если не удается преобразовать в строку, используем repr()
                            processed_row.append(repr(value))
                processed_app_settings.append(tuple(processed_row))
            
            try:
                if use_postgresql:
                    execute_many(
                        "INSERT INTO app_settings (key, value) VALUES (%s, %s) "
                        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                        processed_app_settings
                    )
                else:
                    execute_many(
                        "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                        processed_app_settings
                    )
            except TypeError as e:
                if "not all arguments converted during string formatting" in str(e):
                    logger.error(f"Ошибка форматирования параметров при восстановлении настроек приложения: {e}")
                    logger.error(f"Список обработанных настроек: {processed_app_settings}")
                    raise
                else:
                    logger.error(f"Ошибка при восстановлении настроек приложения: {e}")
                    raise
            except Exception as e:
                logger.error(f"Ошибка при восстановлении настроек приложения: {e}")
                raise
        
        # Восстанавливаем состояния окон
        if 'window_states' in backup_data and backup_data['window_states']:
            # Обрабатываем данные, чтобы избежать проблем с форматированием
            processed_window_states = []
            for state_row in backup_data['window_states']:
                processed_row = []
                for value in state_row:
                    if value is None:
                        processed_row.append(None)
                    else:
                        # Преобразуем все значения в строки, чтобы избежать проблем с форматированием
                        try:
                            processed_row.append(str(value))
                        except Exception:
                            # Если не удается преобразовать в строку, используем repr()
                            processed_row.append(repr(value))
                processed_window_states.append(tuple(processed_row))
            
            try:
                if use_postgresql:
                    execute_many(
                        "INSERT INTO window_state (key, value) VALUES (%s, %s) "
                        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                        processed_window_states
                    )
                else:
                    execute_many(
                        "INSERT INTO window_state (key, value) VALUES (?, ?) "
                        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                        processed_window_states
                    )
            except TypeError as e:
                if "not all arguments converted during string formatting" in str(e):
                    logger.error(f"Ошибка форматирования параметров при восстановлении состояний окон: {e}")
                    logger.error(f"Список обработанных состояний окон: {processed_window_states}")
                    raise
                else:
                    logger.error(f"Ошибка при восстановлении состояний окон: {e}")
                    raise
            except Exception as e:
                logger.error(f"Ошибка при восстановлении состояний окон: {e}")
                raise
        
        # Восстанавливаем поставки
        if 'shipments' in backup_data and backup_data['shipments']:
            # Обрабатываем данные, чтобы избежать проблем с форматированием
            processed_shipments = []
            for shipment_row in backup_data['shipments']:
                # Пропускаем id (первое поле) при восстановлении, так как это SERIAL
                processed_row = []
                for i, value in enumerate(shipment_row):
                    if i == 0:  # Пропускаем id
                        continue
                    if value is None:
                        processed_row.append(None)
                    else:
                        # Преобразуем все значения в строки, чтобы избежать проблем с форматированием
                        try:
                            processed_row.append(str(value))
                        except Exception:
                            # Если не удается преобразовать в строку, используем repr()
                            processed_row.append(repr(value))
                processed_shipments.append(tuple(processed_row))
            
            try:
                if use_postgresql:
                    execute_many(
                        "INSERT INTO shipments (destination_name, font_size, label_font_size, theme, removed_items, "
                        "parent_group, properties, archived, archived_date, archived_by) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (destination_name) DO UPDATE SET "
                        "font_size = EXCLUDED.font_size, label_font_size = EXCLUDED.label_font_size, "
                        "theme = EXCLUDED.theme, removed_items = EXCLUDED.removed_items, parent_group = EXCLUDED.parent_group, "
                        "properties = EXCLUDED.properties, archived = EXCLUDED.archived, "
                        "archived_date = EXCLUDED.archived_date, archived_by = EXCLUDED.archived_by",
                        processed_shipments
                    )
                else:
                    execute_many(
                        "INSERT INTO shipments (destination_name, font_size, label_font_size, theme, removed_items, "
                        "parent_group, properties, archived, archived_date, archived_by) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT (destination_name) DO UPDATE SET "
                        "font_size = EXCLUDED.font_size, label_font_size = EXCLUDED.label_font_size, "
                        "theme = EXCLUDED.theme, removed_items = EXCLUDED.removed_items, parent_group = EXCLUDED.parent_group, "
                        "properties = EXCLUDED.properties, archived = EXCLUDED.archived, "
                        "archived_date = EXCLUDED.archived_date, archived_by = EXCLUDED.archived_by",
                        processed_shipments
                    )
            except TypeError as e:
                if "not all arguments converted during string formatting" in str(e):
                    logger.error(f"Ошибка форматирования параметров при восстановлении поставок: {e}")
                    logger.error(f"Список обработанных поставок: {processed_shipments}")
                    raise
                else:
                    logger.error(f"Ошибка при восстановлении поставок: {e}")
                    raise
            except Exception as e:
                logger.error(f"Ошибка при восстановлении поставок: {e}")
                raise
        
        # Восстанавливаем товары поставок
        if 'shipment_items' in backup_data and backup_data['shipment_items']:
            # Получаем маппинг между старыми и новыми ID поставок
            shipment_mapping = {}
            all_old_shipment_ids = set()
            for item_row in backup_data['shipment_items']:
                old_shipment_id = item_row[1] # shipment_id - второй элемент (после id)
                all_old_shipment_ids.add(old_shipment_id)
            
            # Для каждого старого ID поставки находим новое имя поставки, а затем получим новый ID
            for old_shipment_id in all_old_shipment_ids:
                # Получаем имя поставки по старому ID из бэкапа
                old_shipment_data = None
                for shipment_row in backup_data['shipments']:
                    if str(shipment_row[0]) == str(old_shipment_id):  # id - первый элемент
                        old_shipment_data = shipment_row
                        break
                if old_shipment_data:
                    destination_name = old_shipment_data[1]  # destination_name - второй элемент
                    # Получаем новый ID по новому имени
                    new_shipment_result = execute_query(
                        "SELECT id FROM shipments WHERE destination_name = %s",
                        (destination_name,),
                        fetchone=True
                    )
                    if new_shipment_result:
                        shipment_mapping[str(old_shipment_id)] = new_shipment_result[0]
                    else:
                        # Если не нашли новый ID, оставляем None
                        shipment_mapping[str(old_shipment_id)] = None
            
            # Обрабатываем данные, чтобы избежать проблем с форматированием
            processed_shipment_items = []
            for item_row in backup_data['shipment_items']:
                # Пропускаем id (первое поле) при восстановлении, так как это SERIAL
                processed_row = []
                for i, value in enumerate(item_row):
                    if i == 0:  # Пропускаем id
                        continue
                    if i == 1:  # shipment_id - второй элемент, нужно заменить на новый ID
                        old_shipment_id = str(value)
                        new_shipment_id = shipment_mapping.get(old_shipment_id, value)
                        processed_row.append(str(new_shipment_id) if new_shipment_id is not None else str(value))
                    else:
                        if value is None:
                            processed_row.append(None)
                        else:
                            # Преобразуем все значения в строки, чтобы избежать проблем с форматированием
                            try:
                                processed_row.append(str(value))
                            except Exception:
                                # Если не удается преобразовать в строку, используем repr()
                                processed_row.append(repr(value))
                processed_shipment_items.append(tuple(processed_row))
            
            try:
                # Для shipment_items используем INSERT без ON CONFLICT, так как нет уникального ограничения
                if use_postgresql:
                    execute_many(
                        "INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        processed_shipment_items
                    )
                else:
                    execute_many(
                        "INSERT INTO shipment_items (shipment_id, barcode, sku, total_qty, allocated_qty) "
                        "VALUES (?, ?, ?, ?, ?)",
                        processed_shipment_items
                    )
            except TypeError as e:
                if "not all arguments converted during string formatting" in str(e):
                    logger.error(f"Ошибка форматирования параметров при восстановлении товаров поставок: {e}")
                    logger.error(f"Список обработанных товаров поставок: {processed_shipment_items}")
                    raise
                else:
                    logger.error(f"Ошибка при восстановлении товаров поставок: {e}")
                    raise
            except Exception as e:
                logger.error(f"Ошибка при восстановлении товаров поставок: {e}")
                raise
        
        # Восстанавливаем коробки
        if 'boxes' in backup_data and backup_data['boxes']:
            # Обрабатываем данные, чтобы избежать проблем с форматированием
            processed_boxes = []
            for box_row in backup_data['boxes']:
                # Пропускаем id (первое поле) при восстановлении, так как это SERIAL
                processed_row = []
                for i, value in enumerate(box_row):
                    if i == 0:  # Пропускаем id
                        continue
                    if i == 1:  # shipment_id - второй элемент, нужно сопоставить с новым ID
                        old_shipment_id = str(value)
                        # Получаем имя поставки по старому ID
                        old_shipment_data = None
                        for shipment_row in backup_data['shipments']:
                            if str(shipment_row[0]) == str(old_shipment_id):  # id - первый элемент
                                old_shipment_data = shipment_row
                                break
                        new_shipment_id = value  # по умолчанию оставляем старое значение
                        if old_shipment_data:
                            destination_name = old_shipment_data[1]  # destination_name - второй элемент
                            # Получаем новый ID по новому имени
                            new_shipment_result = execute_query(
                                "SELECT id FROM shipments WHERE destination_name = %s",
                                (destination_name,),
                                fetchone=True
                            )
                            if new_shipment_result:
                                new_shipment_id = new_shipment_result[0]
                        processed_row.append(str(new_shipment_id) if new_shipment_id is not None else str(value))
                    else:
                        if value is None:
                            processed_row.append(None)
                        else:
                            # Преобразуем все значения в строки, чтобы избежать проблем с форматированием
                            try:
                                processed_row.append(str(value))
                            except Exception:
                                # Если не удается преобразовать в строку, используем repr()
                                processed_row.append(repr(value))
                processed_boxes.append(tuple(processed_row))
            
            try:
                # Для boxes используем INSERT без ON CONFLICT, так как нет уникального ограничения
                if use_postgresql:
                    execute_many(
                        "INSERT INTO boxes (shipment_id, box_id, is_current) "
                        "VALUES (%s, %s, %s)",
                        processed_boxes
                    )
                else:
                    execute_many(
                        "INSERT INTO boxes (shipment_id, box_id, is_current) "
                        "VALUES (?, ?, ?)",
                        processed_boxes
                    )
            except TypeError as e:
                if "not all arguments converted during string formatting" in str(e):
                    logger.error(f"Ошибка��б��а форматирования параметров при восстановлении коробок: {e}")
                    logger.error(f"Список обработанных коробок: {processed_boxes}")
                    raise
                else:
                    logger.error(f"Ошибка при восстановлении коробок: {e}")
                    raise
            except Exception as e:
                logger.error(f"Ошибка при восстановлении коробок: {e}")
                raise
        
        # Восстанавливаем товары в коробках
        if 'box_items' in backup_data and backup_data['box_items']:
            # Обрабатываем данные, чтобы избежать проблем с форматированием
            processed_box_items = []
            for item_row in backup_data['box_items']:
                # Пропускаем id (первое поле) при восстановлении, так как это SERIAL
                processed_row = []
                for i, value in enumerate(item_row):
                    if i == 0:  # Пропускаем id
                        continue
                    if i == 1:  # box_id - второй элемент, нужно сопоставить с новым ID
                        old_box_id = str(value)
                        # Нужно найти новый ID коробки, сопоставив по shipment_id и box_id
                        old_box_data = None
                        for box_row in backup_data['boxes']:
                            if str(box_row[0]) == str(old_box_id):  # id - первый элемент
                                old_box_data = box_row
                                break
                        new_box_id = value  # по умолчанию оставляем старое значение
                        if old_box_data:
                            old_shipment_id = str(old_box_data[1])  # shipment_id - второй элемент
                            box_id_str = old_box_data[2]  # box_id - третий элемент
                            # Получаем имя поставки по старому ID
                            old_shipment_data = None
                            for shipment_row in backup_data['shipments']:
                                if str(shipment_row[0]) == str(old_shipment_id):  # id - первый элемент
                                    old_shipment_data = shipment_row
                                    break
                            if old_shipment_data:
                                destination_name = old_shipment_data[1]  # destination_name - второй элемент
                                # Получаем новый ID по новому имени
                                new_shipment_result = execute_query(
                                    "SELECT id FROM shipments WHERE destination_name = %s",
                                    (destination_name,),
                                    fetchone=True
                                )
                                if new_shipment_result:
                                    new_shipment_id = new_shipment_result[0]
                                    # Теперь ищем новый ID коробки по новому shipment_id и старому box_id
                                    new_box_result = execute_query(
                                        "SELECT id FROM boxes WHERE shipment_id = %s AND box_id = %s",
                                        (new_shipment_id, box_id_str),
                                        fetchone=True
                                    )
                                    if new_box_result:
                                        new_box_id = new_box_result[0]
                        processed_row.append(str(new_box_id) if new_box_id is not None else str(value))
                    else:
                        if value is None:
                            processed_row.append(None)
                        else:
                            # Преобразуем все значения в строки, чтобы избежать проблем с форматированием
                            try:
                                processed_row.append(str(value))
                            except Exception:
                                # Если не удается преобразовать в строку, используем repr()
                                processed_row.append(repr(value))
                processed_box_items.append(tuple(processed_row))
            
            try:
                # Для box_items используем INSERT без ON CONFLICT, так как нет уникального ограничения
                if use_postgresql:
                    execute_many(
                        "INSERT INTO box_items (box_id, barcode, qty) "
                        "VALUES (%s, %s, %s)",
                        processed_box_items
                    )
                else:
                    execute_many(
                        "INSERT INTO box_items (box_id, barcode, qty) "
                        "VALUES (?, ?, ?)",
                        processed_box_items
                    )
            except TypeError as e:
                if "not all arguments converted during string formatting" in str(e):
                    logger.error(f"Ошибка форматирования параметров при восстановлении товаров в коробках: {e}")
                    logger.error(f"Список обработанных товаров в коробках: {processed_box_items}")
                    raise
                else:
                    logger.error(f"Ошибка при восстановлении товаров в коробках: {e}")
                    raise
            except Exception as e:
                logger.error(f"Ошибка при восстановлении товаров в коробках: {e}")
                raise
        
        # Восстанавливаем сессии пользователяей (если таблица существует)
        try:
            # Проверяем, существует ли таблица user_sessions
            result = execute_query("""
                SELECT EXISTS (
                  SELECT FROM information_schema.tables
                  WHERE table_schema = 'public'
                  AND table_name = 'user_sessions'
                );
            """, fetchone=True)
            table_exists = result[0] if result else False
            
            # Если таблица существует, восстанавливаем данные
            if table_exists and 'user_sessions' in backup_data and backup_data['user_sessions']:
                # Обрабатываем данные, чтобы избежать проблем с форматированием
                processed_user_sessions = []
                for session_row in backup_data['user_sessions']:
                    # Пропускаем id (первое поле) при восстановлении, так как это SERIAL
                    processed_row = []
                    for i, value in enumerate(session_row):
                        if i == 0:  # Пропускаем id
                            continue
                        if i == 1: # shipment_name - второй элемент, нужно сопоставить с новым именем
                            old_shipment_id = str(value)
                            # Получаем имя поставки по старому ID из бэкапа
                            old_shipment_data = None
                            for shipment_row in backup_data['shipments']:
                                if str(shipment_row[0]) == str(old_shipment_id):  # id - первый элемент
                                    old_shipment_data = shipment_row
                                    break
                            new_shipment_name = value  # по умолчанию оставляем старое значение
                            if old_shipment_data:
                                new_shipment_name = old_shipment_data[1]  # destination_name - второй элемент
                            processed_row.append(str(new_shipment_name))
                        else:
                            if value is None:
                                processed_row.append(None)
                            else:
                                # Преобразуем все значения в строки, чтобы избежать проблем с форматированием
                                try:
                                    processed_row.append(str(value))
                                except Exception:
                                    # Если не удается преобразовать в строку, используем repr()
                                    processed_row.append(repr(value))
                    processed_user_sessions.append(tuple(processed_row))
                
                try:
                    # Для user_sessions используем INSERT без ON CONFLICT, так как нет уникального ограничения
                    if use_postgresql:
                        execute_many(
                            "INSERT INTO user_sessions (shipment_name, username, last_activity) "
                            "VALUES (%s, %s, %s)",
                            processed_user_sessions
                        )
                    else:
                        execute_many(
                            "INSERT INTO user_sessions (shipment_name, username, last_activity) "
                            "VALUES (?, ?, ?)",
                            processed_user_sessions
                        )
                except TypeError as e:
                    if "not all arguments converted during string formatting" in str(e):
                        logger.error(f"Ошибка форматирования параметров при восстановлении сессий пользователяей: {e}")
                        logger.error(f"Список обработанных сессий пользователяей: {processed_user_sessions}")
                        raise
                    else:
                        logger.error(f"Ошибка при восстановлении сессий пользователяей: {e}")
                        raise
                except Exception as e:
                    logger.error(f"Ошибка при восстановлении сессий пользователяей: {e}")
                    raise
        except Exception as e:
            # Таблица user_sessions не существует, пропускаем восстановление
            if "отношение \"user_sessions\" не существует" not in str(e):
                logger.error(f"Ошибка при проверке существования таблицы user_sessions: {e}")
            pass
    
    def delete_backup(self):
        """Удаляет выбранный бэкап"""
        current_row = self.backups_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите бэкап для удаления!")
            return
        
        item = self.backups_table.item(current_row, 0)
        backup_path = item.data(Qt.ItemDataRole.UserRole)
        
        if not backup_path or not os.path.exists(backup_path):
            QMessageBox.critical(self, "Ошибка", "Файл бэкапа не найден!")
            return
        
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить бэкап?\n\nФайл: {os.path.basename(backup_path)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(backup_path)
                QMessageBox.information(
                    self,
                    "Бэкап удален",
                    "Файл бэкапа успешно удален!"
                )
                
                # Обновляем список бэкапов
                self.load_backups()
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Ошибка удаления",
                    f"Не удалось удалить файл бэкапа:\n{str(e)}"
                )
    
    def confirm_clear_database(self):
        """Подтверждает и выполняет очистку базы данных"""
        reply = QMessageBox.question(
            self,
            "Подтверждение очистки",
            "Вы уверены, что хотите очистить всю базу данных?\n\n"
            "Это действие удалит:\n"
            "- Все поставки (включая архивированные)\n"
            "- Все пользователяи\n"
            "- Все настройки\n\n"
            "ДАННЫЕ БУДУТ БЕЗВОЗВРАТНО УТЕРЯНЫ!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = database.clear_database()
                
                if success:
                    QMessageBox.information(
                        self,
                        "Очистка завершена",
                        "База данных успешно очищена!\n"
                        "Приложение необходимо перезапустить для завершения процесса."
                    )
                    
                    # Обновляем информацию о базе данных
                    self.load_database_info()
                else:
                    QMessageBox.critical(
                        self,
                        "Ошибка очистки",
                        "Не удалось очистить базу данных. Проверьте логи для получения подробной информации."
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Произошла ошибка при попытке очистить базу данных:\n{str(e)}"
                )
    
    def apply_theme(self):
        """Применяет текущую тему к диалогу"""
        theme = themes.THEMES.get(self.current_theme, themes.THEMES["Светлая"])
        
        # Применяем стили в зависимости от темы
        if self.current_theme == "Тёмная":
            self.setStyleSheet(f"""
                QDialog {{
                    background-color: {theme["window_bg"].name()};
                    color: {theme["window_text"].name()};
                }}
                QGroupBox {{
                    font-weight: bold;
                    border: 1px solid {theme["button_border"].name()};
                    border-radius: 6px;
                    margin-top: 1ex;
                    padding-top: 12px;
                    color: {theme["header_text"].name()};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 8px 0 8px;
                    background-color: {theme["window_bg"].name()};
                }}
                QTabWidget::pane {{
                    border: 1px solid {theme["button_border"].name()};
                    background-color: {theme["window_bg"].name()};
                }}
                QTabWidget::tab-bar {{
                    left: 5px;
                }}
                QTabBar::tab {{
                    background-color: {theme["button_bg"].name()};
                    color: {theme["button_text"].name()};
                    padding: 6px 12px;
                    margin-right: 2px;
                    border: 1px solid {theme["button_border"].name()};
                    border-bottom-color: {theme["button_border"].name()};
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }}
                QTabBar::tab:selected {{
                    background-color: {theme["header_bg"].name()};
                    color: {theme["header_text"].name()};
                    border-bottom-color: {theme["window_bg"].name()};
                }}
                QTabBar::tab:hover {{
                    background-color: {theme["highlight"].name()};
                }}
                QTableWidget {{
                    background-color: {theme["table_bg"].name()};
                    color: {theme["text"].name()};
                    gridline-color: {theme["button_border"].name()};
                    border: 1px solid {theme["button_border"].name()};
                }}
                QTableWidget::item {{
                    border-bottom: 1px solid {theme["button_border"].name()};
                    background-color: transparent;
                    padding: 4px;
                }}
                QTableWidget::item:selected {{
                    background-color: {theme["highlight"].name()};
                    color: {theme["text"].name()};
                }}
                QHeaderView::section {{
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 {theme["header_bg"].lighter(110).name()},
                        stop: 1 {theme["header_bg"].name()});
                    color: {theme["header_text"].name()};
                    padding: 8px;
                    border: none;
                    font-weight: 600;
                    font-size: 13px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QDialog {{
                    background-color: {theme["window_bg"].name()};
                    color: {theme["window_text"].name()};
                }}
                QGroupBox {{
                    font-weight: bold;
                    border: 1px solid {theme["button_border"].name()};
                    border-radius: 6px;
                    margin-top: 1ex;
                    padding-top: 12px;
                    color: {theme["header_text"].name()};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 8px 0 8px;
                    background-color: {theme["window_bg"].name()};
                }}
                QTabWidget::pane {{
                    border: 1px solid {theme["button_border"].name()};
                    background-color: {theme["window_bg"].name()};
                }}
                QTabWidget::tab-bar {{
                    left: 5px;
                }}
                QTabBar::tab {{
                    background-color: {theme["button_bg"].name()};
                    color: {theme["button_text"].name()};
                    padding: 6px 12px;
                    margin-right: 2px;
                    border: 1px solid {theme["button_border"].name()};
                    border-bottom-color: {theme["button_border"].name()};
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }}
                QTabBar::tab:selected {{
                    background-color: {theme["header_bg"].name()};
                    color: {theme["header_text"].name()};
                    border-bottom-color: {theme["window_bg"].name()};
                }}
                QTabBar::tab:hover {{
                    background-color: {theme["highlight"].name()};
                }}
                QTableWidget {{
                    background-color: {theme["table_bg"].name()};
                    color: {theme["text"].name()};
                    gridline-color: {theme["button_border"].name()};
                    border: 1px solid {theme["button_border"].name()};
                }}
                QTableWidget::item {{
                    border-bottom: 1px solid {theme["button_border"].name()};
                    background-color: transparent;
                    padding: 4px;
                }}
                QTableWidget::item:selected {{
                    background-color: {theme["highlight"].name()};
                    color: {theme["text"].name()};
                }}
                QHeaderView::section {{
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 {theme["header_bg"].lighter(105).name()},
                        stop: 1 {theme["header_bg"].name()};
                    color: {theme["header_text"].name()};
                    padding: 8px;
                    border: none;
                    font-weight: 600;
                    font-size: 13px;
                }}
            """)
    
    def showEvent(self, event):
        """Обработка события показа диалога"""
        super().showEvent(event)
        # Применяем тему при показе диалога
        self.apply_theme()