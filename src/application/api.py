from __future__ import annotations

from dataclasses import dataclass
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
    TranscriptResultDTO,
)
from src.domain.download_rules import DownloadRuleError, validate_download_id
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

    def list_downloads(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[DownloadSummaryDTO]:
        return history_queries.list_downloads(self.history_repo, status=status, limit=limit)

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
        return history_queries.get_download(self.history_repo, download_id)

    def search_downloads(
        self,
        query: str,
        limit: int = 20,
        *,
        with_description: bool = False,
    ) -> list[DownloadSummaryDTO]:
        return history_queries.search_downloads(
            self.history_repo,
            query,
            limit=limit,
            with_description=with_description,
        )

    def get_file_paths(self, download_id: int) -> DownloadDetailsDTO | QueryErrorDTO:
        error = self._query_id_error(download_id)
        if error is not None:
            return error
        return history_queries.get_file_paths(self.history_repo, download_id)

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

    def list_history_entries(self, query: str | None = None) -> list[HistoryEntry]:
        return self.history_repo.search(query) if query else self.history_repo.get_all()

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
