# main.py
import sys
import logging
from PyQt6.QtWidgets import QApplication
import logging_config
import config

# Настройка логирования
logging_config.setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Запуск приложения WB Packer")
    
    # Инициализируем настройки базы данных из файла настроек
    config.init_db_settings()
    logger.info(f"Тип БД: {config.DATABASE_TYPE}, Путь SQLite: {config.get_sqlite_database_path()}")
    
    try:
        # Быстрая инициализация QApplication
        app = QApplication(sys.argv)
        
        # Показываем заставку
        from splash_screen import show_splash, hide_splash
        splash = show_splash()
        if splash:
            app.processEvents()  # Обрабатываем события для отображения заставки
        
        # Отложенный импорт тяжелых модулей
        from themes import apply_theme
        from main_window import MainWindow

        # База данных инициализируется в MainWindow.__init__
        # MVC контроллер инициализируется в deferred_initialization()

        # Обновляем заставку
        if splash:
            splash.loading_label.setText("Применение темы...")
            app.processEvents()

        # Применяем тему
        apply_theme(app, config.DEFAULT_THEME)

        # Обновляем заставку
        if splash:
            splash.loading_label.setText("Создание интерфейса...")
            app.processEvents()

        # Создаем главное окно
        window = MainWindow()

        # Обновляем заставку
        if splash:
            splash.loading_label.setText("Завершение загрузки...")
            app.processEvents()

        # Показываем окно
        window.show()
        logger.info("Главное окно отображено")

        # Принудительно вызываем отложенную инициализацию после показа окна
        # Это гарантирует, что данные загрузятся и дерево поставок отобразится
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1, window.deferred_initialization)

        # Скрываем заставку
        hide_splash(splash)
        
        sys.exit(app.exec())
    except KeyboardInterrupt:
        logger.info("Приложение прервано пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске приложения: {e}", exc_info=True)
        sys.exit(1)