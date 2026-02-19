"""Координатор загрузок — оркестрация очереди, потоков, истории.

Классы:
    DownloadCoordinator: Управляет очередью загрузок и публикует события.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.event_bus import EventBus
from ..domain.models import AppSettings, DownloadTask, HistoryEntry
from ..domain.models.app_settings import DownloadType, QualityOption
from ..domain.models.download_task import DownloadStatus
from ..domain.protocols import IHistoryRepository
from ..infrastructure.ytdlp_service import YtDlpService

logger = logging.getLogger(__name__)


class DownloadCoordinator:
    """Оркестратор загрузок.

    Управляет очередью (ThreadPoolExecutor), создаёт записи истории,
    публикует события через EventBus.

    Публикуемые события:
        download.queued(task_id, title, url)
        download.started(task_id)
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
    ) -> None:
        self._history_repo = history_repo
        self._settings = settings
        self._event_bus = event_bus
        self._ffmpeg_path = ffmpeg_path
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()
        # task_id → YtDlpService (для отмены)
        self._active_services: dict[int, YtDlpService] = {}
        # task_id → Future
        self._futures: dict[int, Future] = {}
        # Текущие задачи в памяти (queued + downloading)
        self._tasks: dict[int, DownloadTask] = {}
        self._start_executor()

    def _start_executor(self) -> None:
        """Запускает пул потоков с учётом max_concurrent."""
        if self._executor:
            self._executor.shutdown(wait=False)
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, self._settings.max_concurrent),
            thread_name_prefix="ytdl-worker",
        )
        logger.info("coordinator.executor.start workers=%d", self._settings.max_concurrent)

    def update_settings(self, settings: AppSettings) -> None:
        """Обновляет настройки (без прерывания активных загрузок).

        Args:
            settings: Новые настройки.
        """
        self._settings = settings
        # Перезапускаем executor только если изменился max_concurrent
        self._start_executor()
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
        task_id = self._history_repo.next_id()

        task = DownloadTask(
            id=task_id,
            url=url,
            quality=QualityOption(quality) if quality else self._settings.quality,
            download_type=DownloadType(download_type)
            if download_type
            else self._settings.download_type,
            subtitle_lang=subtitle_lang or self._settings.subtitle_lang,
            save_subtitles=save_subtitles
            if save_subtitles is not None
            else self._settings.save_subtitles,
            save_description=save_description
            if save_description is not None
            else self._settings.save_description,
            save_thumbnail=save_thumbnail
            if save_thumbnail is not None
            else self._settings.save_thumbnail,
        )

        with self._lock:
            self._tasks[task_id] = task

        # Создаём запись в истории сразу (статус QUEUED)
        entry = HistoryEntry(
            id=task_id,
            url=url,
            quality=task.quality,
            download_type=task.download_type,
            status=DownloadStatus.QUEUED,
        )
        self._history_repo.add(entry)

        # Отправляем в пул — будет выполнено как только освободится слот
        future = self._executor.submit(self._run_download, task)
        with self._lock:
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
            return list(self._tasks.values())

    def get_task(self, task_id: int) -> Optional[DownloadTask]:
        """Возвращает задачу по ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def shutdown(self) -> None:
        """Завершает работу координатора (ждёт активных загрузок)."""
        logger.info("coordinator.shutdown")
        if self._executor:
            self._executor.shutdown(wait=False)

    # ─── Внутренние методы ────────────────────────────────────────────

    def _run_download(self, task: DownloadTask) -> None:
        """Выполняется в рабочем потоке ThreadPoolExecutor."""
        service = YtDlpService(ffmpeg_path=self._ffmpeg_path)
        with self._lock:
            self._active_services[task.id] = service

        try:
            self._update_task_status(task, DownloadStatus.DOWNLOADING)
            self._update_entry_status(task.id, DownloadStatus.DOWNLOADING)
            self._event_bus.publish("download.started", task_id=task.id)

            # Сначала получаем метаданные (для заголовка и playlist_title)
            try:
                info = service.fetch_info(task.url, self._settings)
                task.title = info.title
                task.playlist_title = info.playlist_title if info.is_playlist else ""
                self._update_entry_title(task.id, task.title, task.playlist_title)
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
            paths = service.download(task, self._settings.output_dir, on_progress)
            logger.info(
                "coordinator.files video=%s",
                paths.get("video") or paths.get("audio") or "?",
            )

            # Обновляем историю с путями
            self._finalize_entry(task.id, paths)
            self._update_task_status(task, DownloadStatus.DONE)
            self._event_bus.publish("download.done", task_id=task.id, entry_id=task.id)
            logger.info("coordinator.done id=%d", task.id)

        except Exception as exc:
            error_msg = str(exc)
            task.error_message = error_msg
            self._update_task_status(task, DownloadStatus.FAILED)
            self._update_entry_error(task.id, error_msg)
            self._event_bus.publish("download.failed", task_id=task.id, error=error_msg)
            logger.error("coordinator.failed id=%d", task.id, exc_info=True)

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

    def _finalize_entry(self, task_id: int, paths: dict) -> None:
        """Записывает финальные пути файлов в историю."""
        entry = self._history_repo.get_by_id(task_id)
        if not entry:
            return
        entry.video_path = paths.get("video")
        entry.audio_path = paths.get("audio")
        entry.subtitle_paths = paths.get("subtitles", [])
        entry.description_path = paths.get("description")
        entry.thumbnail_path = paths.get("thumbnail")
        entry.info_json_path = paths.get("info_json")
        entry.output_dir = paths.get("scan_root")  # Папка плейлиста или папка видео
        entry.status = DownloadStatus.DONE
        entry.finished_at = datetime.now()
        self._history_repo.update(entry)

    def _update_entry_error(self, task_id: int, error: str) -> None:
        entry = self._history_repo.get_by_id(task_id)
        if entry:
            entry.status = DownloadStatus.FAILED
            entry.error_message = error
            entry.finished_at = datetime.now()
            self._history_repo.update(entry)
