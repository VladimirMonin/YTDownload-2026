"""Репозитории на базе JSON файлов.

Классы:
    JsonHistoryRepository: История загрузок в JSON с автоинкрементным ID.
    JsonSettingsRepository: Настройки в JSON файле.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

from src.application.history_semantics import history_entry_matches_query

from ..domain.models import AppSettings, HistoryEntry
from ..domain.protocols import IHistoryRepository, ISettingsRepository

logger = logging.getLogger(__name__)

_HISTORY_FILE = "history.json"
_SETTINGS_FILE = "settings.json"


class JsonHistoryRepository(IHistoryRepository):
    """Хранит историю загрузок в JSON файле.

    Формат файла:
        { "next_id": 1, "entries": [{...}, ...] }

    ID автоинкрементируется потокобезопасно.
    """

    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / _HISTORY_FILE
        self._lock = threading.Lock()
        self._entries: dict[int, HistoryEntry] = {}
        self._next_id: int = 1
        self._load()

    def _load(self) -> None:
        """Загружает данные из файла."""
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._next_id = data.get("next_id", 1)
            for item in data.get("entries", []):
                entry = HistoryEntry.from_dict(item)
                self._entries[entry.id] = entry
            logger.info("history.load count=%d", len(self._entries))
        except Exception:
            logger.error("history.load.failed", exc_info=True)

    def _save(self) -> None:
        """Сохраняет данные в файл (вызывается под локом)."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "next_id": self._next_id,
                "entries": [
                    e.to_dict() for e in sorted(self._entries.values(), key=lambda x: -x.id)
                ],
            }
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.error("history.save.failed", exc_info=True)

    def next_id(self) -> int:
        """Возвращает и резервирует следующий доступный ID."""
        with self._lock:
            current = self._next_id
            self._next_id += 1
            self._save()
            return current

    def add(self, entry: HistoryEntry) -> None:
        """Добавляет запись в историю."""
        with self._lock:
            self._entries[entry.id] = entry
            self._save()
            _status = entry.status.value if hasattr(entry.status, "value") else entry.status
            logger.info("history.add id=%d status=%s", entry.id, _status)

    def update(self, entry: HistoryEntry) -> None:
        """Обновляет существующую запись."""
        with self._lock:
            if entry.id not in self._entries:
                raise KeyError(f"Entry id={entry.id} not found")
            self._entries[entry.id] = entry
            self._save()
            _status = entry.status.value if hasattr(entry.status, "value") else entry.status
            logger.info("history.update id=%d status=%s", entry.id, _status)

    def get_by_id(self, entry_id: int) -> Optional[HistoryEntry]:
        """Возвращает запись по ID."""
        with self._lock:
            return self._entries.get(entry_id)

    def get_all(self) -> list[HistoryEntry]:
        """Возвращает все записи, новые первыми."""
        with self._lock:
            return sorted(self._entries.values(), key=lambda e: -e.id)

    def search(self, query: str) -> list[HistoryEntry]:
        """Ищет записи по названию или URL (нечувствительно к регистру)."""
        with self._lock:
            return [
                e
                for e in sorted(self._entries.values(), key=lambda x: -x.id)
                if history_entry_matches_query(e, query)
            ]

    def delete(self, entry_id: int) -> None:
        """Удаляет запись по ID."""
        with self._lock:
            if entry_id in self._entries:
                del self._entries[entry_id]
                self._save()
                logger.info("history.delete id=%d", entry_id)


class JsonSettingsRepository(ISettingsRepository):
    """Хранит настройки приложения в JSON файле."""

    def __init__(self, config_dir: Path) -> None:
        self._path = config_dir / _SETTINGS_FILE

    def load(self) -> AppSettings:
        """Загружает настройки из файла (defaults если файл не найден)."""
        if not self._path.exists():
            return AppSettings()
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return AppSettings.from_dict(data)
        except Exception:
            logger.error("settings.load.failed", exc_info=True)
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        """Сохраняет настройки в файл."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(settings.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info("settings.save ok")
        except Exception:
            logger.error("settings.save.failed", exc_info=True)
