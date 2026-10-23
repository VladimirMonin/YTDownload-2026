from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.application.dto import DeleteFileDTO
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
    from src.application.deletion import DeletionPolicy
    from src.application.download_coordinator import DownloadCoordinator
    from src.domain.protocols.file_remover import IFileRemover

logger = logging.getLogger(__name__)

class CommandError(Exception):
    """Base command-layer exception with a user-facing hint."""

    code = "INTERNAL_ERROR"
    task_id: int | None = None
    result: dict[str, object] | None = None

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
    plan_token: str = ""
    files: list[DeleteFileDTO] = field(default_factory=list)
    missing_count: int = 0
    output_root: str | None = None


@dataclass(frozen=True)
class DeleteResult:
    id: int
    deleted: bool
    files_removed: bool
    files: list[DeleteFileDTO] = field(default_factory=list)
    moved_count: int = 0
    missing_count: int = 0


class DownloadCommandAPI:
    """Transport-neutral command layer shared by CLI and MCP."""

    def __init__(
        self, coordinator: DownloadCoordinator | None, history_repo: IHistoryRepository,
        *, file_remover: IFileRemover | None = None, data_root: Path | None = None,
        output_root: Path | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._history_repo = history_repo
        self._file_remover = file_remover
        self._data_root, self._output_root = data_root, output_root

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
        if self._coordinator is None:
            raise CommandError("A live owner is required", code="OWNER_REQUIRED")
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
        if self._coordinator is None:
            raise CommandError("A live owner is required", code="OWNER_REQUIRED")
        task = self._coordinator.get_task(download_id)
        if task is None:
            if self._history_repo.get_by_id(download_id) is not None:
                raise CommandError("A live owner is required", code="OWNER_REQUIRED")
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
        download_id = self._positive_id(download_id)
        if self._coordinator is None:
            raise CommandError("A live owner is required", code="OWNER_REQUIRED")
        task = self._coordinator.get_task(download_id)
        if task is None:
            if self._history_repo.get_by_id(download_id) is not None:
                raise CommandError("A live owner is required", code="OWNER_REQUIRED")
            raise NotFoundError(f"Download #{download_id} not found")
        if task.status.value == "cancelled":
            return CancelResult(download_id, "cancelled")
        if task.status.is_terminal():
            raise ConflictError(f"Download #{download_id} is already terminal")
        if not self._coordinator.cancel(download_id):
            raise ConflictError(f"Download #{download_id} could not be cancelled")
        logger.info("command_api.cancel_download id=%d", download_id)
        return CancelResult(id=download_id, status="cancel_requested")

    def _deletion(self) -> DeletionPolicy:
        from src.application.deletion import DeletionPolicy
        from src.application.download_coordinator import DownloadCoordinator

        owner = self._coordinator if isinstance(self._coordinator, DownloadCoordinator) else None
        return DeletionPolicy(self._history_repo, owner, self._file_remover,
                              self._data_root, self._output_root)

    @staticmethod
    def _delete_mode(delete_files: bool) -> bool:
        if not isinstance(delete_files, bool):
            raise ValidationError("delete_files must be a boolean")
        return delete_files

    def prepare_delete_download(self, download_id: int, delete_files: bool = True) -> DeletePreview:
        return self._deletion().preview(
            self._positive_id(download_id), self._delete_mode(delete_files)
        )

    def delete_download(
        self, download_id: int, delete_files: bool = True, *, expected_plan: str | None = None,
    ) -> DeleteResult:
        return self._deletion().apply(
            self._positive_id(download_id), self._delete_mode(delete_files), expected_plan
        )

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
