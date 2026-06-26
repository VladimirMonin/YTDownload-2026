from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.application.history_semantics import (
    resolve_history_entry_folder,
    resolve_history_entry_title,
)
from src.domain.models.app_settings import DownloadType, QualityOption

logger = logging.getLogger(__name__)

_VALID_QUALITY = {"best", "1080p", "720p", "480p", "360p", "audio"}
_VALID_TYPE = {"video", "audio"}


class CommandError(Exception):
    """Base command-layer exception with a user-facing hint."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(CommandError):
    pass


class NotFoundError(CommandError):
    pass


class ConflictError(CommandError):
    pass


@dataclass(frozen=True)
class AddDownloadResult:
    task_id: int
    status: str


@dataclass(frozen=True)
class CancelPreview:
    id: int
    title: str
    current_status: str


@dataclass(frozen=True)
class CancelResult:
    id: int
    status: str


@dataclass(frozen=True)
class DeletePreview:
    id: int
    title: str
    output_dir: str | None
    file_count: int
    delete_files: bool


@dataclass(frozen=True)
class DeleteResult:
    id: int
    deleted: bool
    files_removed: bool


class DownloadCommandAPI:
    """Transport-neutral command layer shared by CLI and MCP."""

    def __init__(self, coordinator: Any, history_repo: Any) -> None:
        self._coordinator = coordinator
        self._history_repo = history_repo

    def queue_add_download(
        self,
        *,
        url: str,
        quality: str = "720p",
        download_type: str = "video",
        subtitle_lang: str | None = None,
        save_subtitles: bool = False,
        save_description: bool = False,
        save_thumbnail: bool = False,
    ) -> AddDownloadResult:
        normalized_url = self._normalize_url(url)
        normalized_quality, normalized_type = self._normalize_add_options(quality, download_type)

        quality_map = {
            "best": QualityOption.BEST,
            "1080p": QualityOption.P1080,
            "720p": QualityOption.P720,
            "480p": QualityOption.P480,
            "360p": QualityOption.P360,
            "audio": QualityOption.AUDIO,
        }
        task_id = self._coordinator.add(
            url=normalized_url,
            quality=quality_map[normalized_quality],
            download_type=(
                DownloadType.AUDIO if normalized_type == "audio" else DownloadType.VIDEO
            ),
            subtitle_lang=subtitle_lang,
            save_subtitles=save_subtitles,
            save_description=save_description,
            save_thumbnail=save_thumbnail,
        )
        logger.info(
            "command_api.queue_add_download id=%d quality=%s type=%s",
            task_id,
            normalized_quality,
            normalized_type,
        )
        return AddDownloadResult(task_id=task_id, status="queued")

    def prepare_cancel_download(self, download_id: int) -> CancelPreview:
        task = self._coordinator.get_task(download_id)
        if task is None:
            raise NotFoundError(
                f"Download #{download_id} not found or already finished",
                "Use list_downloads() to see active downloads",
            )

        current_status = task.status.value if hasattr(task.status, "value") else str(task.status)
        if task.status.is_terminal():
            raise ConflictError(
                f"Download #{download_id} is already {current_status}",
                "Can only cancel 'queued' or 'downloading' tasks",
            )

        return CancelPreview(
            id=download_id,
            title=task.title or task.url[:80],
            current_status=current_status,
        )

    def cancel_download(self, download_id: int) -> CancelResult:
        self.prepare_cancel_download(download_id)
        cancelled = self._coordinator.cancel(download_id)
        if not cancelled:
            raise ConflictError(
                f"Download #{download_id} could not be cancelled",
                "Try list_downloads() and retry while it is still queued or downloading",
            )
        logger.info("command_api.cancel_download id=%d", download_id)
        return CancelResult(id=download_id, status="cancel_requested")

    def prepare_delete_download(self, download_id: int, delete_files: bool = True) -> DeletePreview:
        entry = self._history_repo.get_by_id(download_id)
        if entry is None:
            raise NotFoundError(
                f"Download #{download_id} not found",
                "Use list_downloads() to see valid IDs",
            )

        folder = resolve_history_entry_folder(entry)
        return DeletePreview(
            id=download_id,
            title=resolve_history_entry_title(entry),
            output_dir=str(folder) if folder else None,
            file_count=_count_files(folder) if folder else 0,
            delete_files=delete_files,
        )

    def delete_download(self, download_id: int, delete_files: bool = True) -> DeleteResult:
        preview = self.prepare_delete_download(download_id, delete_files=delete_files)

        files_removed = False
        if delete_files and preview.output_dir:
            folder = Path(preview.output_dir)
            if folder.exists():
                shutil.rmtree(folder)
                files_removed = True
                logger.info(
                    "command_api.delete_download.files_removed id=%d path_len=%d",
                    download_id,
                    len(str(folder)),
                )

        self._history_repo.delete(download_id)
        logger.info(
            "command_api.delete_download id=%d files_removed=%s",
            download_id,
            files_removed,
        )
        return DeleteResult(id=download_id, deleted=True, files_removed=files_removed)

    @staticmethod
    def _normalize_url(url: str) -> str:
        normalized_url = (url or "").strip()
        if not normalized_url.startswith(("http://", "https://")):
            raise ValidationError(
                "Invalid URL",
                "URL must start with http:// or https://",
            )
        return normalized_url

    @staticmethod
    def _normalize_add_options(quality: str, download_type: str) -> tuple[str, str]:
        normalized_quality = (quality or "").lower().strip()
        normalized_type = (download_type or "").lower().strip()

        if normalized_quality == "audio":
            normalized_type = "audio"
            normalized_quality = "best"

        if normalized_quality not in _VALID_QUALITY:
            raise ValidationError(
                f"Invalid quality '{normalized_quality}'",
                f"Valid values: {', '.join(sorted(_VALID_QUALITY))}",
            )
        if normalized_type not in _VALID_TYPE:
            raise ValidationError(
                f"Invalid download_type '{normalized_type}'",
                "Valid values: video, audio",
            )
        return normalized_quality, normalized_type


def build_command_api(services: dict[str, Any]) -> DownloadCommandAPI:
    return DownloadCommandAPI(
        coordinator=services["coordinator"],
        history_repo=services["history_repo"],
    )


def _count_files(folder: Path) -> int:
    try:
        return sum(1 for candidate in folder.rglob("*") if candidate.is_file())
    except Exception:
        return 0
