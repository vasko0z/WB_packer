"""
Модуль для диалога проверки остатков по штрихкоду
"""
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QMessageBox,
    QFrame
)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont

from moysklad_api import MoyskladAPI
import database
from main_window import MainWindow


class StockCheckWorker(QThread):
    """
    Рабочий поток для проверки остатков
    """
    finished = pyqtSignal(dict, str)  # Словарь остатков и сообщение об ошибке
    
    def __init__(self, barcode, token, store_ids):
        super().__init__()
        self.barcode = barcode
        self.token = token
        self.store_ids = store_ids
        
    def run(self):
        try:
            api = MoyskladAPI(self.token)
            
            # Сначала ищем товар по штрихкоду
            product = api._find_product_by_barcode(self.barcode)
            if not product:
                self.finished.emit({}, f"Товар с штрихкодом {self.barcode} не найден в МойСклад")
                return
                
            product_id = product['id']
            product_name = product.get('name', 'Неизвестный товар')
            
            # Получаем остатки по выбранным складам для найденного товара
            stocks_data = api.get_stock_by_stores([self.barcode], self.store_ids)
            
            # Формируем результат
            result = {
                'product_name': product_name,
                'product_id': product_id,
                'stocks': {}
            }
            
            # Обрабатываем данные в формате {barcode: {store_id: quantity}}
            if isinstance(stocks_data, dict) and self.barcode in stocks_data:
                stores_for_barcode = stocks_data[self.barcode]
                for store_id, quantity in stores_for_barcode.items():
                    # Проверяем, если store_ids заданы, то фильтруем только по ним
                    if not self.store_ids or store_id in self.store_ids:
                        store_name = f"Склад {store_id}"
                        # Для простого метода get_stock_by_stores, quantity - это общий остаток,
                        # а не раздельные значения stock, reserve, in_transit
                        result['stocks'][store_name] = {
                            'stock': quantity,
                            'reserve': 0,  # Значение по умолчанию
                            'in_transit': 0  # Значение по умолчанию
                        }
            
            self.finished.emit(result, "")
            
        except Exception as e:
            self.finished.emit({}, f"Ошибка при получении остатков: {str(e)}")


class CheckStockDialog(QDialog):
    """
    Диалог для проверки остатков по штрихкоду
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр остатка МС")
        self.setModal(True)
        self.resize(600, 500)
        
        self.worker = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Поле ввода штрихкода
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Штрихкод:"))
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Введите штрихкод для проверки остатков")
        self.barcode_input.returnPressed.connect(self.check_stock)
        input_layout.addWidget(self.barcode_input)
        
        # Кнопка проверки
        self.check_btn = QPushButton("Проверить остаток")
        self.check_btn.clicked.connect(self.check_stock)
        input_layout.addWidget(self.check_btn)
        
        layout.addLayout(input_layout)
        
        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Результаты
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setFont(QFont("Courier New", 10))
        layout.addWidget(self.results_text)
        
        # Кнопка закрытия
        close_btn_layout = QHBoxLayout()
        close_btn_layout.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.close)
        close_btn_layout.addWidget(close_btn)
        layout.addLayout(close_btn_layout)
        
    def check_stock(self):
        """
        Проверить остатки по введенному штрихкоду
        """
        barcode = self.barcode_input.text().strip()
        if not barcode:
            QMessageBox.warning(self, "Ошибка", "Введите штрихкод для проверки")
            return
            
        # Получаем настройки пользователя
        try:
            if hasattr(self.parent(), 'current_user'):
                current_user = self.parent().current_user
            else:
                # Пытаемся получить пользователя другим способом
                main_window = self.get_main_window()
                if main_window and hasattr(main_window, 'current_user'):
                    current_user = main_window.current_user
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось получить данные пользователя")
                    return
                    
            user_settings = database.get_user_settings(current_user)
            if not user_settings or not user_settings.get('moysklad_enabled', True):
                QMessageBox.warning(self, "Ошибка", "Интеграция с МойСклад отключена. Включите интеграцию в настройках.")
                return
                
            if not user_settings or not user_settings.get('moysklad_token'):
                QMessageBox.warning(self, "Ошибка", "Токен МойСклад не настроен. Проверьте настройки интеграции.")
                return
                
            # Получаем ID складов для синхронизации
            store_ids = []
            try:
                stores_str = user_settings.get('moysklad_stores', '[]')
                store_ids = json.loads(stores_str)
            except json.JSONDecodeError:
                store_ids = []
                
            # Отключаем кнопку и поле ввода во время запроса
            self.check_btn.setEnabled(False)
            self.barcode_input.setEnabled(False)
            self.results_text.setPlainText("Получение данных из МойСклад...")
            
            # Запускаем рабочий поток
            self.worker = StockCheckWorker(barcode, user_settings['moysklad_token'], store_ids)
            self.worker.finished.connect(self.on_stock_check_finished)
            self.worker.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при проверке остатков:\n{str(e)}")
            self.check_btn.setEnabled(True)
            self.barcode_input.setEnabled(True)
            
    def on_stock_check_finished(self, result, error):
        """
        Обработчик завершения проверки остатков
        """
        # Возвращаем кнопку и поле ввода в активное состояние
        self.check_btn.setEnabled(True)
        self.barcode_input.setEnabled(True)
        
        if error:
            QMessageBox.warning(self, "Ошибка", error)
            self.results_text.setPlainText(error)
            return
            
        # Формируем отчет об остатках в простом формате
        if not result['stocks']:
            text = f"Остаток: 0"
            self.results_text.setPlainText(text)
        else:
            total_stock = 0
            
            for store_name, stock_data in result['stocks'].items():
                stock = stock_data['stock']
                total_stock += stock
            
            text = f"Остаток: {total_stock}"
            self.results_text.setPlainText(text)
            
    def get_main_window(self):
        """
        Вспомогательный метод для получения главного окна
        """
        parent = self.parent()
        while parent:
            if isinstance(parent, MainWindow):
                return parent
            parent = parent.parent()
        return None
        
    def closeEvent(self, event):
        """
        Обработка закрытия окна
        """
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        event.accept()


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = CheckStockDialog()
    dialog.show()
    sys.exit(app.exec())