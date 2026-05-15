"""
Модуль для диалога настроек интеграции с МойСклад
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFormLayout, QMessageBox, QListWidget, QListWidgetItem, QGroupBox
)
from PyQt6.QtCore import Qt
import database
import json
from image_check_box import ImageCheckBox


class MoyskladSettingsDialog(QDialog):
    """
    Диалог настроек интеграции с МойСклад
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки интеграции с МойСклад")
        self.setModal(True)
        self.resize(600, 500)
        
        self.main_window = parent
        self.current_user = parent.current_user if parent else "Default"
        
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        layout = QVBoxLayout()
        
        # Форма для основных настроек
        form_group = QGroupBox("Основные настройки")
        form_layout = QFormLayout()
        
        # Чекбокс для включения интеграции
        self.enabled_checkbox = ImageCheckBox("Включить интеграцию")
        self.enabled_checkbox.setStyleSheet("QCheckBox::indicator { width: 0; height: 0; }")
        form_layout.addRow(self.enabled_checkbox)
        
        # Поле для токена
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)  # Скрываем токен
        form_layout.addRow("Токен доступа:", self.token_input)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Список складов
        stores_group = QGroupBox("Склады для отображения остатков")
        stores_layout = QVBoxLayout()
        
        self.stores_list = QListWidget()
        self.stores_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        stores_layout.addWidget(self.stores_list)
        
        # Кнопки для управления складами
        buttons_layout = QHBoxLayout()
        
        self.test_connection_btn = QPushButton("Проверка связи")
        self.test_connection_btn.clicked.connect(self.test_connection)
        buttons_layout.addWidget(self.test_connection_btn)
        
        self.load_stores_btn = QPushButton("Загрузить склады из МойСклад")
        self.load_stores_btn.clicked.connect(self.load_stores_from_api)
        buttons_layout.addWidget(self.load_stores_btn)
        
        buttons_layout.addStretch()
        
        stores_group = QGroupBox("Склады для отображения остатков")
        stores_group_layout = QVBoxLayout()
        stores_group_layout.addWidget(self.stores_list)
        stores_group_layout.addLayout(buttons_layout)  # Перемещаем кнопки внутрь группы
        stores_group.setLayout(stores_group_layout)
        layout.addWidget(stores_group)
        
        # Кнопки OK/Cancel/Сохранить
        action_buttons_layout = QHBoxLayout()
        
        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self.save_settings)
        action_buttons_layout.addWidget(save_button)
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        action_buttons_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        action_buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(action_buttons_layout)
        
        self.setLayout(layout)
    
    def load_settings(self):
        """Загрузка сохраненных настроек"""
        try:
            # Настройки МойСклад теперь глобальные (для всех пользователей)
            moysklad_token = database.get_moysklad_token()
            moysklad_enabled = database.get_moysklad_enabled()
            stores_str = database.get_moysklad_stores() or '[]'
            
            self.token_input.setText(moysklad_token)
            self.enabled_checkbox.setChecked(moysklad_enabled)

            # Загружаем сохраненные склады
            try:
                saved_stores = json.loads(stores_str)
                # Заполняем список складов
                self.populate_stores_list(saved_stores)
            except json.JSONDecodeError:
                # Если не удается распарсить JSON, используем пустой список
                self.populate_stores_list([])
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить настройки: {str(e)}")

    def showEvent(self, event):
        """Обработка события отображения диалога"""
        super().showEvent(event)
        # При открытии диалога проверяем, есть ли токен, и если есть - автоматически загружаем склады
        moysklad_token = database.get_moysklad_token()
        if moysklad_token and moysklad_token.strip():
            # Загружаем склады из API, чтобы пользователь сразу видел актуальный список
            self.load_stores_from_api()
    
    def populate_stores_list(self, saved_stores):
        """Заполнение списка складов"""
        # Очищаем текущий список
        self.stores_list.clear()
        
        # Если есть сохраненные склады, то отображаем их
        # В противном случае список остается пустым до загрузки из API
        if saved_stores:
            # Пытаемся получить реальные названия складов из API
            token = self.token_input.text().strip()
            if token:
                try:
                    from moysklad_api import MoyskladAPI
                    api = MoyskladAPI(token)
                    stores = api.get_stores()
                    
                    # Создаем словарь соответствия ID склада и его названия
                    stores_dict = {store["id"]: store["name"] for store in stores}
                    
                    for store_id in saved_stores:
                        store_name = stores_dict.get(store_id, f"Склад {store_id}")
                        item = QListWidgetItem(store_name)
                        item.setData(Qt.ItemDataRole.UserRole, store_id)
                        item.setCheckState(Qt.CheckState.Checked)
                        self.stores_list.addItem(item)
                except Exception:
                    # Если не удалось получить реальные данные, используем ID складов
                    for store_id in saved_stores:
                        item = QListWidgetItem(f"Склад {store_id}")
                        item.setData(Qt.ItemDataRole.UserRole, store_id)
                        item.setCheckState(Qt.CheckState.Checked)
                        self.stores_list.addItem(item)
            else:
                # Если токена нет, просто отображаем ID складов
                for store_id in saved_stores:
                    item = QListWidgetItem(f"Склад {store_id}")
                    item.setData(Qt.ItemDataRole.UserRole, store_id)
                    item.setCheckState(Qt.CheckState.Checked)
                    self.stores_list.addItem(item)
    
    def load_stores_from_api(self):
        """Загрузка списка складов из API МойСклад"""
        try:
            token = self.token_input.text().strip()
            if not token:
                QMessageBox.warning(self, "Ошибка", "Введите токен доступа к МойСклад")
                return
            
            # Импортируем класс API
            from moysklad_api import MoyskladAPI
            api = MoyskladAPI(token)
            
            # Получаем список складов
            stores = api.get_stores()
            
            # Загружаем текущие выбранные склады
            current_selection = []
            for i in range(self.stores_list.count()):
                item = self.stores_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    current_selection.append(item.data(Qt.ItemDataRole.UserRole))
            
            # Обновляем список складов
            self.stores_list.clear()
            for store in stores:
                item = QListWidgetItem(store["name"])
                item.setData(Qt.ItemDataRole.UserRole, store["id"])  # Сохраняем ID склада
                # Сохраняем предыдущий статус выбора
                item.setCheckState(Qt.CheckState.Checked if store["id"] in current_selection else Qt.CheckState.Unchecked)
                self.stores_list.addItem(item)
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить склады из МойСклад:\n{str(e)}")
    
    def test_connection(self):
        """Проверка связи с API МойСклад"""
        try:
            # Импортируем requests для обработки ошибок
            import requests
        except ImportError:
            QMessageBox.critical(self, "Ошибка", "Модуль requests не установлен. Обратитесь к администратору.")
            return

        try:
            token = self.token_input.text().strip()
            if not token:
                QMessageBox.warning(self, "Ошибка", "Введите токен доступа к МойСклад")
                return

            # Импортируем класс API
            from moysklad_api import MoyskladAPI
            api = MoyskladAPI(token)

            # Проверяем соединение, например, делая простой запрос к API
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json;charset=utf-8"
            }
            response = requests.get("https://api.moysklad.ru/api/remap/1.2/context/employee", headers=headers)
            response.raise_for_status()

            # Если запрос прошел успешно, значит токен действителен
            user_info = response.json()
            # Получаем имя из firstName и lastName или используем shortFio
            first_name = user_info.get('firstName', '')
            last_name = user_info.get('lastName', '')
            user_name = f"{first_name} {last_name}".strip() if first_name or last_name else user_info.get('shortFio', 'Пользователь')

            # Загружаем список складов
            stores = api.get_stores()

            if stores:
                # Автоматически загружаем список складов в интерфейс
                # Загружаем текущие выбранные склады
                current_selection = []
                for i in range(self.stores_list.count()):
                    item = self.stores_list.item(i)
                    if item.checkState() == Qt.CheckState.Checked:
                        current_selection.append(item.data(Qt.ItemDataRole.UserRole))

                # Обновляем список складов
                self.stores_list.clear()
                for store in stores:
                    item = QListWidgetItem(store["name"])
                    item.setData(Qt.ItemDataRole.UserRole, store["id"])  # Сохраняем ID склада
                    # Сохраняем предыдущий статус выбора
                    item.setCheckState(Qt.CheckState.Checked if store["id"] in current_selection else Qt.CheckState.Unchecked)
                    self.stores_list.addItem(item)

                QMessageBox.information(self, "Успешно", f"Связь с МойСклад установлена!\nПользователь: {user_name}\nНайдено складов: {len(stores)}")
            else:
                QMessageBox.information(self, "Успешно", f"Связь с МойСклад установлена!\nПользователь: {user_name}\nСклады не найдены или доступ к ним ограничен")

        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                QMessageBox.critical(self, "Ошибка", f"Не удалось установить связь с МойСклад:\nНеверный токен доступа")
            elif response.status_code == 403:
                QMessageBox.critical(self, "Ошибка", f"Не удалось установить связь с МойСклад:\nДоступ запрещен")
            else:
                QMessageBox.critical(self, "Ошибка", f"Не удалось установить связь с МойСклад:\nHTTP ошибка: {response.status_code}")
        except Exception as e:
            # Если не сработал первый метод, пробуем использовать метод из API класса
            try:
                from moysklad_api import MoyskladAPI
                api = MoyskladAPI(token)

                # Проверяем соединение, получая список складов
                stores = api.get_stores()

                if stores:
                    # Автоматически загружаем список складов в интерфейс
                    # Загружаем текущие выбранные склады
                    current_selection = []
                    for i in range(self.stores_list.count()):
                        item = self.stores_list.item(i)
                        if item.checkState() == Qt.CheckState.Checked:
                            current_selection.append(item.data(Qt.ItemDataRole.UserRole))

                    # Обновляем список складов
                    self.stores_list.clear()
                    for store in stores:
                        item = QListWidgetItem(store["name"])
                        item.setData(Qt.ItemDataRole.UserRole, store["id"])  # Сохраняем ID склада
                        # Сохраняем предыдущий статус выбора
                        item.setCheckState(Qt.CheckState.Checked if store["id"] in current_selection else Qt.CheckState.Unchecked)
                        self.stores_list.addItem(item)

                    QMessageBox.information(self, "Успешно", f"Связь с МойСклад установлена!\nНайдено складов: {len(stores)}")
                else:
                    QMessageBox.information(self, "Успешно", "Связь с МойСклад установлена, но склады не найдены или недоступны")
            except Exception as secondary_e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось установить связь с МойСклад:\n{str(secondary_e)}")
    
    def get_selected_stores(self):
        """Получить список выбранных складов"""
        selected_stores = []
        for i in range(self.stores_list.count()):
            item = self.stores_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                store_id = item.data(Qt.ItemDataRole.UserRole)
                selected_stores.append(store_id)
        return selected_stores
    
    def save_settings(self):
        """Сохранение настроек без закрытия диалога"""
        try:
            # Получаем значения настроек МойСклад из интерфейса
            moysklad_token = self.token_input.text().strip()
            moysklad_enabled = self.enabled_checkbox.isChecked()
            selected_stores = self.get_selected_stores()
            moysklad_stores = json.dumps(selected_stores, ensure_ascii=False)

            # Сохраняем глобальные настройки МойСклад (для всех пользователей)
            database.set_moysklad_token(moysklad_token)
            database.set_moysklad_stores(moysklad_stores)
            database.set_moysklad_enabled(moysklad_enabled)

            QMessageBox.information(self, "Успешно", "Настройки интеграции с МойСклад сохранены!")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки:\n{str(e)}")
    
    def accept(self):
        """Сохранение настроек при нажатии OK"""
        # Сохраняем настройки
        self.save_settings()
        
        # Закрываем диалог
        super().accept()