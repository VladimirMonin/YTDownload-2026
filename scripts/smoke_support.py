"""Small offline-smoke isolation and legacy resource cleanup helpers.

Synthetic roots are retained (no permanent file deletion). This is not the
application's future runtime/lifecycle implementation.
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


@contextmanager
def isolated_smoke() -> Iterator[Path]:
    """Assign owned paths before importing application/Qt/MCP modules."""
    root = Path(tempfile.mkdtemp(prefix="ytdl-smoke-", dir=os.getenv("YTDL_SMOKE_ROOT")))
    paths = {
        "APPDATA": root / "appdata",
        "LOCALAPPDATA": root / "localappdata",
        "HOME": root / "home",
        "USERPROFILE": root / "home",
        "TMP": root / "temp",
        "TEMP": root / "temp",
        "TMPDIR": root / "temp",
        "XDG_CACHE_HOME": root / "cache",
        "UV_CACHE_DIR": root / "cache" / "uv",
        "YTDL_LOG_DIR": root / "logs",
        "YTDL_OUTPUT_DIR": root / "home" / "Downloads" / "YTDownloader",
    }
    overrides = {key: str(path) for key, path in paths.items()}
    overrides.update(
        UV_OFFLINE="1", UV_NO_SYNC="1", UV_PYTHON_DOWNLOADS="never",
        PYTHONDONTWRITEBYTECODE="1", QT_QPA_PLATFORM="offscreen",
        FASTMCP_CHECK_FOR_UPDATES="off", DO_NOT_TRACK="1",
    )
    previous = {key: os.environ.get(key) for key in overrides}
    previous_temp = tempfile.tempdir
    logger = logging.getLogger()
    borrowed_handlers = logger.handlers[:]
    try:
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        os.environ.update(overrides)
        tempfile.tempdir = str(root / "temp")
        yield root
    finally:
        try:
            for handler in logger.handlers[:]:
                if handler not in borrowed_handlers:
                    logger.removeHandler(handler)
                    try:
                        handler.flush()
                    finally:
                        handler.close()
        finally:
            tempfile.tempdir = previous_temp
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def close_services(services: dict[str, Any] | None) -> None:
    """Join only this smoke's coordinator; legacy shutdown() does not wait."""
    if services is not None:
        services["coordinator"]._executor.shutdown(wait=True)
