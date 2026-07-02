"""Entry point приложения YT Downloader.

Тонкий слой: настройка логирования → QApplication → DI → MCP thread → MainWindow → exec.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_logs_dir() -> Path:
    """Вычисляет путь для логов — %APPDATA%/YTDownloader/logs."""
    app_data = Path(os.getenv("APPDATA", Path.home())) / "YTDownloader"
    logs_dir = app_data / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _install_exception_hooks() -> None:
    """Устанавливает глобальные обработчики необработанных исключений."""

    def _excepthook(exc_type, exc_value, exc_tb):  # type: ignore[no-untyped-def]
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical("unhandled.exception", exc_info=(exc_type, exc_value, exc_tb))
        # Показываем диалог если Qt доступен
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance()
            if app:
                QMessageBox.critical(
                    None,
                    "Критическая ошибка",
                    f"Произошла непредвиденная ошибка:\n{exc_type.__name__}: {exc_value}\n\n"
                    f"Подробности в логах.",
                )
        except Exception:
            pass

    sys.excepthook = _excepthook


def main() -> None:
    """Запускает приложение."""
    from src.core.logging_setup import setup_logging

    logs_dir = _get_logs_dir()
    setup_logging(log_dir=logs_dir)

    _install_exception_hooks()

    # Импорты после setup_logging, чтобы logging работал
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from main import initialize_app
    from src.ui.main_window import MainWindow
    from src.ui.utils.theme import Theme, apply_theme

    # Высокое DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("YT Downloader")
    app.setOrganizationName("YTDownloader")

    # DI — создание всех сервисов
    services = initialize_app()

    # MCP сервер — запуск в daemon-потоке (не блокирует Qt event loop)
    import threading

    mcp_port = services["settings"].mcp_port
    mcp_thread = threading.Thread(
        target=_start_mcp_safe,
        kwargs={"services": services, "host": "127.0.0.1", "port": mcp_port},
        daemon=True,  # завершится вместе с процессом
        name="mcp-server",
    )
    mcp_thread.start()

    # Применить тему ДО показа окна
    apply_theme(Theme(services["settings"].theme))

    # Главное окно
    window = MainWindow(services)
    window.show()

    sys.exit(app.exec())


def _start_mcp_safe(services: dict, host: str, port: int) -> None:
    """Запускает MCP сервер с обработкой ошибок порта."""
    from src.infrastructure.mcp.server import run_server

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            run_server(services=services, host=host, port=port + attempt)
            return
        except OSError:
            logger.warning(
                "mcp.server.port_busy port=%d attempt=%d",
                port + attempt,
                attempt + 1,
            )
            if attempt == max_attempts - 1:
                logger.error("mcp.server.failed_all_ports", exc_info=True)
        except Exception:
            logger.error("mcp.server.unexpected_error", exc_info=True)
            return


if __name__ == "__main__":
    main()
