"""Настройка логирования приложения.

Функции:
    setup_logging: Настраивает логирование с ротацией файлов.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path | None = None) -> None:
    """Настраивает логирование с ротацией файлов.

    Args:
        log_dir: Директория для файлов логов. По умолчанию — рядом с app.py.
    """
    level_str = os.environ.get("YTDL_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    if log_dir is None:
        log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # StreamHandler с явной кодировкой — иначе на Windows cp1251 → кириллица в \xNN
    import sys
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    try:
        # Python 3.9+ поддерживает reconfigure
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    handlers: list[logging.Handler] = [stream_handler]

    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    handlers.append(file_handler)

    error_handler = RotatingFileHandler(
        log_dir / "app.error.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)
    handlers.append(error_handler)

    for h in handlers:
        h.setFormatter(fmt)

    logging.basicConfig(level=level, handlers=handlers, force=True)

    # Приглушаем шумные библиотеки
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)
