"""Entry point приложения YT Downloader.

Тонкий слой: настройка логирования → QApplication → DI → MainWindow → exec.
"""

from __future__ import annotations

import sys


def main() -> None:
    """Запускает приложение."""
    from src.core.logging_setup import setup_logging

    setup_logging()

    # Импорты после setup_logging, чтобы logging работал
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    from main import initialize_app
    from src.ui.utils.theme import Theme, apply_theme
    from src.ui.main_window import MainWindow

    # Высокое DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("YT Downloader")
    app.setOrganizationName("YTDownloader")

    # DI — создание всех сервисов
    services = initialize_app()

    # Применить тему ДО показа окна
    apply_theme(Theme(services["settings"].theme))

    # Главное окно
    window = MainWindow(services)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
