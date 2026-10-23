"""Lazy QtCore system Trash boundary, usable without QApplication."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.domain.protocols.file_remover import FileRemovalError

logger = logging.getLogger(__name__)


def _qfile() -> Any:
    from PySide6.QtCore import QFile

    return QFile


def _identity(path: Path) -> tuple[int, int, int, int, int] | None:
    try:
        info = path.lstat()
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    except FileNotFoundError:
        return None


class QtFileRemover:
    def move_to_trash(self, path: Path) -> bool:
        before = None
        attempted = False
        try:
            before = _identity(path)
            qt = _qfile()
            capability = getattr(qt, "supportsMoveToTrash", None)
            move = getattr(qt, "moveToTrash", None)
            if not callable(capability) or not capability() or not callable(move):
                raise FileRemovalError()
            # Installed static overload returns (bool, pathInTrash); do not coerce tuple truthiness.
            attempted = True
            result = move(str(path))
            succeeded = (
                isinstance(result, tuple)
                and len(result) == 2
                and result[0] is True
                and isinstance(result[1], str)
            )
            after = _identity(path)
            if not succeeded or before is None or after == before:
                raise FileRemovalError(outcome="unknown" if after != before else "failed")
            logger.info("trash.move.completed count=1")
            return True
        except FileRemovalError:
            logger.error("trash.move.failed reason_code=TRASH_UNAVAILABLE")
            raise
        except Exception:
            try:
                outcome = "failed" if not attempted or _identity(path) == before else "unknown"
            except OSError:
                outcome = "unknown"
            logger.error("trash.move.failed reason_code=TRASH_UNAVAILABLE")
            raise FileRemovalError(outcome=outcome) from None

    def close(self) -> None:
        pass
