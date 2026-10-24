"""Desktop composition: logging → one runtime → subscribed window → managed HTTP."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

    from src.infrastructure.mcp.server import HTTPServerHandle

from src.infrastructure.mcp.tools._utils import error_payload

logger = logging.getLogger(__name__)


def _get_logs_dir() -> Path:
    selected = os.environ.get("YTDL_LOG_DIR")
    if selected:
        return Path(selected).expanduser().resolve()
    data = os.environ.get("YTDL_DATA_DIR")
    return (
        Path(data) if data else Path(os.getenv("APPDATA") or Path.home()) / "YTDownloader"
    ) / "logs"


@contextmanager
def _logging() -> Iterator[None]:
    """Register each owned handler immediately; preserve borrowed handlers/levels."""
    root = logging.getLogger()
    previous, level = root.handlers[:], root.level
    owned: list[logging.Handler] = []
    names = ("yt_dlp", "fastmcp", "mcp", "uvicorn.access")
    levels = {name: logging.getLogger(name).level for name in names}
    root.handlers = []
    try:
        directory = _get_logs_dir()
        directory.mkdir(parents=True, exist_ok=True)
        owned.append(logging.StreamHandler(sys.stderr))
        root.addHandler(owned[-1])
        owned.append(
            RotatingFileHandler(
                directory / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
        )
        root.addHandler(owned[-1])
        errors = RotatingFileHandler(
            directory / "app.error.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        owned.append(errors)
        root.addHandler(errors)
        errors.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        for handler in owned:
            handler.setFormatter(formatter)
        root.setLevel(
            getattr(logging, os.environ.get("YTDL_LOG_LEVEL", "INFO").upper(), logging.INFO)
        )
        for name in names:
            logging.getLogger(name).setLevel(logging.WARNING)
        yield
    finally:
        failed = False
        for handler in owned:
            root.removeHandler(handler)
            try:
                handler.flush()
            except Exception:
                failed = True
            try:
                handler.close()
            except Exception:
                failed = True
        for handler in previous:
            root.addHandler(handler)
        root.setLevel(level)
        for name, old in levels.items():
            logging.getLogger(name).setLevel(old)
        if failed:
            from src.application.command_api import CommandError

            raise CommandError("Diagnostic cleanup was incomplete", code="INTERNAL_ERROR")


def _install_exception_hooks() -> None:
    def _excepthook(
        exc_type: type[BaseException], exc_value: BaseException, exc_tb: TracebackType | None
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            return
        logger.critical("ui.unhandled.failed reason_code=INTERNAL_ERROR")
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance():
                QMessageBox.critical(
                    None,
                    "Критическая ошибка",
                    "Произошла непредвиденная ошибка. Подробности в журнале диагностики.",
                )
        except Exception:
            pass

    sys.excepthook = _excepthook


def _start_mcp_safe(services: dict[str, Any], host: str, port: int) -> "HTTPServerHandle":
    """Return the actual owned listener, or a safely mapped startup refusal."""
    from src.infrastructure.mcp.server import HTTPServerHandle

    return HTTPServerHandle(services, host=host, port=port).start()


def run_desktop(
    qt_app: "QApplication",
    services: dict[str, Any],
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
) -> int:
    """Desktop entry owns services['runtime']; MainWindow and HTTP only borrow it.

    An existing QApplication is supported. No event-loop/server singleton is
    manufactured. Port zero is the ordinary OS allocation boundary for embedding.
    """
    runtime = services["runtime"]
    window = None
    handle = None
    code = 0
    try:
        from src.ui.main_window import MainWindow

        # Constructor attaches signals and restores list_tasks BEFORE HTTP admission.
        window = MainWindow(services)
        handle = _start_mcp_safe(
            services, host, port if port is not None else runtime.api.get_settings().mcp_port
        )
        window.show()
        code = qt_app.exec()
    except KeyboardInterrupt:
        code = 1
    except Exception as error:
        logger.error("ui.startup.failed reason_code=%s", error_payload(error)["code"])
        code = 1
    finally:
        try:
            runtime.close(cancel=True, wait=False)  # Stop admission; not a claim of quiescence.
        except Exception:
            logger.error("ui.shutdown.failed stage=admission reason_code=INTERNAL_ERROR")
            code = 1
        if handle is not None:
            try:
                if not handle.close(timeout=8):
                    logger.error("ui.shutdown.failed stage=http reason_code=EXECUTION_UNAVAILABLE")
                    code = 1
            except Exception:
                logger.error("ui.shutdown.failed stage=http reason_code=INTERNAL_ERROR")
                code = 1
        if window is not None:
            try:
                window.cleanup()
                window.close()
            except Exception:
                logger.error("ui.shutdown.failed stage=window reason_code=INTERNAL_ERROR")
                code = 1
        try:
            result = runtime.close(cancel=True, wait=True)
            if not result.closed or result.error_codes:
                logger.error(
                    "ui.shutdown.failed stage=runtime closed=%s error_count=%d",
                    result.closed,
                    len(result.error_codes),
                )
                code = 1
        except Exception:
            logger.error("ui.shutdown.failed stage=runtime reason_code=INTERNAL_ERROR")
            code = 1
    return code


def main() -> int:
    try:
        with _logging():
            previous_hook = sys.excepthook
            try:
                _install_exception_hooks()
                from PySide6.QtCore import Qt
                from PySide6.QtWidgets import QApplication

                from main import initialize_app

                QApplication.setHighDpiScaleFactorRoundingPolicy(
                    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
                )
                existing = QApplication.instance()
                qt_app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)
                qt_app.setApplicationName("YT Downloader")
                qt_app.setOrganizationName("YTDownloader")
                return run_desktop(qt_app, initialize_app())
            finally:
                sys.excepthook = previous_hook
    except Exception as error:
        payload = error_payload(error)
        print(f"Error: {payload['error']} [{payload['code']}]", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
