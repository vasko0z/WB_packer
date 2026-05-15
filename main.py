# main.py
import sys
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import logging_config
import config

logging_config.setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Запуск приложения WB Packer")
    
    config.init_db_settings()
    logger.info(f"Тип БД: {config.DATABASE_TYPE}, Путь SQLite: {config.get_sqlite_database_path()}")
    
    try:
        app = QApplication(sys.argv)
        
        from splash_screen import show_splash, hide_splash
        splash = show_splash()
        
        from themes import apply_theme
        from main_window import MainWindow

        if splash:
            splash.loading_label.setText("Применение темы...")

        apply_theme(app, config.DEFAULT_THEME)

        if splash:
            splash.loading_label.setText("Создание интерфейса...")

        window = MainWindow()

        if splash:
            splash.loading_label.setText("Завершение загрузки...")

        window.show()
        logger.info("Главное окно отображено")

        QTimer.singleShot(0, window.deferred_initialization)

        hide_splash(splash)
        
        sys.exit(app.exec())
    except KeyboardInterrupt:
        logger.info("Приложение прервано пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске приложения: {e}", exc_info=True)
        sys.exit(1)
