"""Single live task owner: admission, execution, cancellation and durable terminal facts."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from src.application.command_api import CommandError, ValidationError
from src.core.event_bus import EventBus
from src.domain.download_rules import (
    DownloadRuleError,
    normalize_options,
    normalize_url,
    validate_optional_flag,
    validate_settings,
)
from src.domain.models import AppSettings, DownloadTask, HistoryEntry
from src.domain.models.app_settings import DownloadType, QualityOption
from src.domain.models.download_outcome import DownloadOutcome
from src.domain.models.download_task import DownloadStatus
from src.domain.protocols import IHistoryRepository
from src.domain.protocols.download_service import IDownloadService
from src.domain.protocols.history_repository import StorageError

logger = logging.getLogger(__name__)


class _LifecycleExecutor(ThreadPoolExecutor):
    """The legacy explicit join still notifies the runtime; retirement does not close it."""

    def __init__(
        self,
        workers: int,
        before_shutdown: Callable[[], None],
        on_joined: Callable[[], None],
    ) -> None:
        super().__init__(max_workers=workers, thread_name_prefix="ytdl-worker")
        self._before_shutdown, self._on_joined = before_shutdown, on_joined

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        self._before_shutdown()
        super().shutdown(wait=wait, cancel_futures=cancel_futures)
        if wait:
            self._on_joined()

    def retire(self) -> None:
        super().shutdown(wait=True)


@dataclass
class _Execution:
    task: DownloadTask
    settings: AppSettings
    cancel: threading.Event = field(default_factory=threading.Event)
    admitted: threading.Event = field(default_factory=threading.Event)
    settled: threading.Event = field(default_factory=threading.Event)


class _Progress:
    def __init__(self, owner: DownloadCoordinator, execution: _Execution) -> None:
        self.owner, self.execution = owner, execution

    def __call__(self, percent: float, speed: float, eta: int) -> None:
        self.owner._progress(self.execution, percent, speed, eta)

    def measured(self, percent: float | None, speed: float | None, eta: int | None) -> None:
        self.owner._progress(self.execution, percent, speed, eta)

    def stage(self, status: DownloadStatus) -> None:
        self.owner._stage(self.execution, status)


class DownloadCoordinator:
    def __init__(
        self,
        history_repo: IHistoryRepository,
        settings: AppSettings,
        event_bus: EventBus,
        ffmpeg_path: Path | None = None,
        *,
        service_factory: Callable[[], IDownloadService],
    ) -> None:
        self._history_repo, self._event_bus = history_repo, event_bus
        self._settings = validate_settings(settings)
        self._ffmpeg_path, self._service_factory = ffmpeg_path, service_factory
        self._lock = threading.RLock()
        self._active_services: dict[int, IDownloadService] = {}
        self._futures: dict[int, Future[None]] = {}
        self._tasks: dict[int, DownloadTask] = {}
        self._executions: dict[int, _Execution] = {}
        self._closing = self._joined = False
        self._on_closing: Callable[[], None] | None = None
        self._on_joined: Callable[[], None] | None = None
        self._persistence_errors: set[int] = set()
        self._pool_cap = self._settings.max_concurrent
        self._executor = _LifecycleExecutor(self._pool_cap, self.stop_admission, self._mark_joined)
        logger.info("coordinator.executor.start workers=%d", self._pool_cap)

    def bind_lifecycle(self, on_closing: Callable[[], None], on_joined: Callable[[], None]) -> None:
        with self._lock:
            if self._on_joined is not None:
                raise RuntimeError("Coordinator already has a lifecycle owner")
            self._on_closing, self._on_joined = on_closing, on_joined

    def stop_admission(self) -> None:
        with self._lock:
            callback = self._on_closing
        if callback is not None:
            callback()
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
        snapshot = validate_settings(settings)
        with self._lock:
            if self._closing:
                raise CommandError("Runtime is closing", code="RUNTIME_CLOSING")
            self._settings = snapshot
        self._event_bus.publish("coordinator.settings_updated")

    def add(
        self,
        url: str,
        quality: QualityOption | None = None,
        download_type: DownloadType | None = None,
        subtitle_lang: str | None = None,
        save_subtitles: bool | None = None,
        save_description: bool | None = None,
        save_thumbnail: bool | None = None,
    ) -> int:
        try:
            url = normalize_url(url)
            q, t = normalize_options(quality, download_type)
            for flag in (save_subtitles, save_description, save_thumbnail):
                validate_optional_flag(flag)
            if subtitle_lang is not None and not isinstance(subtitle_lang, str):
                raise DownloadRuleError("Invalid subtitle language")
        except DownloadRuleError as exc:
            raise ValidationError(str(exc), exc.hint) from None
        submit_failed = False
        with self._lock:
            if self._closing:
                raise CommandError("Runtime is closing", code="RUNTIME_CLOSING")
            # All old futures AND notification callbacks have drained before replacement.
            # No old worker can enter another owner critical section after its final callback.
            if not self._futures and self._pool_cap != self._settings.max_concurrent:
                self._executor.retire()
                self._pool_cap = self._settings.max_concurrent
                self._executor = _LifecycleExecutor(
                    self._pool_cap,
                    self.stop_admission,
                    self._mark_joined,
                )
                logger.info("coordinator.executor.start workers=%d", self._pool_cap)
            settings = deepcopy(self._settings)
            q, t = normalize_options(q or settings.quality, t or settings.download_type)
            task_id = self._history_repo.next_id()
            task = DownloadTask(
                id=task_id,
                url=url,
                quality=q or settings.quality,
                download_type=t or settings.download_type,
                subtitle_lang=(subtitle_lang or "").strip() or settings.subtitle_lang,
                save_subtitles=settings.save_subtitles
                if save_subtitles is None
                else save_subtitles,
                save_description=settings.save_description
                if save_description is None
                else save_description,
                save_thumbnail=settings.save_thumbnail
                if save_thumbnail is None
                else save_thumbnail,
                output_root=settings.output_dir,
            )
            self._history_repo.add(
                HistoryEntry(
                    id=task_id,
                    url=url,
                    quality=task.quality,
                    download_type=task.download_type,
                    status=DownloadStatus.QUEUED,
                    output_root=settings.output_dir,
                )
            )
            execution = _Execution(task, settings)  # Token exists BEFORE submit/factory/worker.
            self._tasks[task_id], self._executions[task_id] = task, execution
            try:
                future = self._executor.submit(self._run_download, execution)
                self._futures[task_id] = future
                future.add_done_callback(lambda f: self._finished(execution, f))
            except RuntimeError:
                submit_failed = True
        if submit_failed:
            self._finish(execution, DownloadOutcome("failed", error_code="EXECUTION_UNAVAILABLE"))
            execution.settled.set()
            error = CommandError("Execution unavailable", code="EXECUTION_UNAVAILABLE")
            error.task_id = task_id
            error.result = {
                "task_id": task_id,
                "status": execution.task.status.value,
                "result_persisted": execution.task.result_persisted,
                "error_code": execution.task.error_code,
            }
            raise error
        # No subscriber runs under the coordinator lock. The worker cannot precede queued.
        try:
            logger.info("coordinator.queued id=%d", task_id)
            self._event_bus.publish("download.queued", task_id=task_id, url=url)
        finally:
            execution.admitted.set()
        return task_id

    def cancel(self, task_id: int) -> bool:
        with self._lock:
            execution = self._executions.get(task_id)
            if execution is None:
                return False
            task = execution.task
            if task.status == DownloadStatus.CANCELLED:
                return True
            if task.status.is_terminal():
                raise CommandError("Download is already terminal", code="ALREADY_TERMINAL")
            if execution.cancel.is_set():
                return True
            execution.cancel.set()
            task.cancel_requested = True
            service, future = self._active_services.get(task_id), self._futures.get(task_id)
        logger.info("coordinator.cancel_requested id=%d", task_id)
        if service is not None:
            try:
                service.cancel()  # External port, never under the coordination lock.
            except Exception:
                logger.warning("coordinator.cancel.signal_failed id=%d", task_id)
        if future is not None:
            future.cancel()  # Done callback finalizes only if the worker really did not start.
        return True

    def get_tasks(self) -> list[DownloadTask]:
        with self._lock:
            return deepcopy(list(self._tasks.values()))

    def get_task(self, task_id: int) -> DownloadTask | None:
        with self._lock:
            return deepcopy(self._tasks.get(task_id))

    def wait(self, task_id: int, timeout: float | None = None) -> DownloadTask:
        if timeout is not None and timeout < 0:
            raise ValidationError("Timeout must be nonnegative")
        with self._lock:
            execution = self._executions.get(task_id)
        if execution is None:
            code = "OWNER_REQUIRED" if self._history_repo.get_by_id(task_id) else "NOT_FOUND"
            raise CommandError("Live task not found", code=code)
        execution.settled.wait(timeout)  # Includes worker return and notification callbacks.
        with self._lock:
            return deepcopy(execution.task)

    def shutdown(self) -> None:
        self.close(wait=False, cancel=False)

    def close(self, *, wait: bool = True, cancel: bool = False) -> None:
        self.stop_admission()
        if cancel:
            for task in self.get_tasks():
                if not task.status.is_terminal():
                    try:
                        self.cancel(task.id)
                    except CommandError:
                        pass  # Completion won the owner lock; not an error or a second outcome.
        self._executor.shutdown(wait=wait)

    def close_state(self) -> tuple[bool, list[int], list[int]]:
        with self._lock:
            return self._joined, sorted(self._futures), sorted(self._persistence_errors)

    def _finished(self, execution: _Execution, future: Future[None]) -> None:
        if future.cancelled():
            self._finish(execution, DownloadOutcome("cancelled"))
        with self._lock:
            self._active_services.pop(execution.task.id, None)
            self._futures.pop(execution.task.id, None)
            execution.settled.set()  # Last owner action; no stale registration after this point.

    def _run_download(self, execution: _Execution) -> None:
        task = execution.task
        execution.admitted.wait()
        try:
            if execution.cancel.is_set():
                self._finish(execution, DownloadOutcome("cancelled"))
                return
            with self._lock:
                task.status = DownloadStatus.DOWNLOADING
                entry = self._history_repo.get_by_id(task.id)
                if entry is None:
                    raise StorageError("History record unavailable", code="PERSISTENCE_FAILED")
                entry.status = task.status
                self._history_repo.update(entry)
            self._event_bus.publish("download.started", task_id=task.id)
            service = self._service_factory()
            with self._lock:
                self._active_services[task.id] = service
            if execution.cancel.is_set():
                try:
                    service.cancel()
                except Exception:
                    logger.warning("coordinator.cancel.signal_failed id=%d", task.id)
                self._finish(execution, DownloadOutcome("cancelled"))
                return
            try:
                info = service.fetch_info(task.url, deepcopy(execution.settings))
                if execution.cancel.is_set():
                    self._finish(execution, DownloadOutcome("cancelled"))
                    return
                with self._lock:
                    task.title = info.title
                    task.playlist_title = info.playlist_title if info.is_playlist else ""
                    entry = self._history_repo.get_by_id(task.id)
                    if entry is None:
                        raise StorageError("History record unavailable", code="PERSISTENCE_FAILED")
                    entry.title, entry.playlist_title = task.title, task.playlist_title
                    self._history_repo.update(entry)
                display_title = task.playlist_title or task.title
                if display_title:
                    self._event_bus.publish(
                        "download.title_resolved",
                        task_id=task.id,
                        title=display_title,
                    )
            except StorageError:
                raise
            except Exception:
                if execution.cancel.is_set():
                    self._finish(execution, DownloadOutcome("cancelled"))
                    return
                logger.warning("coordinator.fetch_info.skipped id=%d", task.id)
            if execution.cancel.is_set():
                self._finish(execution, DownloadOutcome("cancelled"))
                return
            with self._lock:
                request = deepcopy(task)
            raw = service.download(
                request, deepcopy(execution.settings), _Progress(self, execution)
            )
            outcome = raw if isinstance(raw, DownloadOutcome) else DownloadOutcome.from_paths(raw)
            self._finish(execution, outcome)
        except StorageError:
            self._finish(execution, DownloadOutcome("failed", error_code="PERSISTENCE_FAILED"))
        except Exception:
            self._finish(execution, DownloadOutcome("failed", error_code="DOWNLOAD_FAILED"))

    def _progress(
        self,
        execution: _Execution,
        percent: float | None,
        speed: float | None,
        eta: int | None,
    ) -> None:
        with self._lock:
            task = execution.task
            if task.status.is_terminal():
                return
            task.measured_progress, task.measured_speed, task.measured_eta = percent, speed, eta
            task.progress, task.speed, task.eta_seconds = percent or 0.0, speed or 0.0, eta or 0
            legacy_percent, legacy_speed, legacy_eta = task.progress, task.speed, task.eta_seconds
        self._event_bus.publish(
            "download.progress",
            task_id=task.id,
            percent=legacy_percent,
            speed=legacy_speed,
            eta=legacy_eta,
        )

    def _stage(self, execution: _Execution, status: DownloadStatus) -> None:
        with self._lock:
            if not execution.task.status.is_terminal() and status == DownloadStatus.MERGING:
                execution.task.status = status  # Only a real backend postprocessing signal.

    @staticmethod
    def project(entry: HistoryEntry, task: DownloadTask) -> HistoryEntry:
        entry.status, entry.title, entry.playlist_title = (
            task.status,
            task.title,
            task.playlist_title,
        )
        entry.error_code, entry.error_message = task.error_code, task.error_message
        entry.finished_at, entry.artifact_paths = task.finished_at, list(task.artifact_paths)
        if task.outcome is not None:
            for field_name, key in (
                ("video_path", "video"),
                ("audio_path", "audio"),
                ("description_path", "description"),
                ("thumbnail_path", "thumbnail"),
                ("info_json_path", "info_json"),
                ("output_dir", "scan_root"),
            ):
                setattr(entry, field_name, task.outcome.get(key))
            entry.subtitle_paths = list(task.outcome.subtitles)
        return entry

    def _finish(self, execution: _Execution, outcome: DownloadOutcome) -> None:
        task = execution.task
        with self._lock:
            if task.status.is_terminal():
                return
            root = execution.settings.output_dir.resolve()

            def valid(path: Path | None) -> bool:
                try:
                    return (
                        path is not None and path.is_file() and path.resolve().is_relative_to(root)
                    )
                except OSError:
                    return False

            known = tuple(p for p in outcome.artifact_paths if valid(p))
            outcome = replace(
                outcome,
                artifact_paths=known,
                video=outcome.video if outcome.video in known else None,
                audio=outcome.audio if outcome.audio in known else None,
                subtitles=tuple(p for p in outcome.subtitles if p in known),
                description=outcome.description if outcome.description in known else None,
                thumbnail=outcome.thumbnail if outcome.thumbnail in known else None,
                info_json=outcome.info_json if outcome.info_json in known else None,
            )
            task.outcome, task.artifact_paths = outcome, list(known)
            media = outcome.audio if task.download_type == DownloadType.AUDIO else outcome.video
            if outcome.status == "failed":
                status = DownloadStatus.FAILED
                code = (
                    outcome.error_code
                    if outcome.error_code
                    in {
                        "PARTIAL_DOWNLOAD",
                        "PERSISTENCE_FAILED",
                        "EXECUTION_UNAVAILABLE",
                        "INTERRUPTED",
                    }
                    else "DOWNLOAD_FAILED"
                )
            elif outcome.status == "cancelled" or execution.cancel.is_set():
                status, code = DownloadStatus.CANCELLED, None
            elif not valid(media):
                status, code = DownloadStatus.FAILED, "DOWNLOAD_FAILED"
            else:
                status, code = DownloadStatus.DONE, None
            task.status, task.error_code, task.finished_at = status, code, datetime.now()
            task.error_message = "Download execution failed" if code else ""
            try:
                if code == "PERSISTENCE_FAILED":
                    raise StorageError("Result could not be persisted", code="PERSISTENCE_FAILED")
                entry = self._history_repo.get_by_id(task.id)
                if entry is None:
                    raise StorageError("History record unavailable", code="PERSISTENCE_FAILED")
                self._history_repo.update(self.project(entry, task))
                task.result_persisted = True
            except StorageError:
                task.status, task.error_code = DownloadStatus.FAILED, "PERSISTENCE_FAILED"
                task.error_message, task.result_persisted = "Result could not be persisted", False
                self._persistence_errors.add(task.id)
            event = "done" if task.status == DownloadStatus.DONE else task.status.value
            code = task.error_code
        if event == "done":
            self._event_bus.publish("download.done", task_id=task.id, entry_id=task.id)
        elif event == "cancelled":
            self._event_bus.publish("download.cancelled", task_id=task.id)
        else:
            self._event_bus.publish("download.failed", task_id=task.id, error=task.error_message)
        if code:
            logger.error("coordinator.failed id=%d reason_code=%s", task.id, code)
        else:
            logger.info(
                "coordinator.%s id=%d result_persisted=%s", event, task.id, task.result_persisted
            )
