from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.application import history_queries
from src.application.command_api import DownloadCommandAPI
from src.application.download_coordinator import DownloadCoordinator
from src.application.dto import (
    DescriptionResultDTO,
    DownloadDetailsDTO,
    DownloadSummaryDTO,
    QueryErrorDTO,
    TranscriptResultDTO,
)
from src.domain.protocols import IHistoryRepository


@dataclass(slots=True)
class ApplicationAPI:
    history_repo: IHistoryRepository
    coordinator: DownloadCoordinator | None = None

    def _command_api(self) -> DownloadCommandAPI:
        if self.coordinator is None:
            raise RuntimeError("Command API requires an initialized coordinator")
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

    def get_download(self, download_id: int) -> DownloadDetailsDTO | QueryErrorDTO:
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
        return history_queries.get_file_paths(self.history_repo, download_id)

    def get_transcript(
        self,
        download_id: int,
        *,
        lang: str | None = None,
        raw: bool = False,
        timestamps: bool = False,
    ) -> TranscriptResultDTO | QueryErrorDTO:
        return history_queries.get_transcript(
            self.history_repo,
            download_id,
            lang=lang,
            raw=raw,
            timestamps=timestamps,
        )

    def read_description(self, download_id: int) -> DescriptionResultDTO | QueryErrorDTO:
        return history_queries.read_description(self.history_repo, download_id)

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
    ) -> Any:
        return self._command_api().queue_add_download(
            url=url,
            quality=quality,
            download_type=download_type,
            subtitle_lang=subtitle_lang,
            save_subtitles=save_subtitles,
            save_description=save_description,
            save_thumbnail=save_thumbnail,
        )

    def prepare_cancel_download(self, download_id: int) -> Any:
        return self._command_api().prepare_cancel_download(download_id)

    def cancel_download(self, download_id: int) -> Any:
        return self._command_api().cancel_download(download_id)

    def prepare_delete_download(self, download_id: int, *, delete_files: bool = True) -> Any:
        return self._command_api().prepare_delete_download(download_id, delete_files=delete_files)

    def delete_download(self, download_id: int, *, delete_files: bool = True) -> Any:
        return self._command_api().delete_download(download_id, delete_files=delete_files)


def build_application_api(services: dict[str, Any]) -> ApplicationAPI:
    return ApplicationAPI(
        history_repo=services["history_repo"],
        coordinator=services.get("coordinator"),
    )
