# custom_table_widget.py
from PyQt6.QtWidgets import QTableWidget, QAbstractItemView, QStyle, QStyleOptionViewItem
from PyQt6.QtCore import Qt, QTimer, QObject, QEvent
from PyQt6.QtGui import QFocusEvent


class CustomTableWidget(QTableWidget):
    """
    Custom table widget that ensures text fits during editing by temporarily 
    adjusting column width when a cell enters edit mode.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_column_widths = {}
        self.original_row_height = None
        self.editing_item = None
        self.editing_column = -1
        self.editing_row = None
        self.active_editors = set()  # Track active editors
        self.installEventFilter(self)  # Install event filter to handle editor destruction
        self._original_style = self.styleSheet() # Store original style
        self._original_font = self.font() # Store original font
        
    def edit(self, index, trigger, event):
        """
        Override the edit method to adjust column width and row height before editing
        """
        if index.isValid():
            # Store the current column width
            column = index.column()
            row = index.row()

            # Temporarily increase the column width to accommodate longer text during editing
            # We'll calculate the needed width based on the current text and font
            item = self.item(index.row(), index.column())
            if item:
                self.editing_item = item  # Сохраняем ссылку на редактируемый элемент
                self.editing_column = column
                self.editing_row = row
                self.original_column_widths[column] = self.columnWidth(column)
                self.original_row_height = self.rowHeight(row)

                # Only save the original style if it hasn't been saved yet in this instance
                if not hasattr(self, '_original_style_saved') or not self._original_style_saved:
                    self._original_style = self.styleSheet()
                    self._original_style_saved = True

                # Don't apply any custom styling that might interfere with the original appearance
                # Just ensure the original style is maintained
                pass

                # Calculate text width to ensure it fits properly during editing
                text = item.text()
                font_metrics = self.fontMetrics()
                text_width = font_metrics.horizontalAdvance(text + "00")  # Add some padding
                text_height = max(1, font_metrics.height() // 2)  # Use half of the text height for compact view
                min_width = max(self.columnWidth(column), text_width, 150)  # Minimum 150 pixels for editing
                min_height = max(self.rowHeight(row), text_height)  # Use only text height without extra padding

                # Не расширяем столбец, если он не редактируемый (флаги не включают ItemIsEditable)
                if not (item.flags() & Qt.ItemFlag.ItemIsEditable):
                    # Просто сохраняем оригинальную ширину, не изменяем её
                    pass
                else:
                    self.setColumnWidth(column, min_width)
                    self.setRowHeight(row, min_height)
            else:
                # If item is not found, set default values
                self.editing_item = None
                self.editing_column = column
                self.editing_row = row
                self.original_column_widths[column] = self.columnWidth(column)
                self.original_row_height = self.rowHeight(row)

            # Call the parent edit method
            result = super().edit(index, trigger, event)

            # Track this editor if it was successfully created
            current_editor = self.indexWidget(index)
            if current_editor:
                self.active_editors.add(current_editor)

            return result

        return super().edit(index, trigger, event)
    
    def commitData(self, editor):
        """
        Override commitData to restore original column width and row height after editing
        """
        # Check if this editor was created by this table
        if editor in self.active_editors:
            super().commitData(editor)
            if hasattr(self, 'editing_column') and self.editing_column >= 0:
                # Restore original column width after editing is complete
                if self.editing_column in self.original_column_widths:
                    self.setColumnWidth(self.editing_column, self.original_column_widths[self.editing_column])
                # Restore original row height if we have the original value
                if hasattr(self, 'original_row_height') and hasattr(self, 'editing_row') and self.editing_row is not None:
                    # Уменьшаем высоту строки в два раза при восстановлении
                    self.setRowHeight(self.editing_row, max(1, self.original_row_height // 2))
                self.editing_column = -1
                self.editing_row = None
                self.editing_item = None
            
            # Remove from active editors and restore the original style after editing is complete
            self.active_editors.discard(editor)
            # Only restore the original style if we have it stored
            if hasattr(self, '_original_style'):
                self.setStyleSheet(self._original_style)
        else:
            super().commitData(editor)
    
    def closeEditor(self, editor, hint):
        """
        Override closeEditor to restore original column width and row height when editor closes
        """
        # Check if this editor was created by this table
        if editor in self.active_editors:
            super().closeEditor(editor, hint)
            if hasattr(self, 'editing_column') and self.editing_column >= 0:
                # Restore original column width when editor closes
                if self.editing_column in self.original_column_widths:
                    self.setColumnWidth(self.editing_column, self.original_column_widths[self.editing_column])
                # Restore original row height if we have the original value
                if hasattr(self, 'original_row_height') and hasattr(self, 'editing_row') and self.editing_row is not None:
                    # Уменьшаем высоту строки в два раза при восстановлении
                    self.setRowHeight(self.editing_row, max(1, self.original_row_height // 2))
                self.editing_column = -1
                self.editing_row = None
                self.editing_item = None
            
            # Remove from active editors and restore the original style after editing is complete
            self.active_editors.discard(editor)
            # Only restore the original style if we have it stored
            if hasattr(self, '_original_style'):
                self.setStyleSheet(self._original_style)
        else:
            super().closeEditor(editor, hint)
    
    def eventFilter(self, obj, event):
        """
        Event filter to track when editors are destroyed
        """
        if event.type() == QEvent.Type.ChildRemoved:
            # When an editor widget is destroyed, remove it from active editors
            self.active_editors.discard(obj)
        return super().eventFilter(obj, event)
    
    def itemSelectionChanged(self):
        """
        Override itemSelectionChanged to ensure font consistency when selection changes
        """
        super().itemSelectionChanged()
        # Restore font when selection changes to ensure consistency
        if hasattr(self, '_original_font'):
            self.setFont(self._original_font)
    