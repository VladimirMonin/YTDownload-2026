"""Менеджер истории загрузок.

Классы:
    HistoryManager: Управляет историей загрузок и обновлением виджета истории.
"""

from __future__ import annotations

import logging
from typing import Any

from ...core.event_bus import EventBus
from ...domain.protocols import IHistoryRepository

logger = logging.getLogger(__name__)


class HistoryManager:
    """Синхронный менеджер истории загрузок.

    Загружает историю из репозитория и предоставляет интерфейс для UI.
    Обновляет список при завершении загрузок.
    """

    def __init__(
        self,
        history_repo: IHistoryRepository,
        event_bus: EventBus,
        command_api: Any | None = None,
    ) -> None:
        self._repo = history_repo
        self._event_bus = event_bus
        self._command_api = command_api
        self._on_done_callback = None
        self._subscribe()

    def _subscribe(self) -> None:
        self._event_bus.subscribe("download.done", self._on_download_event)
        self._event_bus.subscribe("download.failed", self._on_download_event)
        self._event_bus.subscribe("download.cancelled", self._on_download_event)

    def cleanup(self) -> None:
        """Отписывается от событий."""
        self._event_bus.unsubscribe("download.done", self._on_download_event)
        self._event_bus.unsubscribe("download.failed", self._on_download_event)
        self._event_bus.unsubscribe("download.cancelled", self._on_download_event)

    def set_on_updated(self, callback) -> None:
        """Устанавливает коллбэк обновления (вызывается когда история изменилась)."""
        self._on_done_callback = callback

    def get_all(self):
        """Возвращает все записи истории."""
        return self._repo.get_all()

    def search(self, query: str):
        """Ищет записи по запросу."""
        return self._repo.search(query)

    def delete(self, entry_id: int, *, delete_files: bool = False) -> Any:
        """Удаляет запись из истории."""
        if self._command_api is not None:
            result = self._command_api.delete_download(entry_id, delete_files=delete_files)
        else:
            self._repo.delete(entry_id)
            result = None

        logger.info("history_manager.delete id=%d delete_files=%s", entry_id, delete_files)
        if self._on_done_callback:
            self._on_done_callback()
        return result

    def _on_download_event(self, **_) -> None:
        """Вызывается при изменении статуса загрузки."""
        if self._on_done_callback:
            self._on_done_callback()
