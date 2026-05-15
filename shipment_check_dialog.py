# shipment_check_dialog.py
import pandas as pd
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QFileDialog, QLabel, QHeaderView, QMessageBox,
    QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
import json
import os
from pathlib import Path

# Import the utils module for sound functionality
# We'll handle the import gracefully to avoid crashes
try:
    from utils import play_sound
    UTILS_AVAILABLE = True
except ImportError:
    # Create a mock play_sound function if import fails
    def play_sound(sound_name, tone_sound=False):
        pass  # Do nothing if utils module is not available
    UTILS_AVAILABLE = False


class ShipmentCheckDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Проверка поставки")
        self.resize(1000, 600)

        self.parent = parent
        self.excel_data = {}
        self.scanned_items = {}
        self.excel_items = {}
        self.original_file_path = None # Store the original file path
        self.ok_sound = "ok.wav"  # Default sound file names
        self.error_sound = "error.wav"
        self.dialog_state = {}  # Store dialog state for persistence
        self.state_file = Path("shipment_check_state.json")  # File to store state between sessions
        self.is_scanning = False  # Флаг защиты от повторного срабатывания сканера
        self.is_initialized = False  # Flag to track if dialog is initialized
        
        # Get sound settings from parent if available
        if parent and hasattr(parent, 'ok_sound'):
            self.ok_sound = parent.ok_sound
        if parent and hasattr(parent, 'error_sound'):
            self.error_sound = parent.error_sound
        
        self.init_ui()
        self.setup_shortcuts()
        self.load_persistent_state()  # Load saved state when initializing
        self.is_initialized = True
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Top section with buttons
        top_layout = QHBoxLayout()
        
        self.load_excel_btn = QPushButton("Загрузить Excel файл")
        self.load_excel_btn.clicked.connect(self.load_excel_file)
        
        self.reset_btn = QPushButton("Сброс")
        self.reset_btn.clicked.connect(self.reset_check)
        self.reset_btn.setEnabled(False)
        
        self.export_btn = QPushButton("Экспорт отчета")
        self.export_btn.clicked.connect(self.export_report)
        self.export_btn.setEnabled(False) # Enable only after check is completed
        
        top_layout.addWidget(self.load_excel_btn)
        top_layout.addWidget(self.reset_btn)
        top_layout.addWidget(self.export_btn)
        top_layout.addStretch()
        
        # Label to show status
        self.status_label = QLabel("Ожидание загрузки Excel файла")
        self.status_label.setStyleSheet("font-weight: bold; color: #666666;")
        
        # Table to show shipment data
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Штрихкод", "Артикул", "Кол-во по Excel",
            "Кол-во сосканировано", "Разница", "Статус"
        ])
        
        # Set header properties
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        
        # Enable editing for the "Кол-во сосканировано" column (index 3)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.table.cellChanged.connect(self.on_table_cell_changed)
        
        # Input for scanning
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText("Отсканируйте штрихкод и нажмите Enter")
        self.scan_input.returnPressed.connect(self.handle_scan)
        self.scan_input.setEnabled(False)
        
        # Add widgets to layout
        layout.addLayout(top_layout)
        layout.addWidget(self.status_label)
        layout.addWidget(self.table)
        layout.addWidget(self.scan_input)
        
        self.setLayout(layout)
        
    def setup_shortcuts(self):
        # Add shortcuts
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self.accept)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.reject)
        
    def load_excel_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите Excel файл с поставкой",
            "",
            "Excel Files (*.xlsx *.xls)"
        )
        
        if not file_path:
            return
            
        try:
            # Store the original file path for export functionality
            self.original_file_path = file_path
            
            # Load Excel file - assuming standard format with barcode, sku, quantity
            # First, read without specifying dtypes to identify columns
            df_temp = pd.read_excel(file_path)
            
            # Try to identify columns by name (common variations)
            barcode_col = None
            for col in df_temp.columns:
                col_name = str(col).lower()
                if 'штрихкод' in col_name or 'barcode' in col_name or 'бак' in col_name:
                    barcode_col = col
                    break
            
            # If we can't identify the barcode column by name, use the first column
            if barcode_col is None:
                barcode_col = df_temp.columns[0]
            
            # Now read the file again with the barcode column specified as string to preserve leading zeros
            dtype_dict = {barcode_col: str}
            df = pd.read_excel(file_path, dtype=dtype_dict)
            
            # Try to identify columns by name (common variations)
            barcode_col = None
            sku_col = None
            qty_col = None
            
            for col in df.columns:
                col_name = str(col).lower()
                if 'штрихкод' in col_name or 'barcode' in col_name or 'бак' in col_name:
                    barcode_col = col
                elif 'артикул' in col_name or 'sku' in col_name or 'article' in col_name:
                    sku_col = col
                elif 'кол' in col_name or 'qty' in col_name or 'quantity' in col_name or 'шт' in col_name:
                    qty_col = col
            
            # If we can't identify columns by name, use common positions
            if barcode_col is None:
                barcode_col = df.columns[0]  # First column
            if sku_col is None:
                sku_col = df.columns[1] if len(df.columns) > 1 else barcode_col  # Second column or same as barcode
            if qty_col is None:
                qty_col = df.columns[2] if len(df.columns) > 2 else df.columns[1] if len(df.columns) > 1 else barcode_col  # Third or second or first column
                
            # Process the data
            self.excel_items = {}
            for _, row in df.iterrows():
                barcode = str(row[barcode_col]).strip()
                sku = str(row[sku_col]).strip() if sku_col in row else "?"
                qty = int(row[qty_col]) if pd.notna(row[qty_col]) else 0
                
                if barcode:
                    self.excel_items[barcode] = {
                        'sku': sku,
                        'expected_qty': qty,
                        'scanned_qty': 0
                    }
            
            self.update_table()
            self.status_label.setText(f"Загружено {len(self.excel_items)} позиций из Excel файла")
            self.scan_input.setEnabled(True)
            self.reset_btn.setEnabled(True)
            self.load_excel_btn.setEnabled(False)  # Disable after loading
            self.export_btn.setEnabled(True)  # Enable export after loading
            self.save_dialog_state()  # Save state after loading Excel file
            
            QMessageBox.information(self, "Успех", f"Загружено {len(self.excel_items)} позиций из Excel файла")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить Excel файл:\n{str(e)}")
            
    def handle_scan(self):
        # Защита от повторного срабатывания сканера
        if self.is_scanning:
            return
        self.is_scanning = True
        
        try:
            if not self.scan_input.text().strip():
                return

            barcode = self.scan_input.text().strip()
            self.scan_input.clear()

            # Check if this barcode exists in the Excel file
            if barcode in self.excel_items:
                # Valid barcode - increment scanned quantity
                self.excel_items[barcode]['scanned_qty'] += 1
                self.update_table()

                # Find the row for this barcode and update its status
                for row in range(self.table.rowCount()):
                    if self.table.item(row, 0).text() == barcode:
                        diff = self.excel_items[barcode]['scanned_qty'] - self.excel_items[barcode]['expected_qty']
                        status = self.get_status_text(diff)
                        self.table.item(row, 5).setText(status)
                        break

                # Play success sound if available
                if UTILS_AVAILABLE:
                    play_sound(self.ok_sound, False)  # tone_sound=False для проверки
                self.save_dialog_state()  # Save state after successful scan
            else:
                # Barcode not in Excel - this is an extra item
                if barcode not in self.scanned_items:
                    # Add to scanned items as an extra
                    self.scanned_items[barcode] = {
                        'sku': 'НЕИЗВЕСТНО',
                        'expected_qty': 0,
                        'scanned_qty': 1
                    }
                    self.add_extra_item_to_table(barcode)
                else:
                    # Increment count for this extra item
                    self.scanned_items[barcode]['scanned_qty'] += 1
                    self.update_table()

                QMessageBox.warning(self, "Внимание", f"Штрихкод {barcode} не найден в Excel файле (излишек)")
                # Play error sound if available
                if UTILS_AVAILABLE:
                    play_sound(self.error_sound, False)  # tone_sound=False для проверки
                self.save_dialog_state()  # Save state after handling extra item

            # Update status
            total_expected = sum(item['expected_qty'] for item in self.excel_items.values())
            total_scanned = sum(item['scanned_qty'] for item in self.excel_items.values())
            total_extra = sum(item['scanned_qty'] for item in self.scanned_items.values())

            self.status_label.setText(
                f"Скан: ожидается {total_expected}, сосканировано {total_scanned}, излишки {total_extra}"
            )
        finally:
            # Сбрасываем флаг после небольшой задержки
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(200, self._reset_scanning_flag)
    
    def _reset_scanning_flag(self):
        """Сброс флага сканирования после задержки"""
        self.is_scanning = False
    
    def get_status_text(self, diff):
        if diff == 0:
            return "OK"
        elif diff > 0:
            return f"Излишек (+{diff})"
        else:
            return f"Недостача ({diff})"
    
    def update_table(self):
        # Отключаем сигнал cellChanged на время программного обновления
        self.table.blockSignals(True)
        try:
            # Calculate total rows needed (items from Excel + extra scanned items)
            total_items = len(self.excel_items) + len(self.scanned_items)
            self.table.setRowCount(total_items)

            row = 0
            # Add items from Excel file
            for barcode, item_data in self.excel_items.items():
                self.set_table_row(row, barcode, item_data, is_extra=False)
                row += 1

            # Add extra scanned items
            for barcode, item_data in self.scanned_items.items():
                self.set_table_row(row, barcode, item_data, is_extra=True)
                row += 1
        finally:
            # Включаем сигнал обратно
            self.table.blockSignals(False)
    
    def set_table_row(self, row, barcode, item_data, is_extra=False):
        # Barcode
        barcode_item = QTableWidgetItem(barcode)
        barcode_item.setFlags(barcode_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Make not editable
        if is_extra:
            barcode_item.setBackground(Qt.GlobalColor.red)
            barcode_item.setForeground(Qt.GlobalColor.white)
        self.table.setItem(row, 0, barcode_item)
        
        # SKU
        sku_item = QTableWidgetItem(item_data['sku'])
        sku_item.setFlags(sku_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Make not editable
        if is_extra:
            sku_item.setBackground(Qt.GlobalColor.red)
            sku_item.setForeground(Qt.GlobalColor.white)
        self.table.setItem(row, 1, sku_item)
        
        # Expected quantity
        expected_item = QTableWidgetItem(str(item_data['expected_qty']))
        expected_item.setFlags(expected_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Make not editable
        if is_extra:
            expected_item.setText("0")
            expected_item.setBackground(Qt.GlobalColor.red)
            expected_item.setForeground(Qt.GlobalColor.white)
        self.table.setItem(row, 2, expected_item)
        
        # Scanned quantity - make this editable
        scanned_item = QTableWidgetItem(str(item_data['scanned_qty']))
        if is_extra:
            scanned_item.setBackground(Qt.GlobalColor.red)
            scanned_item.setForeground(Qt.GlobalColor.white)
        self.table.setItem(row, 3, scanned_item)
        
        # Difference
        diff = item_data['scanned_qty'] - item_data['expected_qty']
        diff_item = QTableWidgetItem(str(diff))
        diff_item.setFlags(diff_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Make not editable
        if diff < 0:
            # Shortage - red
            diff_item.setBackground(Qt.GlobalColor.red)
            diff_item.setForeground(Qt.GlobalColor.white)
        elif diff > 0:
            # Excess - yellow
            diff_item.setBackground(Qt.GlobalColor.yellow)
        else:
            # Exact match - green
            diff_item.setBackground(Qt.GlobalColor.green)
            diff_item.setForeground(Qt.GlobalColor.white)
        self.table.setItem(row, 4, diff_item)
        
        # Status
        status_text = self.get_status_text(diff)
        status_item = QTableWidgetItem(status_text)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Make not editable
        if diff < 0:
            # Shortage - red
            status_item.setBackground(Qt.GlobalColor.red)
            status_item.setForeground(Qt.GlobalColor.white)
        elif diff > 0:
            # Excess - yellow
            status_item.setBackground(Qt.GlobalColor.yellow)
        else:
            # Exact match - green
            status_item.setBackground(Qt.GlobalColor.green)
            status_item.setForeground(Qt.GlobalColor.white)
        self.table.setItem(row, 5, status_item)
    
    def add_extra_item_to_table(self, barcode):
        # Add a new row for the extra item
        current_rows = self.table.rowCount()
        self.table.setRowCount(current_rows + 1)
        row = current_rows
        
        item_data = self.scanned_items[barcode]
        self.set_table_row(row, barcode, item_data, is_extra=True)
    
    def reset_check(self):
        """Reset the current check session"""
        self.excel_data = {}
        self.scanned_items = {}
        self.excel_items = {}
        self.original_file_path = None  # Reset file path
        self.table.setRowCount(0)
        self.status_label.setText("Ожидание загрузки Excel файла")
        self.scan_input.clear()
        self.scan_input.setEnabled(False)
        self.load_excel_btn.setEnabled(True)
        self.reset_btn.setEnabled(False)
        self.export_btn.setEnabled(False)  # Disable export after reset
        self.dialog_state = {}  # Clear dialog state
        # Remove the persistent state file when resetting
        if self.state_file.exists():
            try:
                self.state_file.unlink()  # Delete the state file
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error removing state file: {e}")
        
    def accept(self):
        """Override accept to show summary before closing"""
        if len(self.excel_items) > 0 or len(self.scanned_items) > 0:
            # Calculate summary
            shortages = 0
            excesses = 0
            extras = len(self.scanned_items)
            
            for item_data in self.excel_items.values():
                diff = item_data['scanned_qty'] - item_data['expected_qty']
                if diff < 0:
                    shortages += 1
                elif diff > 0:
                    excesses += 1
            
            summary = f"Проверка завершена.\n"
            summary += f"Недостач: {shortages}\n"
            summary += f"Излишков (в Excel): {excesses}\n"
            summary += f"Лишних позиций (не в Excel): {extras}"
            
            QMessageBox.information(self, "Результат проверки", summary)
            self.export_btn.setEnabled(True)  # Enable export button after check is completed
            self.save_dialog_state()  # Save state after check completion
        
    def reject(self):
        """Override reject to save state before closing"""
        self.save_dialog_state()
        super().reject()
    
    def closeEvent(self, event):
        """Override closeEvent to save dialog state"""
        self.save_dialog_state()
        super().closeEvent(event)
    
    def export_report(self):
        """Export the check results as an Excel file"""
        if not hasattr(self, 'original_file_path') or not self.original_file_path:
            # If we don't have the original file path, ask the user to provide it
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить отчет проверки",
                "Отчет_проверки.xlsx",
                "Excel Files (*.xlsx *.xls)"
            )
            if not file_path:
                return
        else:
            # Create the output file name based on the original file
            import os
            name, ext = os.path.splitext(self.original_file_path)
            file_path = f"{name}_проверено{ext}"
        
        try:
            # Prepare data for export
            data = []
            
            # Add items from Excel file
            for barcode, item_data in self.excel_items.items():
                diff = item_data['scanned_qty'] - item_data['expected_qty']
                data.append({
                    'Штрихкод': barcode,
                    'Артикул': item_data['sku'],
                    'Кол-во по Excel': item_data['expected_qty'],
                    'Кол-во сосканировано': item_data['scanned_qty'],
                    'Разница': diff,
                    'Статус': self.get_status_text(diff)
                })
            
            # Add extra scanned items
            for barcode, item_data in self.scanned_items.items():
                diff = item_data['scanned_qty'] - item_data['expected_qty']
                data.append({
                    'Штрихкод': barcode,
                    'Артикул': item_data['sku'],
                    'Кол-во по Excel': item_data['expected_qty'],
                    'Кол-во сосканировано': item_data['scanned_qty'],
                    'Разница': diff,
                    'Статус': self.get_status_text(diff)
                })
            
            # Create DataFrame and export to Excel
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            
            QMessageBox.information(self, "Экспорт", f"Отчет успешно экспортирован в:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать отчет:\n{str(e)}")
    
    def on_table_cell_changed(self, row, column):
        """Handle changes to the scanned quantity column"""
        if column == 3: # Scanned quantity column
            try:
                new_qty = int(self.table.item(row, column).text())
                barcode = self.table.item(row, 0).text()
                
                # Update the appropriate item based on whether it's from Excel or extra
                is_extra = False
                if barcode in self.excel_items:
                    self.excel_items[barcode]['scanned_qty'] = new_qty
                elif barcode in self.scanned_items:
                    self.scanned_items[barcode]['scanned_qty'] = new_qty
                    is_extra = True
                else:
                    # If barcode is not found, skip update
                    return
                
                # Update difference and status columns
                if is_extra:
                    item_data = self.scanned_items[barcode]
                else:
                    item_data = self.excel_items[barcode]
                
                diff = item_data['scanned_qty'] - item_data['expected_qty']
                diff_item = self.table.item(row, 4)
                if diff_item:  # Check if the item exists before updating
                    diff_item.setText(str(diff))
                    
                    # Update background colors for difference cell
                    if diff < 0:
                        # Shortage - red
                        diff_item.setBackground(Qt.GlobalColor.red)
                        diff_item.setForeground(Qt.GlobalColor.white)
                    elif diff > 0:
                        # Excess - yellow
                        diff_item.setBackground(Qt.GlobalColor.yellow)
                    else:
                        # Exact match - green
                        diff_item.setBackground(Qt.GlobalColor.green)
                        diff_item.setForeground(Qt.GlobalColor.white)
                
                # Update status cell
                status_item = self.table.item(row, 5)
                if status_item:  # Check if the item exists before updating
                    status_text = self.get_status_text(diff)
                    status_item.setText(status_text)
                    
                    # Update background colors for status cell
                    if diff < 0:
                        # Shortage - red
                        status_item.setBackground(Qt.GlobalColor.red)
                        status_item.setForeground(Qt.GlobalColor.white)
                    elif diff > 0:
                        # Excess - yellow
                        status_item.setBackground(Qt.GlobalColor.yellow)
                    else:
                        # Exact match - green
                        status_item.setBackground(Qt.GlobalColor.green)
                        status_item.setForeground(Qt.GlobalColor.white)
                
                # Update status label
                total_expected = sum(item['expected_qty'] for item in self.excel_items.values())
                total_scanned = sum(item['scanned_qty'] for item in self.excel_items.values())
                total_extra = sum(item['scanned_qty'] for item in self.scanned_items.values())
                
                self.status_label.setText(
                    f"Скан: ожидается {total_expected}, сосканировано {total_scanned}, излишки {total_extra}"
                )
                
                # Play success sound when quantity is updated
                if UTILS_AVAILABLE:
                    play_sound(self.ok_sound, False)  # tone_sound=False для проверки
                self.save_dialog_state()  # Save state after updating quantity

            except ValueError:
                # If the input is not a valid integer, revert to the previous value
                if barcode in self.excel_items:
                    prev_qty = self.excel_items[barcode]['scanned_qty']
                elif barcode in self.scanned_items:
                    prev_qty = self.scanned_items[barcode]['scanned_qty']
                else:
                    prev_qty = 0
                table_item = self.table.item(row, column)
                if table_item:  # Check if the item exists before updating
                    table_item.setText(str(prev_qty))
                QMessageBox.warning(self, "Ошибка", "Количество должно быть целым числом")
                # Play error sound when quantity is updated
                if UTILS_AVAILABLE:
                    play_sound(self.error_sound, False)  # tone_sound=False для проверки
                self.save_dialog_state()  # Save state after handling error
    
    def save_persistent_state(self):
        """Save the current dialog state to persistent storage"""
        state_data = {
            'excel_items': self.excel_items,
            'scanned_items': self.scanned_items,
            'original_file_path': self.original_file_path
        }
        
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving dialog state: {e}")
    
    def load_persistent_state(self):
        """Load the saved dialog state from persistent storage"""
        if not self.state_file.exists():
            return  # No saved state to load
            
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
                
            # Restore items
            self.excel_items = state_data.get('excel_items', {})
            self.scanned_items = state_data.get('scanned_items', {})
            self.original_file_path = state_data.get('original_file_path')
            
            # Update the UI based on the loaded state
            self.update_table()
            
            # Update UI elements
            if self.excel_items or self.scanned_items:
                self.scan_input.setEnabled(True)
                self.reset_btn.setEnabled(True)
                self.export_btn.setEnabled(True)
                self.load_excel_btn.setEnabled(False)
                total_items = len(self.excel_items) + len(self.scanned_items)
                self.status_label.setText(f"Восстановлено {total_items} позиций из предыдущей сессии")
            else:
                self.scan_input.setEnabled(False)
                self.reset_btn.setEnabled(False)
                self.export_btn.setEnabled(False)
                self.load_excel_btn.setEnabled(True)
                self.status_label.setText("Ожидание загрузки Excel файла")
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error loading dialog state: {e}")
            # If there's an error loading the state, reset to clean state
            self.reset_check()
    
    def save_dialog_state(self):
        """Save the current dialog state (alias for persistent save)"""
        self.save_persistent_state()
    
    def load_dialog_state(self):
        """Load the saved dialog state (alias for persistent load)"""
        self.load_persistent_state()
    
    def restore_dialog_state(self):
        """Restore the dialog state from self.dialog_state - kept for compatibility"""
        if not self.dialog_state:
            return
            
        # Restore items
        self.excel_items = {k: v.copy() for k, v in self.dialog_state.get('excel_items', {}).items()}
        self.scanned_items = {k: v.copy() for k, v in self.dialog_state.get('scanned_items', {}).items()}
        self.original_file_path = self.dialog_state.get('original_file_path')
        table_row_count = self.dialog_state.get('table_row_count', 0)
        
        # Restore table state
        self.table.setRowCount(table_row_count)
        self.update_table()
        
        # Update UI elements
        if self.excel_items or self.scanned_items:
            self.scan_input.setEnabled(True)
            self.reset_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self.load_excel_btn.setEnabled(False)
            total_items = len(self.excel_items) + len(self.scanned_items)
            self.status_label.setText(f"Восстановлено {total_items} позиций")
        else:
            self.scan_input.setEnabled(False)
            self.reset_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
            self.load_excel_btn.setEnabled(True)
            self.status_label.setText("Ожидание загрузки Excel файла")