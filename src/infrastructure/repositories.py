"""Atomic fail-closed JSON adapters; detached caches, no implicit writer lease.

Composition supplies a live lease mutation guard. Direct repository users own
that policy explicitly. Failed unique temporary files are retained, never scanned
or permanently removed here; successful replace consumes the owned temp name.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.application.history_semantics import history_entry_matches_query
from src.domain.download_rules import validate_settings
from src.domain.models import AppSettings, HistoryEntry
from src.domain.protocols import IHistoryRepository, ISettingsRepository
from src.domain.protocols.history_repository import StorageError

logger = logging.getLogger(__name__)
_HISTORY_FILE = "history.json"
_SETTINGS_FILE = "settings.json"
MutationGuard = Callable[[], AbstractContextManager[None]]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate storage key")
        result[key] = value
    return result


def _read_object(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream, object_pairs_hook=_unique_object)
        if not isinstance(data, dict):
            raise ValueError("Storage must contain an object")
        return data
    except FileNotFoundError:
        return None
    except (ValueError, TypeError):
        logger.error("repository.read.failed reason_code=STORAGE_CORRUPT")
        raise StorageError("Stored data is corrupt", code="STORAGE_CORRUPT") from None
    except OSError:
        logger.error("repository.read.failed reason_code=PERSISTENCE_FAILED")
        raise StorageError("Stored data could not be read", code="PERSISTENCE_FAILED") from None


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}-", suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except (OSError, ValueError, TypeError):
        logger.error("repository.write.failed reason_code=PERSISTENCE_FAILED")
        raise StorageError("Stored data could not be saved", code="PERSISTENCE_FAILED") from None


class JsonHistoryRepository(IHistoryRepository):
    """JSON {next_id, entries}; publish the new cache only after atomic replace."""

    def __init__(
        self, data_dir: Path, *, read_only: bool = False, write_guard: MutationGuard = nullcontext
    ) -> None:
        self._path = data_dir / _HISTORY_FILE
        self._lock = threading.Lock()
        self._read_only = read_only
        self._write_guard = write_guard
        self._entries: dict[int, HistoryEntry] = {}
        self._next_id = 1
        self._load()

    def _load(self) -> None:
        data = _read_object(self._path)
        if data is None:
            return
        try:
            next_id, rows = data.get("next_id", 1), data.get("entries", [])
            if type(next_id) is not int or next_id < 1 or not isinstance(rows, list):
                raise ValueError
            entries: dict[int, HistoryEntry] = {}
            for row in rows:
                entry = HistoryEntry.from_dict(row)
                if type(entry.id) is not int or entry.id < 1 or entry.id in entries:
                    raise ValueError
                entries[entry.id] = entry
            self._entries = entries
            self._next_id = max(next_id, max(entries, default=0) + 1)
        except (KeyError, TypeError, ValueError, AttributeError):
            logger.error("history.load.failed reason_code=STORAGE_CORRUPT")
            raise StorageError("Stored history is corrupt", code="STORAGE_CORRUPT") from None
        logger.info("history.load count=%d", len(self._entries))

    def _writable(self) -> None:
        if self._read_only:
            raise StorageError("A writable owner is required", code="OWNER_REQUIRED")

    def _save(self, entries: dict[int, HistoryEntry], next_id: int) -> None:
        self._writable()
        with self._write_guard():
            _atomic_write(self._path, {
                "next_id": next_id,
                "entries": [e.to_dict() for e in sorted(entries.values(), key=lambda e: -e.id)],
            })
            self._entries, self._next_id = entries, next_id

    def next_id(self) -> int:
        with self._lock:
            current = self._next_id
            self._save(dict(self._entries), current + 1)
            return current

    def add(self, entry: HistoryEntry) -> None:
        if type(entry.id) is not int or entry.id < 1:
            raise ValueError("History id must be a positive integer")
        with self._lock:
            if entry.id in self._entries:
                raise KeyError("History id already exists")
            candidate = deepcopy(self._entries)
            candidate[entry.id] = deepcopy(entry)
            self._save(candidate, max(self._next_id, entry.id + 1))
            logger.info("history.add id=%d", entry.id)

    def update(self, entry: HistoryEntry) -> None:
        self.update_many([entry])

    def update_many(self, entries: list[HistoryEntry]) -> None:
        with self._lock:
            self._writable()
            candidate = deepcopy(self._entries)
            for entry in entries:
                if type(entry.id) is not int or entry.id < 1:
                    raise ValueError("History id must be a positive integer")
                if entry.id not in candidate:
                    raise KeyError("History entry does not exist")
                candidate[entry.id] = deepcopy(entry)
            if entries:
                self._save(candidate, self._next_id)
                logger.info("history.update count=%d", len(entries))

    def get_by_id(self, entry_id: int) -> HistoryEntry | None:
        with self._lock:
            return deepcopy(self._entries.get(entry_id))

    def get_all(self) -> list[HistoryEntry]:
        with self._lock:
            return deepcopy(sorted(self._entries.values(), key=lambda entry: -entry.id))

    def search(self, query: str) -> list[HistoryEntry]:
        return [entry for entry in self.get_all() if history_entry_matches_query(entry, query)]

    def delete(self, entry_id: int) -> None:
        with self._lock:
            self._writable()
            if entry_id in self._entries:
                candidate = deepcopy(self._entries)
                candidate.pop(entry_id)
                self._save(candidate, self._next_id)
                logger.info("history.delete id=%d", entry_id)


class JsonSettingsRepository(ISettingsRepository):
    """Detached validated settings; failed replace leaves cache and old bytes intact."""

    def __init__(
        self, config_dir: Path, *, read_only: bool = False, write_guard: MutationGuard = nullcontext
    ) -> None:
        self._path = config_dir / _SETTINGS_FILE
        self._lock = threading.Lock()
        self._read_only = read_only
        self._write_guard = write_guard
        data = _read_object(self._path)
        try:
            loaded = AppSettings.from_dict(data) if data is not None else AppSettings()
            self._settings = validate_settings(loaded)
        except (KeyError, TypeError, ValueError, AttributeError):
            logger.error("settings.load.failed reason_code=STORAGE_CORRUPT")
            raise StorageError("Stored settings are corrupt", code="STORAGE_CORRUPT") from None

    def load(self) -> AppSettings:
        with self._lock:
            return deepcopy(self._settings)

    def save(self, settings: AppSettings) -> None:
        candidate = validate_settings(settings)
        with self._lock:
            if self._read_only:
                raise StorageError("A writable owner is required", code="OWNER_REQUIRED")
            with self._write_guard():
                _atomic_write(self._path, candidate.to_dict())
                self._settings = candidate
            logger.info("settings.save ok")
