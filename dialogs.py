# dialogs.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QMessageBox, QComboBox, QCheckBox, QFormLayout, QGroupBox,
    QListWidget, QListWidgetItem, QFrame, QScrollArea, QWidget, QGridLayout,
    QDateEdit, QPlainTextEdit, QTreeWidgetItem, QTabWidget, QTreeWidget, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog, QSlider
)
from PyQt6.QtCore import Qt, QDate
import database
from db_connection import get_db_type
import config
import utils
try:
    from moysklad_settings_dialog import MoyskladSettingsDialog
    MOYSKLAD_AVAILABLE = True
except ImportError:
    MOYSKLAD_AVAILABLE = False


class UserManagerDialog(QDialog):
    """
    Диалог управления пользователями
    """
    
    def __init__(self, current_user, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.setWindowTitle("Управление пользователями")
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Список пользователей
        self.users_list = QListWidget()
        layout.addWidget(QLabel("Выберите пользователя:"))
        layout.addWidget(self.users_list)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        self.add_user_btn = QPushButton("Добавить")
        self.add_user_btn.clicked.connect(self.add_user)
        buttons_layout.addWidget(self.add_user_btn)
        
        self.delete_user_btn = QPushButton("Удалить")
        self.delete_user_btn.clicked.connect(self.delete_user)
        buttons_layout.addWidget(self.delete_user_btn)
        
        buttons_layout.addStretch()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        buttons_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        self.load_users()

        # Установить текущего пользователя
        if current_user:
            for i in range(self.users_list.count()):
                item = self.users_list.item(i)
                if item.text() == current_user:
                    self.users_list.setCurrentItem(item)
                    break

    def set_current_user(self, username):
        """Установить текущего пользователя"""
        for i in range(self.users_list.count()):
            item = self.users_list.item(i)
            if item.text() == username:
                self.users_list.setCurrentItem(item)
                break
    
    def load_users(self):
        """Загрузить список пользователей"""
        self.users_list.clear()
        users = database.get_all_users()
        for user in users:
            # user - это кортеж (username, icon) из запроса SELECT username, icon FROM users
            if isinstance(user, tuple) and len(user) >= 1:
                username = user[0]  # Первый элемент кортежа - это username
            elif hasattr(user, '__getitem__'):
                # Если user - это словарь (для PostgreSQL), извлекаем имя пользователя
                username = user.get('username', user.get('name', str(user)))
            else:
                username = str(user)
            self.users_list.addItem(username)
    
    def add_user(self):
        """Добавить нового пользователя"""
        # QInputDialog is already imported at the top of the file
        username, ok = QInputDialog.getText(self, "Новый пользователь", "Введите имя пользователя:")
        if ok and username:
            # Валидация имени пользователя
            from security_utils import validator
            is_valid, error_message = validator.validate_username(username)
            if not is_valid:
                QMessageBox.warning(self, "Ошибка валидации", f"Недопустимое имя пользователя: {error_message}")
                return
            
            # Санитизация имени пользователя
            username = validator.sanitize_input(username)
            
            # Проверяем, существует ли уже такой пользователь
            users = database.get_all_users()
            user_exists = False
            for user in users:
                # user - это кортеж (username, icon) из запроса SELECT username, icon FROM users
                if isinstance(user, tuple) and len(user) >= 1:
                    existing_username = user[0]  # Первый элемент кортежа - это username
                elif hasattr(user, '__getitem__'):
                    existing_username = user.get('username', user.get('name', str(user)))
                else:
                    existing_username = str(user)
                if existing_username == username:
                    user_exists = True
                    break
            
            if user_exists:
                QMessageBox.warning(self, "Ошибка", f"Пользователь '{username}' уже существует!")
                return
            
            # Добавляем пользователя в базу данных
            database.set_user_settings(username, config.DEFAULT_FONT_SIZE,
                                     config.DEFAULT_LABEL_FONT_SIZE, config.DEFAULT_THEME,
                                     "ok.wav", "error.wav", "", "", "", 1300, 800,
                                     "", "", "", "", "", "", False, True,
                                     True, False, True, True, False, "", True, "")
            self.load_users()
    
    def delete_user(self):
        """Удалить выбранного пользователя"""
        current_item = self.users_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Ошибка", "Выберите пользователя для удаления!")
            return
        
        username = current_item.text()
        if username == self.current_user:
            QMessageBox.warning(self, "Ошибка", "Нельзя удалить текущего пользователя!")
            return
        
        reply = QMessageBox.question(self, "Подтверждение", 
                                   f"Вы уверены, что хотите удалить пользователя '{username}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            database.delete_user(username)
            self.load_users()
    
    def get_selected_user(self):
        """Получить выбранного пользователя"""
        current_item = self.users_list.currentItem()
        if current_item:
            return current_item.text()
        return None


class SettingsDialog(QDialog):
    """
    Диалог настроек приложения
    """

    def __init__(self, font_size, label_font_size, theme, ok_sound, error_sound,
                 shipment_locking_enabled=True, tone_sound=False, sound_volume=100, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.resize(700, 600)

        layout = QVBoxLayout()

        # Создаем вкладки
        tab_widget = QTabWidget()

        # === Вкладка "Основные настройки" ===
        general_tab = QWidget()
        general_layout = QVBoxLayout()

        # Форма для основных настроек
        form_layout = QFormLayout()

        # Размер шрифта
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(font_size)
        form_layout.addRow("Размер шрифта:", self.font_size_spin)

        # Размер шрифта этикеток
        self.label_font_size_spin = QSpinBox()
        self.label_font_size_spin.setRange(8, 24)
        self.label_font_size_spin.setValue(label_font_size)
        form_layout.addRow("Размер шрифта этикеток:", self.label_font_size_spin)

        # Тема
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Светлая", "Тёмная"])
        self.theme_combo.setCurrentText(theme)
        form_layout.addRow("Тема:", self.theme_combo)

        # Звуки
        self.ok_sound_combo = QComboBox()
        self.ok_sound_combo.addItems(["ok.wav", "ok2.wav", "ok3.wav", "ok4.wav", "ok5.wav"])
        self.ok_sound_combo.setCurrentText(ok_sound)
        self.ok_sound_combo.currentTextChanged.connect(self.on_sound_changed)
        form_layout.addRow("Звук OK:", self.ok_sound_combo)

        self.error_sound_combo = QComboBox()
        self.error_sound_combo.addItems(["error.wav", "error2.wav", "error3.wav", "error4.wav", "error5.wav", "error6.wav", "error7.wav", "error8.wav", "error9.wav"])
        self.error_sound_combo.setCurrentText(error_sound)
        self.error_sound_combo.currentTextChanged.connect(self.on_sound_changed)
        form_layout.addRow("Звук ошибки:", self.error_sound_combo)

        # Чекбокс "Тоновый звук"
        self.tone_sound_checkbox = QCheckBox()
        self.tone_sound_checkbox.setChecked(tone_sound)
        self.tone_sound_checkbox.setToolTip("При включении вместо звука OK проигрывается случайный тон из tone1.wav - tone5.wav")
        form_layout.addRow("Тоновый звук:", self.tone_sound_checkbox)

        # Ползунок громкости
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(sound_volume)
        self.volume_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.volume_slider.setTickInterval(10)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.volume_label = QLabel(f"{sound_volume}%")
        self.volume_label.setMinimumWidth(40)
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_label)
        form_layout.addRow("Громкость:", volume_layout)

        # Кнопка перекраски кнопок
        self.recolor_buttons_btn = QPushButton("🎨 Перекрасить кнопки")
        self.recolor_buttons_btn.setToolTip("Выбрать случайные цвета для кнопок верхней панели")
        form_layout.addRow("", self.recolor_buttons_btn)

        general_layout.addLayout(form_layout)
        general_tab.setLayout(general_layout)

        tab_widget.addTab(general_tab, "Основные")

        # === Вкладка "Пользователи" ===
        users_tab = QWidget()
        users_layout = QVBoxLayout()
        
        # Список пользователей
        self.users_list = QListWidget()
        self.users_list.itemDoubleClicked.connect(self.edit_user)
        users_layout.addWidget(QLabel("Список пользователей:"))
        users_layout.addWidget(self.users_list)
        
        # Кнопки управления пользователями
        users_btn_layout = QHBoxLayout()
        
        self.add_user_btn = QPushButton("Добавить")
        self.add_user_btn.clicked.connect(self.add_user)
        users_btn_layout.addWidget(self.add_user_btn)
        
        self.edit_user_btn = QPushButton("Изменить")
        self.edit_user_btn.clicked.connect(self.edit_user)
        users_btn_layout.addWidget(self.edit_user_btn)
        
        self.delete_user_btn = QPushButton("Удалить")
        self.delete_user_btn.clicked.connect(self.delete_user)
        users_btn_layout.addWidget(self.delete_user_btn)
        
        users_btn_layout.addStretch()
        
        users_layout.addLayout(users_btn_layout)
        users_tab.setLayout(users_layout)
        
        tab_widget.addTab(users_tab, "Пользователи")
        
        # === Вкладка "База данных" ===
        db_tab = QWidget()
        db_layout = QVBoxLayout()
        
        # Кнопка открытия настроек БД
        self.db_settings_btn = QPushButton("Настройки базы данных")
        self.db_settings_btn.clicked.connect(self.open_database_settings)
        db_layout.addWidget(self.db_settings_btn)
        
        # Информация о БД
        db_info = QLabel(
            "Здесь вы можете настроить параметры подключения к базе данных:\n\n"
            "• Выбрать тип базы данных (PostgreSQL или SQLite)\n"
            "• Настроить параметры подключения\n"
            "• Создать резервную копию\n"
            "• Восстановить данные из бэкапа\n"
            "• Очистить базу данных"
        )
        db_info.setWordWrap(True)
        db_layout.addWidget(db_info)
        
        db_layout.addStretch()
        db_tab.setLayout(db_layout)
        
        tab_widget.addTab(db_tab, "База данных")

        # === Вкладка "SKU и Печать" ===
        sku_print_tab = QWidget()
        sku_print_layout = QVBoxLayout()
        
        # Группа "Таблица SKU"
        sku_group = QGroupBox("Таблица SKU")
        sku_group_layout = QVBoxLayout()
        
        sku_info = QLabel(
            "Таблица SKU содержит информацию о штрихкодах, артикулах и наименованиях товаров.\n"
            "Используется для автоматического заполнения наименований при сканировании штрихкодов.\n"
            "Данные загружаются из Google Sheets."
        )
        sku_info.setWordWrap(True)
        sku_group_layout.addWidget(sku_info)
        
        # Ссылка на Google Sheets
        sheets_link = QLabel('<a href="https://docs.google.com/spreadsheets/d/1tQzh_qTnldbpeu9ryNF8ZKY4-amwT8UfuMqbSU1qOlA/edit">📊 Открыть Google Sheets таблицу SKU</a>')
        sheets_link.setOpenExternalLinks(True)
        sheets_link.setStyleSheet("font-size: 12px; padding: 5px;")
        sku_group_layout.addWidget(sheets_link)
        
        self.update_sku_btn = QPushButton("Актуализировать таблицу SKU")
        self.update_sku_btn.clicked.connect(self.update_sku_table)
        sku_group_layout.addWidget(self.update_sku_btn)
        
        sku_group.setLayout(sku_group_layout)
        sku_print_layout.addWidget(sku_group)
        
        # Группа "Печать этикеток"
        print_group = QGroupBox("Печать этикеток")
        print_group_layout = QVBoxLayout()
        
        print_info = QLabel(
            "Настройки печати этикеток позволяют настроить формат и параметры печати\n"
            "транспортных этикеток для коробок."
        )
        print_info.setWordWrap(True)
        print_group_layout.addWidget(print_info)
        
        self.label_print_settings_btn = QPushButton("Настройки печати этикеток")
        self.label_print_settings_btn.clicked.connect(self.open_label_print_settings)
        print_group_layout.addWidget(self.label_print_settings_btn)
        
        self.print_label_btn = QPushButton("Печать этикетки")
        self.print_label_btn.clicked.connect(self.print_label)
        print_group_layout.addWidget(self.print_label_btn)
        
        print_group.setLayout(print_group_layout)
        sku_print_layout.addWidget(print_group)
        
        sku_print_layout.addStretch()
        sku_print_tab.setLayout(sku_print_layout)
        
        tab_widget.addTab(sku_print_tab, "SKU и Печать")

        # Добавляем вкладку МойСклад, если модуль доступен
        if MOYSKLAD_AVAILABLE:
            self.moysklad_tab = QWidget()
            moysklad_layout = QVBoxLayout()

            # Кнопка открытия настроек МойСклад
            self.moysklad_settings_btn = QPushButton("Настройки интеграции с МойСклад")
            self.moysklad_settings_btn.clicked.connect(self.open_moysklad_settings)
            moysklad_layout.addWidget(self.moysklad_settings_btn)

            # Информационная метка
            info_label = QLabel(
                "Настройки интеграции с МойСклад позволяют:\n"
                "• Подключиться к вашему аккаунту МойСклад\n"
                "• Получать остатки товаров на складах\n"
                "• Отображать остатки в интерфейсе программы"
            )
            info_label.setWordWrap(True)
            moysklad_layout.addWidget(info_label)

            moysklad_layout.addStretch()
            self.moysklad_tab.setLayout(moysklad_layout)

            tab_widget.addTab(self.moysklad_tab, "МойСклад")

        layout.addWidget(tab_widget)

        # Кнопки
        buttons_layout = QHBoxLayout()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        buttons_layout.addWidget(ok_button)

        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)

        layout.addLayout(buttons_layout)

        self.setLayout(layout)
        
        # Загружаем список пользователей
        self.load_users_list()

    def load_users_list(self):
        """Загружает список пользователей"""
        self.users_list.clear()
        try:
            users = database.get_all_users()
            if users:
                for user in users:
                    self.users_list.addItem(user[0] if isinstance(user, (list, tuple)) else user)
        except Exception as e:
            pass

    def add_user(self):
        """Добавляет нового пользователя"""
        from dialogs import UserManagerDialog
        dialog = UserManagerDialog(self.parent.current_user if self.parent else None, self.parent)
        dialog.exec()
        self.load_users_list()

    def edit_user(self):
        """Редактирует выбранного пользователя"""
        current_item = self.users_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Ошибка", "Выберите пользователя для редактирования")
            return
        
        username = current_item.text()
        from dialogs import UserManagerDialog
        dialog = UserManagerDialog(self.parent.current_user if self.parent else None, self.parent)
        dialog.set_current_user(username)
        dialog.exec()
        self.load_users_list()

    def delete_user(self):
        """Удаляет выбранного пользователя"""
        current_item = self.users_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Ошибка", "Выберите пользователя для удаления")
            return
        
        username = current_item.text()
        
        if username == (self.parent.current_user if self.parent else None):
            QMessageBox.warning(self, "Ошибка", "Нельзя удалить текущего пользователя")
            return
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Вы уверены, что хотите удалить пользователя '{username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                database.delete_user(username)
                self.load_users_list()
                QMessageBox.information(self, "Успешно", f"Пользователь '{username}' удален")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при удалении пользователя: {e}")

    def open_moysklad_settings(self):
        """Открыть диалог настроек МойСклад"""
        if MOYSKLAD_AVAILABLE:
            dialog = MoyskladSettingsDialog(self.parent)
            dialog.exec()

    def open_database_settings(self):
        """Открыть диалог настроек базы данных"""
        from db_settings_dialog import DatabaseSettingsDialog
        if self.parent:
            dialog = DatabaseSettingsDialog(self.parent)
            dialog.exec()

    def update_sku_table(self):
        """Актуализировать таблицу SKU"""
        if self.parent and hasattr(self.parent, 'update_sku_table_async'):
            self.parent.update_sku_table_async()
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось обновить таблицу SKU: главное окно недоступно.")

    def open_label_print_settings(self):
        """Открыть настройки печати этикеток"""
        from label_settings_dialog import LabelSettingsDialog
        if self.parent:
            dialog = LabelSettingsDialog(self.parent)
            dialog.exec()

    def print_label(self):
        """Открыть диалог печати этикетки"""
        if self.parent and hasattr(self.parent, 'open_label_print_dialog'):
            self.parent.open_label_print_dialog()
    
    def get_font_size(self):
        return self.font_size_spin.value()
    
    def get_label_font_size(self):
        return self.label_font_size_spin.value()
    
    def get_theme(self):
        return self.theme_combo.currentText()
    
    def get_ok_sound(self):
        return self.ok_sound_combo.currentText()
    
    def get_error_sound(self):
        return self.error_sound_combo.currentText()

    def get_tone_sound(self):
        return self.tone_sound_checkbox.isChecked()

    def get_sound_volume(self):
        return self.volume_slider.value()

    def on_volume_changed(self, value):
        """Обновить метку громкости и проиграть тестовый звук"""
        self.volume_label.setText(f"{value}%")
        # Проигрываем короткий тестовый звук при изменении громкости
        if value > 0:  # Только если громкость не нулевая
            utils.play_sound("ok.wav", tone_sound=False)

    def on_sound_changed(self, sound_name):
        """Проиграть звук при выборе в комбобоксе"""
        if sound_name:  # Проигрываем только если имя звука не пустое
            utils.play_sound(sound_name, tone_sound=False)

    def get_user_icon(self):
        # Возвращаем иконку по умолчанию, так как аватарки удалены
        return "1.png"  # По умолчанию

    # Система блокировки поставок удалена
    # def get_shipment_locking_enabled(self):
    #     return self.shipment_locking_checkbox.isChecked()


def generate_random_color():
    """Генерирует случайный яркий цвет для кнопок"""
    import random
    # Генерируем яркие насыщенные цвета
    h = random.random()  # Оттенок 0-1
    s = 0.7 + random.random() * 0.3  # Насыщенность 70-100%
    v = 0.7 + random.random() * 0.3  # Яркость 70-100%
    
    # Конвертируем HSV в RGB
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    
    # Преобразуем в HEX
    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))


