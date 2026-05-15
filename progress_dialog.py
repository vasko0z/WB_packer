"""
Модуль для отображения прогресса синхронизации остатков с МойСклад
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QObject
import threading


class ProgressDialog(QDialog):
    """
    Диалог с прогресс-баром для отображения прогресса синхронизации
    """
    
    def __init__(self, parent=None, title="Синхронизация", label_text="Выполняется синхронизация..."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(400, 100)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)  # Убираем кнопку закрытия
        
        layout = QVBoxLayout(self)
        
        # Метка с описанием
        self.label = QLabel(label_text)
        layout.addWidget(self.label)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Неопределенный прогресс
        layout.addWidget(self.progress_bar)
        
        # Кнопка отмены (временно скрыта, так как синхронизация не должна прерываться)
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        # Центральное расположение
        self.center_on_screen()
    
    def center_on_screen(self):
        """Центрирует диалог на экране"""
        screen_geometry = self.screen().availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
    
    def set_progress_text(self, text):
        """Устанавливает текст прогресса"""
        self.label.setText(text)
    
    def set_progress(self, value, max_value=100):
        """Устанавливает значение прогресса"""
        self.progress_bar.setRange(0, max_value)
        self.progress_bar.setValue(value)
    
    def set_indeterminate(self):
        """Устанавливает неопределенный прогресс"""
        self.progress_bar.setRange(0, 0)


class SyncWorker(QObject):
    """
    Рабочий класс для синхронизации остатков в отдельном потоке
    """
    finished = pyqtSignal(object)  # Сигнал завершения с результатом
    error = pyqtSignal(str)        # Сигнал ошибки
    
    def __init__(self, api, barcodes, selected_stores):
        super().__init__()
        self.api = api
        self.barcodes = barcodes
        self.selected_stores = selected_stores
    
    def run_sync(self):
        """Выполняет синхронизацию остатков"""
        try:
            # Используем более эффективный метод пакетного получения остатков
            filtered_stocks = self.api.get_stocks_for_barcodes_batch(
                self.barcodes, 
                self.selected_stores
            )
            
            # Отправляем результат
            self.finished.emit(filtered_stocks)
        except Exception as e:
            # Отправляем ошибку
            self.error.emit(str(e))