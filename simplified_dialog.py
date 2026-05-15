# simplified_dialog.py
import sys
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QFileDialog, QLabel, QHeaderView, 
    QMessageBox, QLineEdit
)
from PyQt6.QtCore import Qt

class SimplifiedDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Simplified Dialog")
        self.resize(800, 600)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Top section with buttons
        top_layout = QHBoxLayout()
        self.load_btn = QPushButton("Load File")
        self.load_btn.clicked.connect(self.load_file)
        top_layout.addWidget(self.load_btn)
        top_layout.addStretch()
        
        # Status label
        self.status_label = QLabel("Waiting for file")
        self.status_label.setStyleSheet("font-weight: bold; color: #666666;")
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Barcode", "SKU", "Expected Qty", "Scanned Qty", "Difference", "Status"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        
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
        
    def load_file(self):
        self.status_label.setText("File loaded")
        self.table.setRowCount(3)
        for i in range(3):
            self.table.setItem(i, 0, QTableWidgetItem(f"Barcode{i}"))
            self.table.setItem(i, 1, QTableWidgetItem(f"SKU{i}"))
            self.table.setItem(i, 2, QTableWidgetItem("10"))
            self.table.setItem(i, 3, QTableWidgetItem("0"))
            self.table.setItem(i, 4, QTableWidgetItem("0"))
            self.table.setItem(i, 5, QTableWidgetItem("Pending"))
        
    def handle_scan(self):
        barcode = self.scan_input.text().strip()
        self.scan_input.clear()
        self.status_label.setText(f"Scanned: {barcode}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = SimplifiedDialog()
    dialog.exec()
    sys.exit(0)