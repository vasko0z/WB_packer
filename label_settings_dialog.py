import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                           QLineEdit, QPushButton, QFormLayout, QSpinBox,
                           QMessageBox)
from PyQt6.QtCore import Qt


class LabelSettingsDialog(QDialog):
   def __init__(self, parent=None):
       super().__init__(parent)
       self.setWindowTitle("Настройки печати этикеток")
       self.setModal(True)
       self.resize(400, 300)
       
       layout = QVBoxLayout()
       self.setLayout(layout)
       
       # Создаем форму для настроек
       form_layout = QFormLayout()
       
       # Размеры шрифтов
       self.title_font_size = QSpinBox()
       self.title_font_size.setRange(8, 30)
       self.title_font_size.setValue(12)
       form_layout.addRow("Размер шрифта заголовков:", self.title_font_size)
       
       self.value_font_size = QSpinBox()
       self.value_font_size.setRange(8, 30)
       self.value_font_size.setValue(14)
       form_layout.addRow("Размер шрифта значений:", self.value_font_size)
       
       self.barcode_font_size = QSpinBox()
       self.barcode_font_size.setRange(8, 30)
       self.barcode_font_size.setValue(14)
       form_layout.addRow("Размер шрифта штрихкода:", self.barcode_font_size)
       
       # Количество символов до переноса строки
       self.name_line_wrap = QSpinBox()
       self.name_line_wrap.setRange(10, 50)
       self.name_line_wrap.setValue(16)
       form_layout.addRow("Перенос наименования (символов):", self.name_line_wrap)
       
       self.article_line_wrap = QSpinBox()
       self.article_line_wrap.setRange(10, 50)
       self.article_line_wrap.setValue(16)
       form_layout.addRow("Перенос артикула (символов):", self.article_line_wrap)
       
       # Убираем настройку переноса штрихкода, так как штрихкод не нуждается в переносе
       
       layout.addLayout(form_layout)
       
       # Кнопки OK и Отмена
       buttons_layout = QHBoxLayout()
       
       ok_btn = QPushButton("OK")
       ok_btn.clicked.connect(self.accept)
       buttons_layout.addWidget(ok_btn)
       
       cancel_btn = QPushButton("Отмена")
       cancel_btn.clicked.connect(self.reject)
       buttons_layout.addWidget(cancel_btn)
       
       layout.addLayout(buttons_layout)
       
       # Загружаем сохраненные настройки
       self.load_settings()
   
   def load_settings(self):
       """Загружает сохраненные настройки из общей базы данных"""
       try:
           from database import execute_query
           result = execute_query(
               "SELECT value FROM app_settings WHERE key = 'label_print_settings'",
               fetchone=True
           )
           
           if result:
               settings = json.loads(result[0])
               
               self.title_font_size.setValue(settings.get('title_font_size', 12))
               self.value_font_size.setValue(settings.get('value_font_size', 14))
               self.barcode_font_size.setValue(settings.get('barcode_font_size', 14))
               self.name_line_wrap.setValue(settings.get('name_line_wrap', 16))
               self.article_line_wrap.setValue(settings.get('article_line_wrap', 16))
               # Убираем загрузку barcode_line_wrap, так как эта настройка больше не используется
           else:
               # Если настройки не найдены в базе, используем значения по умолчанию
               # (уже установлены при создании виджетов)
               pass
       except Exception as e:
           QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить настройки из базы данных: {str(e)}")
   
   def save_settings(self):
       """Сохраняет настройки в общую базу данных"""
       settings = {
           'title_font_size': self.title_font_size.value(),
           'value_font_size': self.value_font_size.value(),
           'barcode_font_size': self.barcode_font_size.value(),
           'name_line_wrap': self.name_line_wrap.value(),
           'article_line_wrap': self.article_line_wrap.value()
           # Убираем barcode_line_wrap, так как для штрихкода не нужен перенос строк
       }
       
       try:
           from database import execute_query
           # Сохраняем настройки в таблицу app_settings
           execute_query(
               """
               INSERT INTO app_settings (key, value) VALUES (%s, %s)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
               """,
               ('label_print_settings', json.dumps(settings, ensure_ascii=False))
           )
       except Exception as e:
           QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки в базу данных: {str(e)}")
   
   def accept(self):
       """Переопределяем метод accept для сохранения настроек в базу данных при OK"""
       self.save_settings()
       super().accept()