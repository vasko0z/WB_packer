# splash_screen.py
"""
Simple splash screen for application startup
"""
import logging
import sys
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtWidgets import QSplashScreen, QLabel, QWidget, QVBoxLayout, QProgressBar

logger = logging.getLogger(__name__)


def get_version_string():
    """Получить строку версии"""
    try:
        from version import get_version_string
        return get_version_string()
    except Exception:
        return "1.0.0.0"


class SplashScreen(QSplashScreen):
    def __init__(self):
        try:
            # Create a simple pixmap for splash
            pixmap = QPixmap(400, 320)
            pixmap.fill(Qt.GlobalColor.white)

            super().__init__(pixmap, Qt.WindowType.SplashScreen)
            self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)

            # Получаем версию
            version = get_version_string()

            # Add loading text
            self.loading_label = QLabel("Загрузка WB Packer...", self)
            self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.loading_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            self.loading_label.setStyleSheet("color: #333333; background-color: white;")
            self.loading_label.setGeometry(0, 120, 400, 40)

            # Progress bar
            self.progress_bar = QProgressBar(self)
            self.progress_bar.setGeometry(50, 170, 300, 20)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #ccc;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #f0f0f0;
                }
                QProgressBar::chunk {
                    border-radius: 3px;
                    background-color: #4CAF50;
                }
            """)
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(100)

            self.version_label = QLabel(f"Версия {version}", self)
            self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.version_label.setFont(QFont("Arial", 10))
            self.version_label.setStyleSheet("color: #666666; background-color: white;")
            self.version_label.setGeometry(0, 200, 400, 20)

            # Set a timeout to auto-close if something goes wrong
            self.auto_close_timer = QTimer()
            self.auto_close_timer.setSingleShot(True)
            self.auto_close_timer.timeout.connect(self._auto_close)
            self.auto_close_timer.setInterval(30000)  # 30 seconds timeout
            self.auto_close_timer.start()

            self.show()
        except Exception as e:
            logger.error("Error initializing SplashScreen: %s", e)
            raise

    def set_progress(self, value, message=None):
        """Update progress bar value and optional message"""
        self.progress_bar.setValue(value)
        if message:
            self.loading_label.setText(message)

    def _auto_close(self):
        """Auto-close splash screen if it hangs"""
        logger.warning("Splash screen timeout - auto closing")
        self.close()


def show_splash():
    """Show splash screen"""
    try:
        splash = SplashScreen()
        return splash
    except Exception as e:
        logger.error("Error creating splash screen: %s", e)
        return None


def hide_splash(splash):
    """Hide splash screen"""
    try:
        if splash:
            # Stop the auto-close timer
            if hasattr(splash, 'auto_close_timer'):
                splash.auto_close_timer.stop()
            splash.finish(None)
            splash.deleteLater()
    except Exception as e:
        logger.error("Error hiding splash screen: %s", e)