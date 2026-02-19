"""Менеджер истории загрузок.

Классы:
    HistoryManager: Управляет историей загрузок и обновлением виджета истории.
"""

from __future__ import annotations

import logging
from pathlib import Path

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
    ) -> None:
        self._repo = history_repo
        self._event_bus = event_bus
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

    def delete(self, entry_id: int) -> None:
        """Удаляет запись из истории."""
        self._repo.delete(entry_id)
        logger.info("history_manager.delete id=%d", entry_id)
        if self._on_done_callback:
            self._on_done_callback()

    def _on_download_event(self, **_) -> None:
        """Вызывается при изменении статуса загрузки."""
        if self._on_done_callback:
            self._on_done_callback()
