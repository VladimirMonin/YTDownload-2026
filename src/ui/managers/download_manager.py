"""Менеджер загрузок — Signal Bridge между EventBus и UI виджетами.

Классы:
    DownloadManager: QObject-менеджер для безопасного обновления UI из EventBus.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from ...application.command_api import CommandError
from ...application.dto import QueryErrorDTO
from ...core.event_bus import EventBus
from ...domain.models.download_task import DownloadStatus, DownloadTask

if TYPE_CHECKING:
    from ...application.api import ApplicationAPI
    from ...application.dto import TaskSnapshotDTO

logger = logging.getLogger(__name__)


class DownloadManager(QObject):
    """Signal Bridge: EventBus (фоновые потоки) → Qt Signals → Main Thread.

    Подписывается на события EventBus и эмитирует Qt signals,
    которые автоматически маршализуются в главный поток Qt.
    """

    # Signals для безопасного обновления UI
    task_queued = Signal(int, str)  # task_id, url
    task_started = Signal(int)  # task_id
    task_progress = Signal(int, float, float, int)  # task_id, percent, speed, eta
    task_done = Signal(int)  # task_id
    task_failed = Signal(int, str)  # task_id, error
    task_cancelled = Signal(int)  # task_id
    task_title_updated = Signal(int, str)  # task_id, title
    task_title_resolved = Signal(int, str)  # task_id, title (сразу после fetch_info)

    def __init__(
        self,
        application_api: "ApplicationAPI",
        event_bus: EventBus,
    ) -> None:
        super().__init__()
        self._api = application_api
        self._event_bus = event_bus
        self._subscribe()

    def _subscribe(self) -> None:
        """Подписывается на события координатора."""
        self._event_bus.subscribe("download.queued", self._on_queued)
        self._event_bus.subscribe("download.started", self._on_started)
        self._event_bus.subscribe("download.progress", self._on_progress)
        self._event_bus.subscribe("download.done", self._on_done)
        self._event_bus.subscribe("download.failed", self._on_failed)
        self._event_bus.subscribe("download.cancelled", self._on_cancelled)
        self._event_bus.subscribe("download.title_resolved", self._on_title_resolved)

    def cleanup(self) -> None:
        """Отписывается от всех событий."""
        self._event_bus.unsubscribe("download.queued", self._on_queued)
        self._event_bus.unsubscribe("download.started", self._on_started)
        self._event_bus.unsubscribe("download.progress", self._on_progress)
        self._event_bus.unsubscribe("download.done", self._on_done)
        self._event_bus.unsubscribe("download.failed", self._on_failed)
        self._event_bus.unsubscribe("download.cancelled", self._on_cancelled)
        self._event_bus.unsubscribe("download.title_resolved", self._on_title_resolved)

    def add(
        self,
        url: str,
        quality=None,
        download_type=None,
        subtitle_lang=None,
        save_subtitles=None,
        save_description=None,
        save_thumbnail=None,
    ) -> int:
        """Добавляет URL в очередь через координатор.

        Returns:
            Числовой ID задачи.
        """
        return self._api.queue_add_download(
            url=url,
            quality=quality,
            download_type=download_type,
            subtitle_lang=subtitle_lang,
            save_subtitles=save_subtitles,
            save_description=save_description,
            save_thumbnail=save_thumbnail,
        ).task_id

    def cancel(self, task_id: int) -> None:
        """Запрашивает отмену; финальный статус приходит после quiescence."""
        self._api.cancel_download(task_id)

    @staticmethod
    def _view(snapshot: "TaskSnapshotDTO") -> DownloadTask:
        """Detached presentation mapping for the unchanged card widget."""
        return DownloadTask(id=snapshot.id, url=snapshot.url, title=snapshot.title,
            playlist_title=snapshot.playlist_title, status=DownloadStatus(snapshot.status),
            progress=snapshot.progress or 0.0, speed=snapshot.speed or 0.0,
            eta_seconds=snapshot.eta_seconds or 0, error_message=snapshot.error_message,
            cancel_requested=snapshot.cancel_requested, result_persisted=snapshot.result_persisted,
            error_code=snapshot.error_code)

    def get_task(self, task_id: int) -> DownloadTask | None:
        snapshot = self._api.get_task(task_id)
        if isinstance(snapshot, QueryErrorDTO):
            raise CommandError(snapshot.error, code=snapshot.code, hint=snapshot.hint)
        return self._view(snapshot) if snapshot is not None else None

    def list_tasks(self) -> list[DownloadTask]:
        return [self._view(snapshot) for snapshot in self._api.list_tasks()]

    # ── EventBus callbacks (вызываются из фонового потока) ──────

    def _on_queued(self, task_id: int, url: str, **_) -> None:
        self.task_queued.emit(task_id, url)

    def _on_started(self, task_id: int, **_) -> None:
        self.task_started.emit(task_id)
        # Обновляем задачу для получения title
        task = self.get_task(task_id)
        if task and task.title:
            self.task_title_updated.emit(task_id, task.title)

    def _on_progress(self, task_id: int, percent: float, speed: float, eta: int, **_) -> None:
        self.task_progress.emit(task_id, percent, speed, eta)

    def _on_done(self, task_id: int, **_) -> None:
        self.task_done.emit(task_id)
        # Обновляем title если изменился
        task = self.get_task(task_id)
        if task and task.title:
            self.task_title_updated.emit(task_id, task.title)

    def _on_failed(self, task_id: int, error: str, **_) -> None:
        self.task_failed.emit(task_id, error)

    def _on_cancelled(self, task_id: int, **_) -> None:
        self.task_cancelled.emit(task_id)

    def _on_title_resolved(self, task_id: int, title: str, **_) -> None:
        self.task_title_resolved.emit(task_id, title)
