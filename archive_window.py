from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget,
                             QTreeWidgetItem, QPushButton, QMessageBox, QMenu,
                             QAction, QHeaderView, QAbstractItemView)
from PyQt6.QtCore import Qt
from sqlalchemy.orm import sessionmaker
from models import Shipment, GroupShipment, engine


class ArchiveWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Архив поставок")
        self.setGeometry(100, 100, 1000, 600)
        self.Session = sessionmaker(bind=engine)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # Дерево архивированных поставок
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["ID", "Название", "Группа", "Дата создания", "Дата архивации"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        layout.addWidget(self.tree)
        
        # Кнопки управления
        button_layout = QHBoxLayout()
        
        self.delete_btn = QPushButton("Удалить из архива")
        self.delete_btn.clicked.connect(self.delete_shipment)
        
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.load_data)
        
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self.load_data()
    
    def load_data(self):
        session = self.Session()
        try:
            # Загружаем все архивные поставки и групповые поставки
            shipments = session.query(Shipment).filter(Shipment.archived == True).all()
            group_shipments = session.query(GroupShipment).filter(GroupShipment.archived == True).all()
            
            # Очищаем дерево
            self.tree.clear()
            
            # Сначала создаем словарь для групповых поставок, чтобы можно было легко находить их
            group_dict = {}
            for group in group_shipments:
                group_item = QTreeWidgetItem(self.tree)
                group_item.setText(0, str(group.id))
                group_item.setText(1, group.group_name)
                group_item.setText(2, "Группа")
                group_item.setText(3, group.created_date.strftime("%Y-%m-%d %H:%M") if group.created_date else "")
                group_item.setText(4, group.archived_date.strftime("%Y-%m-%d %H:%M") if group.archived_date else "")
                # Устанавливаем роль, чтобы отличать групповые поставки от обычных
                group_item.setData(0, Qt.ItemDataRole.UserRole, "group")
                group_item.setData(0, Qt.ItemDataRole.UserRole + 1, group.id)
                group_dict[group.id] = group_item
            
            # Теперь добавляем обычные поставки
            for shipment in shipments:
                # Если поставка принадлежит группе
                if shipment.parent_group_id:
                    # Найти родительскую группу
                    parent_group_item = group_dict.get(shipment.parent_group_id)
                    
                    if parent_group_item:
                        # Добавить как дочерний элемент группы
                        child_item = QTreeWidgetItem(parent_group_item)
                        child_item.setText(0, str(shipment.id))
                        child_item.setText(1, shipment.name)
                        child_item.setText(2, shipment.parent_group.group_name if shipment.parent_group else "")
                        child_item.setText(3, shipment.created_date.strftime("%Y-%m-%d %H:%M") if shipment.created_date else "")
                        child_item.setText(4, shipment.archived_date.strftime("%Y-%m-%d %H:%M") if shipment.archived_date else "")
                        # Устанавливаем роль, чтобы отличать обычные поставки от групповых
                        child_item.setData(0, Qt.ItemDataRole.UserRole, "shipment")
                        child_item.setData(0, Qt.ItemDataRole.UserRole + 1, shipment.id)
                    else:
                        # Если группа не найдена, добавить как обычный элемент
                        item = QTreeWidgetItem(self.tree)
                        item.setText(0, str(shipment.id))
                        item.setText(1, shipment.name)
                        item.setText(2, shipment.parent_group.group_name if shipment.parent_group else "")
                        item.setText(3, shipment.created_date.strftime("%Y-%m-%d %H:%M") if shipment.created_date else "")
                        item.setText(4, shipment.archived_date.strftime("%Y-%m-%d %H:%M") if shipment.archived_date else "")
                        # Устанавливаем роль, чтобы отличать обычные поставки от групповых
                        item.setData(0, Qt.ItemDataRole.UserRole, "shipment")
                        item.setData(0, Qt.ItemDataRole.UserRole + 1, shipment.id)
                else:
                    # Обычная поставка (не входящая в группу)
                    item = QTreeWidgetItem(self.tree)
                    item.setText(0, str(shipment.id))
                    item.setText(1, shipment.name)
                    item.setText(2, shipment.parent_group.group_name if shipment.parent_group else "")
                    item.setText(3, shipment.created_date.strftime("%Y-%m-%d %H:%M") if shipment.created_date else "")
                    item.setText(4, shipment.archived_date.strftime("%Y-%m-%d %H:%M") if shipment.archived_date else "")
                    # Устанавливаем роль, чтобы отличать обычные поставки от групповых
                    item.setData(0, Qt.ItemDataRole.UserRole, "shipment")
                    item.setData(0, Qt.ItemDataRole.UserRole + 1, shipment.id)
            
            # Раскрываем все группы по умолчанию
            self.tree.expandAll()
        finally:
            session.close()
    
    def show_context_menu(self, position):
        # Получаем элемент, на котором был клик
        item = self.tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        
        # Определяем тип элемента (группа или поставка)
        item_type = item.data(0, Qt.ItemDataRole.UserRole)
        item_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
        
        if item_type == "group":
            # Для групповых поставок добавляем действие восстановления всей группы
            restore_action = QAction("Восстановить группу из архива", self)
            restore_action.triggered.connect(lambda: self.restore_group(item_id))
            menu.addAction(restore_action)
        else:
            # Для обычных поставок добавляем стандартные действия
            restore_action = QAction("Восстановить из архива", self)
            restore_action.triggered.connect(self.restore_shipment)
            menu.addAction(restore_action)
            
            view_boxes_action = QAction("Просмотреть коробки", self)
            view_boxes_action.triggered.connect(self.view_boxes)
            menu.addAction(view_boxes_action)
        
        delete_action = QAction("Удалить из архива", self)
        delete_action.triggered.connect(self.delete_shipment)
        menu.addAction(delete_action)
        
        menu.exec_(self.tree.viewport().mapToGlobal(position))
    
    def restore_group(self, group_id):
        """Восстановить всю группу из архива"""
        reply = QMessageBox.question(self, "Подтверждение",
                                  "Вы уверены, что хотите восстановить всю группу из архива?",
                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            session = self.Session()
            try:
                # Найти групповую поставку
                group_shipment = session.query(GroupShipment).get(group_id)
                if group_shipment:
                    # Снять с архивации саму группу
                    group_shipment.archived = False
                    group_shipment.archived_date = None
                    
                    # Снять с архивации все подпоставки этой группы
                    for sub_shipment in group_shipment.sub_shipments:
                        sub_shipment.archived = False
                        sub_shipment.archived_date = None
                    
                    session.commit()
                    self.load_data()
                    QMessageBox.information(self, "Успех", "Групповая поставка восстановлена из архива")
                else:
                    QMessageBox.warning(self, "Ошибка", "Групповая поставка не найдена")
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Ошибка", f"Ошибка при восстановлении группы: {e}")
            finally:
                session.close()
    
    def restore_shipment(self):
        # Получаем выбранные элементы
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Ошибка", "Выберите поставку для восстановления")
            return
        
        session = self.Session()
        restored_count = 0
        
        try:
            for item in selected_items:
                item_type = item.data(0, Qt.ItemDataRole.UserRole)
                if item_type == "shipment":
                    shipment_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
                    shipment = session.query(Shipment).get(shipment_id)
                    if shipment:
                        shipment.archived = False
                        shipment.archived_date = None
                        restored_count += 1
            
            session.commit()
            self.load_data()
            QMessageBox.information(self, "Успех", f"{restored_count} поставок восстановлено из архива")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Ошибка", f"Ошибка при восстановлении поставок: {e}")
        finally:
            session.close()
    
    def delete_shipment(self):
        # Получаем выбранные элементы
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Ошибка", "Выберите поставку для удаления")
            return
        
        reply = QMessageBox.question(self, "Подтверждение",
                                  "Вы уверены, что хотите полностью удалить выбранные поставки из архива?",
                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            session = self.Session()
            deleted_count = 0
            
            try:
                for item in selected_items:
                    item_type = item.data(0, Qt.ItemDataRole.UserRole)
                    item_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
                    
                    if item_type == "shipment":
                        shipment = session.query(Shipment).get(item_id)
                        if shipment:
                            session.delete(shipment)
                            deleted_count += 1
                    elif item_type == "group":
                        group_shipment = session.query(GroupShipment).get(item_id)
                        if group_shipment:
                            session.delete(group_shipment)
                            deleted_count += 1
                
                session.commit()
                self.load_data()
                QMessageBox.information(self, "Успех", f"{deleted_count} элементов удалено из архива")
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Ошибка", f"Ошибка при удалении: {e}")
            finally:
                session.close()
    
    def view_boxes(self):
        # Получаем выбранные элементы
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Ошибка", "Выберите поставку для просмотра")
            return
        
        # Просматриваем только первую выбранную поставку
        item = selected_items[0]
        item_type = item.data(0, Qt.ItemDataRole.UserRole)
        if item_type != "shipment":
            QMessageBox.warning(self, "Ошибка", "Можно просматривать коробки только у обычных поставок")
            return
        
        shipment_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
        
        from boxes_window import BoxesWindow
        self.boxes_window = BoxesWindow(shipment_id)
        self.boxes_window.show()