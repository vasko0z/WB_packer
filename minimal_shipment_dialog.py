# minimal_shipment_dialog.py
import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QLabel, QHeaderView, 
    QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt

class MinimalShipmentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Minimal Shipment Dialog")
        self.resize(800, 600)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Top section with buttons
        top_layout = QHBoxLayout()
        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self.load_data)
        top_layout.addWidget(self.load_btn)
        top_layout.addStretch()
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold; color: #666666;")
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Barcode", "SKU", "Expected", "Scanned"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        
        # Enable editing for the "Scanned" column
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.table.cellChanged.connect(self.on_cell_changed)
        
        # Scan input
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText("Scan barcode and press Enter")
        self.scan_input.returnPressed.connect(self.handle_scan)
        
        # Add widgets to layout
        layout.addLayout(top_layout)
        layout.addWidget(self.status_label)
        layout.addWidget(self.table)
        layout.addWidget(self.scan_input)
        
        self.setLayout(layout)
        
    def load_data(self):
        """Load sample data"""
        self.table.setRowCount(3)
        for i in range(3):
            self.table.setItem(i, 0, QTableWidgetItem(f"Barcode{i}"))
            self.table.setItem(i, 1, QTableWidgetItem(f"SKU{i}"))
            self.table.setItem(i, 2, QTableWidgetItem("10"))
            self.table.setItem(i, 3, QTableWidgetItem("0"))
        
        self.status_label.setText("Loaded 3 items")
        
    def handle_scan(self):
        """Handle barcode scanning"""
        barcode = self.scan_input.text().strip()
        self.scan_input.clear()
        
        if barcode:
            self.status_label.setText(f"Scanned: {barcode}")
            
    def on_cell_changed(self, row, column):
        """Handle cell changes"""
        if column == 3:  # Scanned quantity column
            try:
                value = int(self.table.item(row, column).text())
                self.status_label.setText(f"Updated row {row} to {value}")
            except ValueError:
                self.table.item(row, column).setText("0")
                QMessageBox.warning(self, "Error", "Please enter a valid number")

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dialog = MinimalShipmentDialog()
    dialog.exec()
    sys.exit(0)