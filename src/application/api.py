from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from src.application import history_queries
from src.application.command_api import (
    AddDownloadResult,
    CancelPreview,
    CancelResult,
    CommandError,
    DeletePreview,
    DeleteResult,
    DownloadCommandAPI,
)
from src.application.download_coordinator import DownloadCoordinator
from src.application.dto import (
    DescriptionResultDTO,
    DownloadDetailsDTO,
    DownloadSummaryDTO,
    QueryErrorDTO,
    TaskSnapshotDTO,
    TranscriptResultDTO,
)
from src.application.history_semantics import history_entry_matches_query
from src.domain.download_rules import DownloadRuleError, validate_download_id
from src.domain.models import DownloadTask
from src.domain.models.app_settings import AppSettings
from src.domain.models.history_entry import HistoryEntry
from src.domain.protocols import IHistoryRepository

if TYPE_CHECKING:
    from src.application.runtime import ApplicationRuntime


@dataclass(slots=True)
class ApplicationAPI:
    history_repo: IHistoryRepository
    coordinator: DownloadCoordinator | None = None
    runtime: ApplicationRuntime | None = None

    def _command_api(self) -> DownloadCommandAPI:
        if self.runtime is not None:
            self.runtime.require_writable()
        if self.coordinator is None:
            raise CommandError("A live writable owner is required", code="OWNER_REQUIRED")
        return DownloadCommandAPI(
            coordinator=self.coordinator,
            history_repo=self.history_repo,
        )

    def _live_task(self, download_id: int) -> DownloadTask | None:
        # Legacy query-only composition may supply no execution owner at all.
        # Only the real coordinator is authoritative for a live state overlay.
        if isinstance(self.coordinator, DownloadCoordinator):
            return self.coordinator.get_task(download_id)
        return None

    def list_downloads(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[DownloadSummaryDTO]:
        projection = self._history_projection()
        if status:
            projection = [item for item in projection if item[0].status.value == status]
        return [
            self._annotate(history_queries._summary_dto(entry), entry, task)
            for entry, task in projection[: max(1, min(limit, 200))]
        ]

    @staticmethod
    def _query_id_error(download_id: int) -> QueryErrorDTO | None:
        try:
            validate_download_id(download_id)
        except DownloadRuleError as exc:
            return QueryErrorDTO(str(exc), exc.hint, code="INVALID_ARGUMENT")
        return None

    def get_download(self, download_id: int) -> DownloadDetailsDTO | QueryErrorDTO:
        error = self._query_id_error(download_id)
        if error is not None:
            return error
        entry = self.history_repo.get_by_id(download_id)
        if entry is None:
            return QueryErrorDTO(
                f"Download #{download_id} not found",
                "Use list_downloads() to see valid IDs",
                code="NOT_FOUND",
            )
        task = self._live_task(download_id)
        if task is not None:
            entry = DownloadCoordinator.project(entry, task)
        return replace(
            history_queries._details_dto(entry),
            cancel_requested=task.cancel_requested if task else None,
            result_persisted=task.result_persisted if task else None,
            error_code=entry.error_code,
            artifact_paths=(
                [str(p) for p in entry.artifact_paths]
                if task is not None or entry.artifact_paths or entry.error_code
                else None
            ),
        )

    def search_downloads(
        self,
        query: str,
        limit: int = 20,
        *,
        with_description: bool = False,
    ) -> list[DownloadSummaryDTO]:
        results = []
        for entry, task in self._history_projection(query)[
            : max(1, min(limit, 30 if with_description else 100))
        ]:
            dto = history_queries._summary_dto(
                entry,
                description_path=str(entry.description_path)
                if with_description and entry.description_path
                else None,
                description_text=history_queries._load_description_text(entry, max_bytes=8192)
                if with_description
                else None,
            )
            results.append(self._annotate(dto, entry, task))
        return results

    def get_file_paths(self, download_id: int) -> DownloadDetailsDTO | QueryErrorDTO:
        error = self._query_id_error(download_id)
        if error is not None:
            return error
        return self.get_download(download_id)

    def get_transcript(
        self,
        download_id: int,
        *,
        lang: str | None = None,
        raw: bool = False,
        timestamps: bool = False,
    ) -> TranscriptResultDTO | QueryErrorDTO:
        error = self._query_id_error(download_id)
        if error is not None:
            return error
        return history_queries.get_transcript(
            self.history_repo,
            download_id,
            lang=lang,
            raw=raw,
            timestamps=timestamps,
        )

    def read_description(self, download_id: int) -> DescriptionResultDTO | QueryErrorDTO:
        error = self._query_id_error(download_id)
        if error is not None:
            return error
        return history_queries.read_description(self.history_repo, download_id)

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
        return self._command_api().queue_add_download(
            url=url,
            quality=quality,
            download_type=download_type,
            subtitle_lang=subtitle_lang,
            save_subtitles=save_subtitles,
            save_description=save_description,
            save_thumbnail=save_thumbnail,
        )

    def prepare_cancel_download(self, download_id: int) -> CancelPreview:
        return self._command_api().prepare_cancel_download(download_id)

    def cancel_download(self, download_id: int) -> CancelResult:
        return self._command_api().cancel_download(download_id)

    def prepare_delete_download(
        self, download_id: int, *, delete_files: bool = True
    ) -> DeletePreview:
        return self._command_api().prepare_delete_download(download_id, delete_files=delete_files)

    def delete_download(self, download_id: int, *, delete_files: bool = True) -> DeleteResult:
        return self._command_api().delete_download(download_id, delete_files=delete_files)

    def _history_projection(
        self,
        query: str | None = None,
    ) -> list[tuple[HistoryEntry, DownloadTask | None]]:
        projection = []
        for entry in self.history_repo.get_all():
            task = self._live_task(entry.id)
            if task is not None:
                entry = DownloadCoordinator.project(entry, task)
            if not query or history_entry_matches_query(entry, query):
                projection.append((entry, task))
        return projection

    def list_history_entries(self, query: str | None = None) -> list[HistoryEntry]:
        return [entry for entry, _ in self._history_projection(query)]

    def _annotate(
        self,
        dto: DownloadSummaryDTO,
        entry: HistoryEntry,
        task: DownloadTask | None,
    ) -> DownloadSummaryDTO:
        # Use the same detached facts that were selected, never a post-filter live reread.
        return replace(
            dto,
            status=entry.status.value,
            title=entry.title,
            playlist_title=entry.playlist_title,
            is_playlist=bool(entry.playlist_title),
            finished_at=entry.finished_at.isoformat() if entry.finished_at else None,
            error_message=entry.error_message,
            cancel_requested=task.cancel_requested if task else None,
            result_persisted=task.result_persisted if task else None,
            error_code=entry.error_code,
            artifact_paths=(
                [str(p) for p in entry.artifact_paths]
                if task is not None or entry.artifact_paths or entry.error_code
                else None
            ),
        )

    @staticmethod
    def _task_snapshot(task: DownloadTask) -> TaskSnapshotDTO:
        return TaskSnapshotDTO(
            task.id,
            task.url,
            task.title,
            task.playlist_title,
            task.status.value,
            task.measured_progress,
            task.measured_speed,
            task.measured_eta,
            task.cancel_requested,
            task.result_persisted,
            [str(p) for p in task.artifact_paths],
            task.error_code,
            task.error_message,
        )

    def get_task(self, download_id: int) -> TaskSnapshotDTO | QueryErrorDTO:
        error = self._query_id_error(download_id)
        if error is not None:
            return error
        if not isinstance(self.coordinator, DownloadCoordinator):
            return QueryErrorDTO("A live owner is required", code="OWNER_REQUIRED")
        task = self.coordinator.get_task(download_id)
        if task is None:
            code = "OWNER_REQUIRED" if self.history_repo.get_by_id(download_id) else "NOT_FOUND"
            return QueryErrorDTO("Live task not found", code=code)
        return self._task_snapshot(task)

    def list_tasks(self) -> list[TaskSnapshotDTO]:
        return (
            [self._task_snapshot(task) for task in self.coordinator.get_tasks()]
            if isinstance(self.coordinator, DownloadCoordinator)
            else []
        )

    def wait_for_download(self, download_id: int, timeout: float | None = None) -> TaskSnapshotDTO:
        try:
            validate_download_id(download_id)
        except DownloadRuleError as exc:
            raise CommandError(str(exc), code="INVALID_ARGUMENT") from None
        if not isinstance(self.coordinator, DownloadCoordinator):
            raise CommandError("A live owner is required", code="OWNER_REQUIRED")
        return self._task_snapshot(self.coordinator.wait(download_id, timeout))

    def get_settings(self) -> AppSettings:
        if self.runtime is None:
            raise CommandError("A settings owner is required", code="OWNER_REQUIRED")
        return self.runtime.get_settings()

    def update_settings(self, settings: AppSettings) -> AppSettings:
        if self.runtime is None:
            raise CommandError("A settings owner is required", code="OWNER_REQUIRED")
        return self.runtime.update_settings(settings)


def build_application_api(services: dict[str, Any]) -> ApplicationAPI:
    existing = services.get("application_api")
    if isinstance(existing, ApplicationAPI):
        return existing
    return ApplicationAPI(
        history_repo=services["history_repo"],
        coordinator=services.get("coordinator"),
        runtime=services.get("runtime"),
    )
