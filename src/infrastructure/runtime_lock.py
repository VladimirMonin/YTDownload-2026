"""Exclusive process lease on one canonical data root; no lock-file unlinking."""

from __future__ import annotations

import errno
import os
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from src.domain.protocols.history_repository import StorageError


def _lock(stream: BinaryIO, *, unlock: bool = False) -> None:
    stream.seek(0)
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK if unlock else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN if unlock else fcntl.LOCK_EX | fcntl.LOCK_NB)


class RuntimeLease:
    """Own the OS handle and serialize release against in-flight repository writes."""

    def __init__(self, stream: BinaryIO) -> None:
        self._stream: BinaryIO | None = stream
        self._mutex = threading.RLock()

    @classmethod
    def acquire(cls, root: Path) -> RuntimeLease:
        stream = None
        try:
            root.mkdir(parents=True, exist_ok=True)
            stream = (root / ".writer.lock").open("a+b")
            if stream.seek(0, os.SEEK_END) == 0:
                stream.write(b"\0")
                stream.flush()
            _lock(stream)
            return cls(stream)
        except OSError as exc:
            if stream is not None:
                stream.close()
            busy = stream is not None and exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK)
            raise StorageError(
                "Another writer owns this data root"
                if busy else "Could not acquire storage ownership",
                code="OWNER_BUSY" if busy else "PERSISTENCE_FAILED",
            ) from None

    @contextmanager
    def mutation(self) -> Iterator[None]:
        """A stale repository cannot write after this lease is released."""
        with self._mutex:
            if self._stream is None:
                raise StorageError("Storage owner is closed", code="RUNTIME_CLOSING")
            yield

    def close(self) -> None:
        with self._mutex:
            stream = self._stream
            if stream is None:
                return
            try:
                _lock(stream, unlock=True)
            finally:
                try:
                    stream.close()
                finally:
                    self._stream = None
