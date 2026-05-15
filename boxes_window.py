from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem,
                             QHeaderView, QMessageBox, QTableWidget)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import sessionmaker
from models import Shipment, Box, engine

class BoxesWindow(QWidget):
    def __init__(self, shipment_id):
        super().__init__()
        self.shipment_id = shipment_id
        self.Session = sessionmaker(bind=engine)
        self.setWindowTitle(f"Коробки поставки #{shipment_id}")
        self.setGeometry(150, 150, 600, 400)
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["ID коробки", "Название коробки"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(self.show_box_contents)
        
        layout.addWidget(self.table)
        self.setLayout(layout)
        
        self.load_boxes()
    
    def load_boxes(self):
        session = self.Session()
        shipment = session.query(Shipment).get(self.shipment_id)
        
        # Функция для извлечения числового значения из ID коробки для правильной сортировки
        def get_box_number(box):
            try:
                # Поддерживаем оба возможных названия поля
                box_name = getattr(box, 'box_id', None) or getattr(box, 'name', '')
                if box_name:
                    # Обрабатываем оба формата: "Коробка-" (с дефисом) и "Коробка " (с пробелом)
                    if box_name.startswith("Коробка-"):
                        # Извлекаем числовую часть и возвращаем как целое число для правильной сортировки
                        number_part = box_name.split("-")[1]
                        # Проверяем, является ли следующая часть числом
                        return int(''.join(filter(str.isdigit, number_part)))
                    elif box_name.startswith("Коробка "):
                        # Извлекаем числовую часть после пробела
                        number_part = box_name.split(" ", 1)[1]  # Разделяем по первому пробелу
                        # Проверяем, является ли следующая часть числом
                        return int(''.join(filter(str.isdigit, number_part)))
                return 0
            except (IndexError, ValueError, AttributeError):
                return 0
        
        # Сортируем коробки по числовому значению в их имени
        sorted_boxes = sorted(shipment.boxes, key=get_box_number)
        
        self.table.setRowCount(len(sorted_boxes))
        for row, box in enumerate(sorted_boxes):
            box_name = getattr(box, 'box_id', None) or getattr(box, 'name', 'Неизвестная коробка')
            self.table.setItem(row, 0, QTableWidgetItem(str(box.id)))
            self.table.setItem(row, 1, QTableWidgetItem(box_name))
        
        session.close()
    
    def show_box_contents(self):
        current_row = self.table.currentRow()
        if current_row == -1:
            return
            
        box_id = int(self.table.item(current_row, 0).text())
        
        session = self.Session()
        box = session.query(Box).get(box_id)
        
        contents_window = QWidget()
        contents_window.setWindowTitle(f"Содержимое коробки #{box_id}")
        contents_window.setGeometry(200, 200, 500, 300)
        contents_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        
        layout = QVBoxLayout()
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Штрихкод", "Артикул", "Количество"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Получаем товары в коробке из атрибута items
        items_list = list(box.items.items())
        table.setRowCount(len(items_list))
        for row, (barcode, quantity) in enumerate(items_list):
            # Получаем артикул из связанной поставки
            sku = "Неизвестный артикул"  # Значение по умолчанию
            # Попробуем найти артикул в поставке, используя переданный shipment_id
            shipment = session.query(Shipment).get(self.shipment_id)
            if shipment and barcode in shipment.shipment_items:
                sku = shipment.shipment_items[barcode].sku
            else:
                # Если артикул не найден в shipment_items, ищем в removed_items
                if shipment and barcode in shipment.removed_items:
                    sku = shipment.removed_items[barcode]['sku']
            
            table.setItem(row, 0, QTableWidgetItem(str(barcode)))
            table.setItem(row, 1, QTableWidgetItem(sku))
            table.setItem(row, 2, QTableWidgetItem(str(quantity)))
        
        layout.addWidget(table)
        contents_window.setLayout(layout)
        contents_window.show()
        
        session.close()