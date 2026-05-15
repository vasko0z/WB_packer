# editing_delegate.py
from PyQt6.QtWidgets import QStyledItemDelegate, QSpinBox, QLineEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QValidator


class QuantityEditDelegate(QStyledItemDelegate):
    """
    Custom delegate for editing quantity values that ensures proper text visibility during editing
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def createEditor(self, parent, option, index):
        """
        Create an editor for the given index
        """
        # Create a QLineEdit editor for quantity values
        editor = QLineEdit(parent)
        # Set validator to only allow integers
        editor.setValidator(QuantityValidator(parent))
        return editor
    
    def setEditorData(self, editor, index):
        """
        Set the data to be displayed in the editor
        """
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        editor.setText(str(value) if value is not None else "")
    
    def setModelData(self, editor, model, index):
        """
        Save the data from the editor to the model
        """
        text = editor.text()
        try:
            value = int(text)
            if value < 0:
                value = 0  # Ensure non-negative values
        except ValueError:
            value = 0 # Default to 0 if conversion fails
        
        model.setData(index, str(value), Qt.ItemDataRole.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        """
        Update the editor's geometry to ensure it fits the content
        """
        # Calculate the required width and height based on the font and text content
        text = editor.text()
        font_metrics = editor.fontMetrics()
        text_width = font_metrics.horizontalAdvance(text + "00")  # Add some padding
        text_height = font_metrics.height()
        min_width = max(option.rect.width(), text_width, 80)  # Ensure minimum width of 80 pixels
        min_height = text_height  # Use only font height without additional padding
        
        new_option = option
        new_option.rect.setWidth(min_width)
        new_option.rect.setHeight(min_height)
        super().updateEditorGeometry(editor, new_option, index)


class QuantityValidator(QValidator):
    """
    Validator for quantity input to ensure only valid integers are entered
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def validate(self, input_str, pos):
        """
        Validate the input string
        """
        if input_str == "":
            return QValidator.State.Acceptable, input_str, pos
        
        try:
            value = int(input_str)
            if value < 0:
                return QValidator.State.Invalid, input_str, pos
            return QValidator.State.Acceptable, input_str, pos
        except ValueError:
            # Check if it's a partial number (e.g. "-")
            if input_str == "-" or input_str == "":
                return QValidator.State.Intermediate, input_str, pos
            else:
                return QValidator.State.Invalid, input_str, pos