class DestinationDialog(QDialog):
    """
    Диалог ввода пункта назначения
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Пункт назначения")
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("Введите пункт назначения")
        layout.addWidget(self.destination_input)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        buttons_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        self.destination_input.setFocus()
        
        # Устанавливаем код возврата при нажатии Enter
        ok_button.setDefault(True)
        
        # Устанавливаем размер окна
        self.resize(300, 80)
    
    def get_destination(self):
        return self.destination_input.text().strip()


class RenameDialog(QDialog):
    """
    Диалог переименования
    """
    
    def __init__(self, current_name, is_shipment=True, existing_names=None, parent=None):
        super().__init__(parent)
        self.current_name = current_name
        self.existing_names = existing_names or []
        self.setWindowTitle("Переименовать")
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        self.name_input = QLineEdit(current_name)
        layout.addWidget(self.name_input)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.validate_and_accept)
        buttons_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        self.name_input.selectAll()
        self.name_input.setFocus()
        
        # Устанавливаем код возврата при нажатии Enter
        ok_button.setDefault(True)
        
        # Устанавливаем размер окна
        self.resize(300, 80)
        
    def validate_and_accept(self):
        new_name = self.name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Ошибка", "Введите новое имя!")
            return
        
        if new_name == self.current_name:
            super().accept()
            return
        
        if new_name in self.existing_names:
            QMessageBox.warning(self, "Ошибка", f"Название '{new_name}' уже существует!")
            return
        
        super().accept()
    
    def get_new_name(self):
        return self.name_input.text().strip()


class ShipmentPropertiesDialog(QDialog):
    """
    Диалог свойств поставки
    """
    
    def __init__(self, shipment, parent=None):
        super().__init__(parent)
        self.shipment = shipment
        self.setWindowTitle("Свойства поставки")
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Форма для свойств поставки
        form_layout = QFormLayout()
        
        # Номер поставки
        self.shipment_number_input = QLineEdit(shipment.properties.shipment_number)
        form_layout.addRow("Номер поставки:", self.shipment_number_input)
        
        
        self.shipment_date_input = QDateEdit()
        self.shipment_date_input.setDisplayFormat("dd.MM.yyyy")
        self.shipment_date_input.setCalendarPopup(True)
        self.shipment_date_input.setDate(QDate.currentDate())
        # Устанавливаем текущую дату, если в свойствах пусто
        if shipment.properties.shipment_date:
            try:
                date_parts = shipment.properties.shipment_date.split("-")
                if len(date_parts) == 3:
                    year, month, day = map(int, date_parts)
                    self.shipment_date_input.setDate(QDate(year, month, day))
                else:
                    self.shipment_date_input.setDate(QDate.currentDate())
            except (ValueError, IndexError):
                self.shipment_date_input.setDate(QDate.currentDate())
        else:
            self.shipment_date_input.setDate(QDate.currentDate())
        form_layout.addRow("Дата поставки:", self.shipment_date_input)
        
        # Склад назначения
        self.destination_warehouse_input = QLineEdit(shipment.properties.destination_warehouse)
        form_layout.addRow("Склад назначения:", self.destination_warehouse_input)
        
        # Маркетплейс
        self.marketplace_combo = QComboBox()
        self.marketplace_combo.addItems(["", "Wildberries", "Ozon", "Яндекс Маркет"])
        self.marketplace_combo.setCurrentText(shipment.properties.marketplace)
        form_layout.addRow("Маркетплейс:", self.marketplace_combo)
        
        # Юр. лицо
        self.legal_entity_combo = QComboBox()
        self.legal_entity_combo.addItems(["", "ООО ОНДЕФОР", "ИП Лазарчук"])
        self.legal_entity_combo.setCurrentText(shipment.properties.legal_entity)
        form_layout.addRow("Юр. лицо:", self.legal_entity_combo)
        
        # ID коробок
        self.box_ids_text = QPlainTextEdit(shipment.properties.box_ids)
        self.box_ids_text.setMaximumHeight(100)  # Ограничиваем высоту поля
        form_layout.addRow("ID коробок (по одному в строке):", self.box_ids_text)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        buttons_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def accept(self):
        self.shipment.properties.shipment_number = self.shipment_number_input.text().strip()
        self.shipment.properties.shipment_date = self.shipment_date_input.date().toString("yyyy-MM-dd")
        self.shipment.properties.destination_warehouse = self.destination_warehouse_input.text().strip()
        self.shipment.properties.marketplace = self.marketplace_combo.currentText()
        self.shipment.properties.legal_entity = self.legal_entity_combo.currentText()
        self.shipment.properties.box_ids = self.box_ids_text.toPlainText().strip()

        super().accept()


class GroupShipmentPropertiesDialog(QDialog):
    """
    Диалог свойств групповой поставки с таблицей свойств для всех входящих поставок
    """

    def __init__(self, group_shipment, parent=None):
        super().__init__(parent)
        self.group_shipment = group_shipment
        self.setWindowTitle(f"Свойства групповой поставки: {group_shipment.group_name}")
        self.setModal(True)
        self.resize(900, 600)

        layout = QVBoxLayout()

        common_layout = QGridLayout()

        common_layout.addWidget(QLabel("Маркетплейс (общий):"), 0, 0)
        self.marketplace_combo = QComboBox()
        self.marketplace_combo.addItems(["", "Wildberries", "Ozon", "Яндекс Маркет"])
        all_marketplaces = set()
        for shipment in group_shipment.sub_shipments.values():
            if shipment.properties.marketplace:
                all_marketplaces.add(shipment.properties.marketplace)
        if len(all_marketplaces) == 1:
            self.marketplace_combo.setCurrentText(next(iter(all_marketplaces)))
        common_layout.addWidget(self.marketplace_combo, 0, 1)

        common_layout.addWidget(QLabel("Юр. лицо (общее):"), 1, 0)
        self.legal_entity_combo = QComboBox()
        self.legal_entity_combo.addItems(["", "ООО ОНДЕФОР", "ИП Лазарчук"])
        all_legal = set()
        for shipment in group_shipment.sub_shipments.values():
            if shipment.properties.legal_entity:
                all_legal.add(shipment.properties.legal_entity)
        if len(all_legal) == 1:
            self.legal_entity_combo.setCurrentText(next(iter(all_legal)))
        common_layout.addWidget(self.legal_entity_combo, 1, 1)

        common_widget = QWidget()
        common_widget.setLayout(common_layout)
        layout.addWidget(common_widget)

        layout.addWidget(QLabel("Свойства поставок (строки - свойства, столбцы - поставки):"))

        self.table = QTableWidget()
        self.table.setColumnCount(len(group_shipment.sub_shipments))
        self.table.setRowCount(4)
        self.table.setMinimumWidth(600)
        self.table.horizontalHeader().setMinimumSectionSize(120)

        shipment_names = []
        for i, shipment in enumerate(group_shipment.sub_shipments.values()):
            display = getattr(shipment, 'display_name', shipment.destination_name)
            city = display.split("_")[-1] if "_" in display else display
            shipment_names.append(city)
        self.table.setHorizontalHeaderLabels(shipment_names)

        row_labels = ["Номер поставки", "Дата поставки", "Склад назначения", "ID коробок"]
        self.table.setVerticalHeaderLabels(row_labels)

        self.date_widgets = []
        self.box_ids_widgets = []

        for col, shipment in enumerate(group_shipment.sub_shipments.values()):
            number_input = QLineEdit(shipment.properties.shipment_number)
            self.table.setCellWidget(0, col, number_input)

            date_edit = QDateEdit()
            date_edit.setDisplayFormat("dd.MM.yyyy")
            date_edit.setCalendarPopup(True)
            if shipment.properties.shipment_date:
                try:
                    parts = shipment.properties.shipment_date.split("-")
                    if len(parts) == 3:
                        date_edit.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
                except:
                    date_edit.setDate(QDate.currentDate())
            else:
                date_edit.setDate(QDate.currentDate())
            self.table.setCellWidget(1, col, date_edit)
            self.date_widgets.append((col, date_edit))

            warehouse_input = QLineEdit(shipment.properties.destination_warehouse)
            self.table.setCellWidget(2, col, warehouse_input)

            box_ids_text = QPlainTextEdit(shipment.properties.box_ids)
            box_ids_text.setMinimumHeight(120)
            self.table.setCellWidget(3, col, box_ids_text)
            self.box_ids_widgets.append((col, box_ids_text))

        self.table.resizeRowsToContents()
        self.table.setRowHeight(3, 150)
        layout.addWidget(self.table)

        buttons_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        buttons_layout.addWidget(ok_button)
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def accept(self):
        shipments_list = list(self.group_shipment.sub_shipments.values())

        for col, shipment in enumerate(shipments_list):
            number_widget = self.table.cellWidget(0, col)
            if isinstance(number_widget, QLineEdit):
                shipment.properties.shipment_number = number_widget.text().strip()

            date_widget = self.table.cellWidget(1, col)
            if isinstance(date_widget, QDateEdit):
                shipment.properties.shipment_date = date_widget.date().toString("yyyy-MM-dd")

            warehouse_widget = self.table.cellWidget(2, col)
            if isinstance(warehouse_widget, QLineEdit):
                shipment.properties.destination_warehouse = warehouse_widget.text().strip()

            box_widget = self.table.cellWidget(3, col)
            if isinstance(box_widget, QPlainTextEdit):
                shipment.properties.box_ids = box_widget.toPlainText().strip()

        for shipment in shipments_list:
            shipment.properties.marketplace = self.marketplace_combo.currentText()
            shipment.properties.legal_entity = self.legal_entity_combo.currentText()

        super().accept()


class ArchiveDialog(QDialog):
    """
    Диалог архива поставок
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Архив поставок")
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Создаем основной сплиттер для разделения интерфейса
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Левая часть - список архивных поставок
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Создаем таблицу для архивных поставок
        self.archive_table = QTableWidget()
        self.archive_table.setColumnCount(4)
        self.archive_table.setHorizontalHeaderLabels(["Поставка", "Группа", "Дата архивации", "Кем архивировано"])
        self.archive_table.setStyleSheet("""
            QTableWidget {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 4px;
            }
        """)
        # Устанавливаем политику растягивания столбцов
        header = self.archive_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        left_layout.addWidget(QLabel("Архивные поставки:"))
        left_layout.addWidget(self.archive_table)
        
        # Кнопки для поставок
        shipment_buttons_layout = QHBoxLayout()
        
        self.restore_btn = QPushButton("Восстановить")
        self.restore_btn.clicked.connect(self.restore_shipment)
        shipment_buttons_layout.addWidget(self.restore_btn)
        
        self.delete_btn = QPushButton("Удалить навсегда")
        self.delete_btn.clicked.connect(self.delete_shipment)
        shipment_buttons_layout.addWidget(self.delete_btn)
        
        shipment_buttons_layout.addStretch()
        
        left_layout.addLayout(shipment_buttons_layout)
        left_widget.setLayout(left_layout)
        
        # Правая часть - дерево содержимого поставки
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Дерево содержимого поставки
        self.content_tree = QTreeWidget()
        self.content_tree.setHeaderLabels(["Штрихкод", "Артикул", "Количество"])
        self.content_tree.setStyleSheet("""
            QTreeWidget {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 4px;
            }
        """)
        right_layout.addWidget(QLabel("Содержимое поставки:"))
        right_layout.addWidget(self.content_tree)
        
        right_widget.setLayout(right_layout)
        
        # Добавляем виджеты в сплиттер
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 400])  # Устанавливаем начальные размеры
        
        layout.addWidget(splitter)
        self.setLayout(layout)
        self.load_archive()
        
        # Обновляем состояние кнопок при выборе элемента
        self.archive_table.itemSelectionChanged.connect(self.update_buttons)
        
        # Обработчик выбора элемента в таблице архивных поставок
        self.archive_table.itemClicked.connect(self.on_shipment_selected)
    
    def load_archive(self):
        """Загрузить список архивных поставок"""
        self.archive_table.setRowCount(0)  # Очищаем таблицу
        archived_shipments = database.get_archived_shipments()
        for row_idx, shipment_data in enumerate(archived_shipments):
            # shipment_data может быть кортежем или словарем в зависимости от типа БД
            if isinstance(shipment_data, dict):
                shipment_name = shipment_data.get('destination_name', 'Unknown')
                archived_date = shipment_data.get('archived_date', 'Unknown')
                archived_by = shipment_data.get('archived_by', 'Unknown')
                parent_group = shipment_data.get('parent_group', '')
            else:
                shipment_name, archived_date, archived_by = shipment_data[:3]
                # Загружаем также parent_group из базы данных
                shipment_details = database.execute_query(
                    "SELECT parent_group FROM shipments WHERE destination_name = %s",
                    (shipment_name,),
                    fetchone=True
                )
                parent_group = shipment_details[0] if shipment_details else ''
            
            # Преобразуем datetime в строку, если это необходимо
            if hasattr(archived_date, 'strftime'):  # Это datetime объект
                archived_date = archived_date.strftime('%Y-%m-%d %H:%M:%S')
            elif archived_date is None:
                archived_date = 'Unknown'
            else:
                archived_date = str(archived_date)
            
            # Увеличиваем количество строк в таблице
            self.archive_table.setRowCount(row_idx + 1)
            
            # Создаем элементы для каждой колонки
            shipment_item = QTableWidgetItem(shipment_name)
            group_item = QTableWidgetItem(parent_group if parent_group else '')
            date_item = QTableWidgetItem(archived_date)
            archived_by_item = QTableWidgetItem(archived_by)
            
            # Устанавливаем флаги для запрета редактирования
            shipment_item.setFlags(shipment_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            archived_by_item.setFlags(archived_by_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            # Устанавливаем данные в ячейки
            self.archive_table.setItem(row_idx, 0, shipment_item)
            self.archive_table.setItem(row_idx, 1, group_item)
            self.archive_table.setItem(row_idx, 2, date_item)
            self.archive_table.setItem(row_idx, 3, archived_by_item)
            
            # Сохраняем имя поставки в первом элементе строки для дальнейшего использования
            shipment_item.setData(Qt.ItemDataRole.UserRole, shipment_name)
            
        # Устанавливаем размеры столбцов
        self.archive_table.resizeColumnsToContents()
        self.archive_table.setSortingEnabled(True) # Включаем сортировку по клику на заголовки
    
    def update_buttons(self):
        """Обновить состояние кнопок в зависимости от выбора"""
        has_selection = len(self.archive_table.selectedItems()) > 0
        self.restore_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
    
    def show_shipment_content(self, shipment_name):
        """Показать содержимое выбранной поставки"""
        # Загружаем данные поставки из базы данных
        shipment_data = database.execute_query(
            """
            SELECT id, destination_name, font_size, label_font_size, theme, removed_items, parent_group, properties,
                   archived, archived_date, archived_by
            FROM shipments
            WHERE destination_name = %s AND archived = %s
            """,
            (shipment_name, True),
            fetchall=True
        )
        
        if not shipment_data:
            QMessageBox.warning(self, "Ошибка", f"Поставка '{shipment_name}' не найдена в архиве!")
            return
        
        # Получаем ID поставки для загрузки коробок и товаров
        shipment_id = shipment_data[0][0]

        # Загружаем коробки
        db_type = get_db_type()
        if db_type == "sqlite":
            # SQLite-совместимый запрос без regex
            boxes_data = database.execute_query(
                """
                SELECT id, box_id, is_current
                FROM boxes
                WHERE shipment_id = ?
                ORDER BY box_id
                """,
                (shipment_id,),
                fetchall=True
            )
        else:
            # PostgreSQL запрос с сортировкой по номеру коробки
            boxes_data = database.execute_query(
                """
                SELECT id, box_id, is_current
                FROM boxes
                WHERE shipment_id = %s
                ORDER BY
                    CASE
                        WHEN box_id ~ '^[0-9]+$' THEN CAST(box_id AS INTEGER)
                        WHEN box_id ~ '[0-9]+' THEN CAST(REGEXP_REPLACE(box_id, '[^0-9]', '', 'g') AS INTEGER)
                        ELSE 9999
                    END
                """,
                (shipment_id,),
                fetchall=True
            )
        
        # Очищаем дерево содержимого
        self.content_tree.clear()
        
        # Создаем корневой элемент для поставки
        shipment_item = QTreeWidgetItem([f"Поставка: {shipment_name}", "", ""])
        shipment_item.setExpanded(True)
        self.content_tree.addTopLevelItem(shipment_item)
        
        # Загружаем содержимое коробок
        for box_row in boxes_data:
            box_db_id, box_id, is_current = box_row
            box_items = database.execute_query(
                """
                SELECT barcode, qty
                FROM box_items
                WHERE box_id = %s
                """,
                (box_db_id,),
                fetchall=True
            )
            
            # Создаем элемент коробки
            box_item = QTreeWidgetItem([f"{box_id}", "", ""])
            box_item.setExpanded(True)
            shipment_item.addChild(box_item)
            
            # Загружаем товары в коробке
            for item_barcode, qty in box_items:
                # Получаем артикул товара
                item_data = database.execute_query(
                    """
                    SELECT sku
                    FROM shipment_items
                    WHERE shipment_id = %s AND barcode = %s
                    """,
                    (shipment_id, item_barcode),
                    fetchall=True
                )
                
                sku = item_data[0][0] if item_data else "Неизвестный"
                
                # Создаем элемент товара
                item = QTreeWidgetItem([item_barcode, sku, str(qty)])
                box_item.addChild(item)
        
        # Устанавливаем ширину столбцов по содержимому
        self.content_tree.resizeColumnToContents(0)
        self.content_tree.resizeColumnToContents(1)
        self.content_tree.resizeColumnToContents(2)
    
    def show_shipments_list(self):
        """Вернуться к списку поставок"""
        self.tabs.setCurrentIndex(0)
        self.tabs.setTabEnabled(1, False)
    
    def restore_shipment(self):
        """Восстановить выбранную поставку из архива"""
        selected_items = self.archive_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Ошибка", "Выберите поставку для восстановления!")
            return
        
        item = selected_items[0]
        shipment_name = item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Вы уверены, что хотите восстановить поставку '{shipment_name}' из архива?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if database.unarchive_shipment(shipment_name):
                QMessageBox.information(self, "Успех", f"Поставка '{shipment_name}' восстановлена из архива!")
                self.load_archive()  # Обновляем список архивных поставок
                # Обновляем UI в главном окне для отображения восстановленной поставки
                if self.parent():
                    parent = self.parent()
                    # Ищем главное окно
                    while parent and not hasattr(parent, 'load_all_data'):
                        parent = parent.parent() if parent.parent() else None
                    if parent:
                        # Загружаем все данные, чтобы восстановленная поставка появилась в списке
                        parent.load_all_data()
                        # Обновляем интерфейс, чтобы отразить изменения
                        parent.update_ui()
                        # Обновляем дерево поставок для немедленного отображения
                        parent.ui_updater.update_shipments_tree()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось восстановить поставку!")
    
    def delete_shipment(self):
        """Удалить выбранную поставку навсегда"""
        selected_items = self.archive_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Ошибка", "Выберите поставку для удаления!")
            return
        
        item = selected_items[0]
        shipment_name = item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Вы уверены, что хотите удалить поставку '{shipment_name}' навсегда?\nЭто действие нельзя отменить!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if database.delete_archived_shipment(shipment_name):
                QMessageBox.information(self, "Успех", f"Поставка '{shipment_name}' удалена навсегда!")
                self.load_archive() # Обновляем список
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось удалить поставку!")
    
    def showEvent(self, event):
        """Переопределяем событие отображения для обновления списка при открытии диалога"""
        super().showEvent(event)
        # Подключаем обработчик клика по элементу списка
        self.archive_table.itemClicked.connect(self.on_shipment_selected)
    
    def on_shipment_selected(self, item):
        """Обработка выбора поставки - показываем её содержимое"""
        # Получаем имя поставки из первого столбца текущей строки
        row = item.row()
        shipment_item = self.archive_table.item(row, 0)
        if shipment_item:
            shipment_name = shipment_item.data(Qt.ItemDataRole.UserRole)
            self.show_shipment_content(shipment_name)


class QuantityEditDialog(QDialog):
    """
    Диалоговое окно для редактирования количества товара в коробке
    """
    
    def __init__(self, current_quantity, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Изменить количество")
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Метка
        label = QLabel("Введите новое количество:")
        layout.addWidget(label)
        
        # Поле ввода количества
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(0, 99999)  # Устанавливаем диапазон
        self.quantity_input.setValue(current_quantity)
        self.quantity_input.selectAll()  # Выделяем весь текст для удобства редактирования
        layout.addWidget(self.quantity_input)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        buttons_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        
        # Устанавливаем фокус на поле ввода
        self.quantity_input.setFocus()
        
        # Устанавливаем код возврата при нажатии Enter
        ok_button.setDefault(True)
        
        # Устанавливаем размер окна
        self.resize(250, 100)

    def get_quantity(self):
        """Получить введенное количество"""
        return self.quantity_input.value()


class BoxNumberDialog(QDialog):
    """
    Диалог для ввода номера коробки
    """
    
    def __init__(self, current_number="", existing_numbers=None, parent=None):
        super().__init__(parent)
        self.existing_numbers = existing_numbers or []
        self.setWindowTitle("Номер коробки")
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Метка
        label = QLabel("Введите номер коробки:")
        layout.addWidget(label)
        
        # Поле ввода номера
        self.number_input = QLineEdit(current_number)
        layout.addWidget(self.number_input)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.validate_and_accept)
        buttons_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        
        # Устанавливаем фокус на поле ввода
        self.number_input.setFocus()
        
        # Устанавливаем код возврата при нажатии Enter
        ok_button.setDefault(True)
        
        # Устанавливаем размер окна
        self.resize(250, 100)
    
    def validate_and_accept(self):
        """Проверить введенный номер и принять, если он корректен"""
        new_number = self.number_input.text().strip()
        if not new_number:
            QMessageBox.warning(self, "Ошибка", "Введите номер коробки!")
            return
        
        if new_number in self.existing_numbers:
            QMessageBox.warning(self, "Ошибка", f"Коробка с номером '{new_number}' уже существует!")
            return
        
        self.accept()
    
    def get_new_number(self):
        """Получить введенный номер коробки"""
        return self.number_input.text().strip()