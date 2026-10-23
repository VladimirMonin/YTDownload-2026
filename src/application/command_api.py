from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.application.history_semantics import (
    resolve_history_entry_folder,
    resolve_history_entry_title,
)
from src.domain.download_rules import (
    DownloadRuleError,
    normalize_options,
    normalize_url,
    validate_download_id,
    validate_optional_flag,
)
from src.domain.models.app_settings import DownloadType, QualityOption
from src.domain.protocols import IHistoryRepository

if TYPE_CHECKING:
    from src.application.download_coordinator import DownloadCoordinator

logger = logging.getLogger(__name__)

class CommandError(Exception):
    """Base command-layer exception with a user-facing hint."""

    code = "INTERNAL_ERROR"

    def __init__(
        self, message: str, hint: str | None = None, *, code: str | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        if code is not None:
            self.code = code


class ValidationError(CommandError):
    code = "INVALID_ARGUMENT"


class NotFoundError(CommandError):
    code = "NOT_FOUND"


class ConflictError(CommandError):
    code = "ALREADY_TERMINAL"


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

    def __init__(
        self, coordinator: DownloadCoordinator, history_repo: IHistoryRepository
    ) -> None:
        self._coordinator = coordinator
        self._history_repo = history_repo

    def queue_add_download(
        self,
        *,
        url: str,
        quality: str | None = "720p",
        download_type: str | None = "video",
        subtitle_lang: str | None = None,
        save_subtitles: bool | None = False,
        save_description: bool | None = False,
        save_thumbnail: bool | None = False,
    ) -> AddDownloadResult:
        normalized_url = self._normalize_url(url)
        normalized_quality, normalized_type = self._normalize_add_options(quality, download_type)

        try:
            for flag in (save_subtitles, save_description, save_thumbnail):
                validate_optional_flag(flag)
        except DownloadRuleError as exc:
            raise ValidationError(str(exc), exc.hint) from None
        task_id = self._coordinator.add(
            url=normalized_url,
            quality=QualityOption(normalized_quality) if normalized_quality is not None else None,
            download_type=DownloadType(normalized_type) if normalized_type is not None else None,
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
        download_id = self._positive_id(download_id)
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
        download_id = self._positive_id(download_id)
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
    def _positive_id(download_id: int) -> int:
        try:
            return validate_download_id(download_id)
        except DownloadRuleError as exc:
            raise ValidationError(str(exc), exc.hint) from None

    @staticmethod
    def _normalize_url(url: str) -> str:
        try:
            return normalize_url(url)
        except DownloadRuleError as exc:
            raise ValidationError(str(exc), exc.hint) from None

    @staticmethod
    def _normalize_add_options(
        quality: str | None, download_type: str | None
    ) -> tuple[str | None, str | None]:
        try:
            q, t = normalize_options(quality, download_type)
            return q.value if q is not None else None, t.value if t is not None else None
        except DownloadRuleError as exc:
            raise ValidationError(str(exc), exc.hint) from None


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
