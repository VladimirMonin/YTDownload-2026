"""Менеджер истории загрузок.

Классы:
    HistoryManager: Управляет историей загрузок и обновлением виджета истории.
"""

from __future__ import annotations

import logging
from typing import Any

from ...application.command_api import CommandError
from ...core.event_bus import EventBus

logger = logging.getLogger(__name__)


class HistoryManager:
    """Синхронный менеджер истории загрузок.

    Получает detached историю через ApplicationAPI и предоставляет интерфейс для UI.
    Обновляет список при завершении загрузок.
    """

    def __init__(
        self,
        application_api: Any,
        event_bus: EventBus,
        command_api: Any | None = None,
    ) -> None:
        # Legacy explicit command_api remains accepted; no repository fallback.
        self._api = command_api if command_api is not None else application_api
        if not callable(getattr(self._api, "delete_download", None)):
            raise CommandError("An application owner is required", code="OWNER_REQUIRED")
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
        return self._api.list_history_entries()

    def search(self, query: str):
        """Ищет записи по запросу."""
        return self._api.list_history_entries(query)

    def prepare_delete(self, entry_id: int, *, delete_files: bool = True) -> Any:
        return self._api.prepare_delete_download(entry_id, delete_files=delete_files)

    def delete(self, entry_id: int, *, delete_files: bool = False,
               expected_plan: str | None = None) -> Any:
        """Only the public token-bound command may change history or files."""
        result = self._api.delete_download(entry_id, delete_files=delete_files,
            expected_plan=expected_plan)

        logger.info("history_manager.delete id=%d delete_files=%s", entry_id, delete_files)
        if self._on_done_callback:
            self._on_done_callback()
        return result

    def _on_download_event(self, **_) -> None:
        """Вызывается при изменении статуса загрузки."""
        if self._on_done_callback:
            self._on_done_callback()
