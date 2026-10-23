"""Координатор загрузок — оркестрация очереди, потоков, истории.

Классы:
    DownloadCoordinator: Управляет очередью загрузок и публикует события.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.application.command_api import CommandError, ValidationError
from src.domain.download_rules import (
    DownloadRuleError,
    normalize_options,
    normalize_url,
    validate_optional_flag,
    validate_settings,
)
from src.domain.protocols.download_service import DownloadPaths, IDownloadService
from src.domain.protocols.history_repository import StorageError

from ..core.event_bus import EventBus
from ..domain.models import AppSettings, DownloadTask, HistoryEntry
from ..domain.models.app_settings import DownloadType, QualityOption
from ..domain.models.download_task import DownloadStatus
from ..domain.protocols import IHistoryRepository

logger = logging.getLogger(__name__)


class _LifecycleExecutor(ThreadPoolExecutor):
    """Keep legacy explicit executor.shutdown cleanup within the runtime owner.

    No finalizer/GC release: only a real wait=True join invokes on_joined.
    """

    def __init__(
        self, workers: int, before_shutdown: Callable[[], None], on_joined: Callable[[], None]
    ) -> None:
        super().__init__(max_workers=workers, thread_name_prefix="ytdl-worker")
        self._before_shutdown = before_shutdown
        self._on_joined = on_joined

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        self._before_shutdown()
        super().shutdown(wait=wait, cancel_futures=cancel_futures)
        if wait:
            self._on_joined()


class DownloadCoordinator:
    """Оркестратор загрузок.

    Управляет очередью (ThreadPoolExecutor), создаёт записи истории,
    публикует события через EventBus.

    Публикуемые события:
        download.queued(task_id, title, url)
        download.started(task_id)
        download.title_resolved(task_id, title)
        download.progress(task_id, percent, speed, eta)
        download.done(task_id, entry_id)
        download.failed(task_id, error)
        download.cancelled(task_id)
        coordinator.settings_updated()
    """

    def __init__(
        self,
        history_repo: IHistoryRepository,
        settings: AppSettings,
        event_bus: EventBus,
        ffmpeg_path: Optional[Path] = None,
        *,
        service_factory: Callable[[], IDownloadService],
    ) -> None:
        self._history_repo = history_repo
        self._settings = validate_settings(settings)
        self._event_bus = event_bus
        self._ffmpeg_path = ffmpeg_path  # Legacy bootstrap readback, not backend construction.
        self._service_factory = service_factory
        self._lock = threading.RLock()
        self._active_services: dict[int, IDownloadService] = {}
        self._futures: dict[int, Future[None]] = {}
        self._tasks: dict[int, DownloadTask] = {}
        self._closing = False
        self._joined = False
        self._on_closing: Callable[[], None] | None = None
        self._on_joined: Callable[[], None] | None = None
        self._persistence_errors: set[int] = set()
        self._executor = _LifecycleExecutor(
            self._settings.max_concurrent, self.stop_admission, self._mark_joined
        )
        logger.info("coordinator.executor.start workers=%d", self._settings.max_concurrent)

    def bind_lifecycle(
        self, on_closing: Callable[[], None], on_joined: Callable[[], None]
    ) -> None:
        """One owning runtime; borrowed wrappers must not bind/release this owner."""
        with self._lock:
            if self._on_joined is not None:
                raise RuntimeError("Coordinator already has a lifecycle owner")
            self._on_closing, self._on_joined = on_closing, on_joined

    def stop_admission(self) -> None:
        with self._lock:
            callback = self._on_closing
        if callback is not None:
            callback()  # Serialize the owner's settings save/update before closing admission.
        with self._lock:
            self._closing = True

    def _mark_joined(self) -> None:
        with self._lock:
            self._joined = True
            callback = self._on_joined
        if callback is not None:
            callback()

    def get_settings(self) -> AppSettings:
        with self._lock:
            return deepcopy(self._settings)

    def update_settings(self, settings: AppSettings) -> None:
        """Snapshot new admissions; pool-generation/drain policy is completed in S3.

        Never abandon a running executor or release its storage lease to resize it.
        """
        snapshot = validate_settings(settings)
        with self._lock:
            if self._closing:
                raise CommandError("Runtime is closing", code="RUNTIME_CLOSING")
            self._settings = snapshot
        self._event_bus.publish("coordinator.settings_updated")

    def add(
        self,
        url: str,
        quality: Optional[QualityOption] = None,
        download_type: Optional[DownloadType] = None,
        subtitle_lang: Optional[str] = None,
        save_subtitles: Optional[bool] = None,
        save_description: Optional[bool] = None,
        save_thumbnail: Optional[bool] = None,
    ) -> int:
        """Добавляет URL в очередь загрузки.

        Использует настройки из AppSettings как defaults,
        но позволяет переопределить на уровне задачи.

        Args:
            url: URL видео или плейлиста.
            quality: Качество (или из настроек).
            download_type: Тип загрузки (или из настроек).
            subtitle_lang: Язык субтитров (или из настроек).
            save_subtitles: Сохранять субтитры (или из настроек).
            save_description: Сохранять описание (или из настроек).
            save_thumbnail: Сохранять обложку (или из настроек).

        Returns:
            Числовой ID задачи.
        """
        try:
            url = normalize_url(url)
            q, t = normalize_options(quality, download_type)
            for flag in (save_subtitles, save_description, save_thumbnail):
                validate_optional_flag(flag)
            if subtitle_lang is not None and not isinstance(subtitle_lang, str):
                raise DownloadRuleError("Invalid subtitle language")
        except DownloadRuleError as exc:
            raise ValidationError(str(exc), exc.hint) from None

        # Admission -> repository locks. Never hold either around backend I/O.
        with self._lock:
            if self._closing:
                raise CommandError("Runtime is closing", code="RUNTIME_CLOSING")
            settings = deepcopy(self._settings)
            q, t = normalize_options(
                q if q is not None else settings.quality,
                t if t is not None else settings.download_type,
            )
            task_id = self._history_repo.next_id()
            task = DownloadTask(
                id=task_id, url=url,
                quality=q if q is not None else settings.quality,
                download_type=t if t is not None else settings.download_type,
                subtitle_lang=(subtitle_lang or "").strip() or settings.subtitle_lang,
                save_subtitles=(
                    settings.save_subtitles if save_subtitles is None else save_subtitles
                ),
                save_description=(
                    settings.save_description if save_description is None else save_description
                ),
                save_thumbnail=(
                    settings.save_thumbnail if save_thumbnail is None else save_thumbnail
                ),
            )
            entry = HistoryEntry(
                id=task_id, url=url, quality=task.quality, download_type=task.download_type,
                status=DownloadStatus.QUEUED, output_root=settings.output_dir,
            )
            # A failed reservation/add cannot publish a task, submit or invoke a backend.
            self._history_repo.add(entry)
            self._tasks[task_id] = task
            try:
                future = self._executor.submit(self._run_download, task, settings)
            except RuntimeError:
                self._update_entry_error(task_id, "Execution unavailable", "EXECUTION_UNAVAILABLE")
                task.status = DownloadStatus.FAILED
                raise CommandError("Execution unavailable", code="EXECUTION_UNAVAILABLE") from None
            self._futures[task_id] = future

        logger.info("coordinator.queued id=%d", task_id)
        self._event_bus.publish("download.queued", task_id=task_id, url=url)
        return task_id

    def cancel(self, task_id: int) -> bool:
        """Отменяет загрузку по ID.

        Args:
            task_id: ID задачи.

        Returns:
            True если отмена инициирована.
        """
        with self._lock:
            future = self._futures.get(task_id)
            service = self._active_services.get(task_id)

        cancelled = False
        if future and not future.done():
            # Если ещё не запущена — отменяем Future напрямую
            if future.cancel():
                cancelled = True
                logger.info("coordinator.cancel.future id=%d", task_id)

        if service:
            # Если уже скачивается — сигнализируем сервису
            service.cancel()
            cancelled = True
            logger.info("coordinator.cancel.service id=%d", task_id)

        if cancelled:
            self._update_entry_status(task_id, DownloadStatus.CANCELLED)
            self._event_bus.publish("download.cancelled", task_id=task_id)

        return cancelled

    def get_tasks(self) -> list[DownloadTask]:
        """Возвращает список активных задач (queued + downloading)."""
        with self._lock:
            return deepcopy(list(self._tasks.values()))

    def get_task(self, task_id: int) -> Optional[DownloadTask]:
        """Возвращает задачу по ID."""
        with self._lock:
            return deepcopy(self._tasks.get(task_id))

    def shutdown(self) -> None:
        """Legacy nonblocking close request; not a completed join."""
        self.close(wait=False, cancel=False)

    def close(self, *, wait: bool = True, cancel: bool = False) -> None:
        """Drain and join ownership; cancellation still uses the legacy S3-pending path."""
        self.stop_admission()
        try:
            if cancel:
                for task in self.get_tasks():
                    if not task.status.is_terminal():
                        try:
                            self.cancel(task.id)
                        except StorageError:
                            with self._lock:
                                self._persistence_errors.add(task.id)
        finally:
            self._executor.shutdown(wait=wait)

    def close_state(self) -> tuple[bool, list[int], list[int]]:
        with self._lock:
            pending = [task_id for task_id, future in self._futures.items() if not future.done()]
            return self._joined, sorted(pending), sorted(self._persistence_errors)

    # ─── Внутренние методы ────────────────────────────────────────────

    def _run_download(self, task: DownloadTask, settings: AppSettings) -> None:
        """Run the injected backend with this admission's detached settings."""
        try:
            service = self._service_factory()
            with self._lock:
                self._active_services[task.id] = service
            self._update_task_status(task, DownloadStatus.DOWNLOADING)
            self._update_entry_status(task.id, DownloadStatus.DOWNLOADING)
            self._event_bus.publish("download.started", task_id=task.id)

            # Сначала получаем метаданные (для заголовка и playlist_title)
            try:
                info = service.fetch_info(task.url, settings)
                task.title = info.title
                task.playlist_title = info.playlist_title if info.is_playlist else ""
                self._update_entry_title(task.id, task.title, task.playlist_title)
                # Уведомляем UI о полученном заголовке
                display_title = task.playlist_title or task.title
                if display_title:
                    self._event_bus.publish(
                        "download.title_resolved",
                        task_id=task.id,
                        title=display_title,
                    )
            except StorageError:
                raise  # A storage refusal is not an optional metadata-fetch failure.
            except Exception:
                logger.warning("coordinator.fetch_info.skipped id=%d", task.id)

            def on_progress(percent: float, speed: float, eta: int) -> None:
                task.progress = percent
                task.speed = speed
                task.eta_seconds = eta
                self._event_bus.publish(
                    "download.progress",
                    task_id=task.id,
                    percent=percent,
                    speed=speed,
                    eta=eta,
                )

            self._update_task_status(task, DownloadStatus.MERGING)
            paths = service.download(task, settings, on_progress)
            logger.info(
                "coordinator.files has_video=%s has_audio=%s",
                paths.get("video") is not None,
                paths.get("audio") is not None,
            )

            # Обновляем историю с путями
            self._finalize_entry(task.id, paths)
            self._update_task_status(task, DownloadStatus.DONE)
            self._event_bus.publish("download.done", task_id=task.id, entry_id=task.id)
            logger.info("coordinator.done id=%d", task.id)

        except StorageError:
            with self._lock:
                self._persistence_errors.add(task.id)
            task.error_message = "Result could not be persisted"
            self._update_task_status(task, DownloadStatus.FAILED)
            logger.error("coordinator.failed id=%d reason_code=PERSISTENCE_FAILED", task.id)
        except Exception:
            error_msg = "Download execution failed"
            task.error_message = error_msg
            self._update_task_status(task, DownloadStatus.FAILED)
            try:
                self._update_entry_error(task.id, error_msg, "DOWNLOAD_FAILED")
            except StorageError:
                with self._lock:
                    self._persistence_errors.add(task.id)
            self._event_bus.publish("download.failed", task_id=task.id, error=error_msg)
            logger.error("coordinator.failed id=%d reason_code=DOWNLOAD_FAILED", task.id)

        finally:
            with self._lock:
                self._active_services.pop(task.id, None)
                self._futures.pop(task.id, None)
                # Удаляем из активных задач через небольшое время
                # (оставляем в tasks чтобы UI мог показать финальный статус)

    def _update_task_status(self, task: DownloadTask, status: DownloadStatus) -> None:
        task.status = status

    def _update_entry_status(self, task_id: int, status: DownloadStatus) -> None:
        entry = self._history_repo.get_by_id(task_id)
        if entry:
            entry.status = status
            if status.is_terminal():
                entry.finished_at = datetime.now()
            self._history_repo.update(entry)

    def _update_entry_title(self, task_id: int, title: str, playlist_title: str) -> None:
        entry = self._history_repo.get_by_id(task_id)
        if entry:
            entry.title = title
            entry.playlist_title = playlist_title
            self._history_repo.update(entry)

    def _finalize_entry(self, task_id: int, paths: DownloadPaths) -> None:
        """Legacy path-map projection, with correct subtitle-list typing (outcomes: S3)."""
        entry = self._history_repo.get_by_id(task_id)
        if not entry:
            return

        def path(key: str) -> Path | None:
            value = paths.get(key)
            return value if isinstance(value, Path) else None

        entry.video_path = path("video")
        entry.audio_path = path("audio")
        subtitles = paths.get("subtitles")
        entry.subtitle_paths = list(subtitles) if isinstance(subtitles, list) else []
        entry.description_path = path("description")
        entry.thumbnail_path = path("thumbnail")
        entry.info_json_path = path("info_json")
        entry.output_dir = path("scan_root")
        entry.status = DownloadStatus.DONE
        entry.finished_at = datetime.now()
        self._history_repo.update(entry)

    def _update_entry_error(
        self, task_id: int, error: str, error_code: str = "DOWNLOAD_FAILED"
    ) -> None:
        entry = self._history_repo.get_by_id(task_id)
        if entry:
            entry.status = DownloadStatus.FAILED
            entry.error_message = error
            entry.error_code = error_code
            entry.finished_at = datetime.now()
            self._history_repo.update(entry)
