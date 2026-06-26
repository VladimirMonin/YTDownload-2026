from __future__ import annotations

from pathlib import Path

from src.application.api import build_application_api
from src.application.dto import (
    DescriptionResultDTO,
    DownloadDetailsDTO,
    DownloadSummaryDTO,
    QueryErrorDTO,
    TranscriptResultDTO,
    serialize_for_transport,
)
from src.domain.models.app_settings import DownloadType, QualityOption
from src.domain.models.download_task import DownloadStatus
from src.domain.models.history_entry import HistoryEntry
from src.infrastructure.mcp.tools._utils import entry_to_dict_full, entry_to_dict_short
from src.infrastructure.repositories import JsonHistoryRepository


def _make_api(tmp_path: Path):
    repo = JsonHistoryRepository(tmp_path)
    services = {
        "history_repo": repo,
        "coordinator": object(),
    }
    return build_application_api(services), repo


def _seed_entry(tmp_path: Path, repo: JsonHistoryRepository) -> HistoryEntry:
    output_dir = tmp_path / "download-1"
    output_dir.mkdir()
    description_path = output_dir / "video.description"
    description_path.write_text("Full description text", encoding="utf-8")
    subtitle_path = output_dir / "video.ru.vtt"
    subtitle_path.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:03.000\n"
        "<i>Привет</i>\n\n"
        "00:00:03.000 --> 00:00:05.000\n"
        "Привет\n"
        "Мир\n",
        encoding="utf-8",
    )
    video_path = output_dir / "video.mp4"
    video_path.write_text("video", encoding="utf-8")

    entry = HistoryEntry(
        id=1,
        url="https://youtu.be/example",
        title="Example title",
        playlist_title="",
        quality=QualityOption.P720,
        download_type=DownloadType.VIDEO,
        status=DownloadStatus.DONE,
        video_path=video_path,
        subtitle_paths=[subtitle_path],
        description_path=description_path,
        output_dir=output_dir,
    )
    repo.add(entry)
    return entry


def test_build_application_api_returns_query_dtos(tmp_path: Path) -> None:
    api, repo = _make_api(tmp_path)
    _seed_entry(tmp_path, repo)

    items = api.list_downloads(limit=5)
    details = api.get_download(1)

    assert len(items) == 1
    assert isinstance(items[0], DownloadSummaryDTO)
    assert isinstance(details, DownloadDetailsDTO)
    assert details.video_path and details.video_path.endswith("video.mp4")


def test_search_with_description_and_transport_serialization(tmp_path: Path) -> None:
    api, repo = _make_api(tmp_path)
    _seed_entry(tmp_path, repo)

    results = api.search_downloads("example", with_description=True)
    payload = serialize_for_transport(results)

    assert isinstance(results[0], DownloadSummaryDTO)
    assert payload[0]["description_text"] == "Full description text"
    assert payload[0]["description_path"].endswith("video.description")


def test_search_matches_playlist_title_too(tmp_path: Path) -> None:
    api, repo = _make_api(tmp_path)
    repo.add(
        HistoryEntry(
            id=7,
            url="https://youtu.be/playlist-item",
            title="Episode 01",
            playlist_title="Python Backend Course",
            status=DownloadStatus.DONE,
        )
    )

    results = api.search_downloads("backend course")

    assert [item.id for item in results] == [7]


def test_read_description_missing_file_returns_hint_dto(tmp_path: Path) -> None:
    api, repo = _make_api(tmp_path)
    entry = HistoryEntry(
        id=2,
        url="https://youtu.be/missing-description",
        title="Missing description",
        status=DownloadStatus.DONE,
    )
    repo.add(entry)

    result = api.read_description(2)

    assert isinstance(result, DescriptionResultDTO)
    assert result.description_text is None
    assert result.hint is not None


def test_get_transcript_cleanup_and_timestamps(tmp_path: Path) -> None:
    api, repo = _make_api(tmp_path)
    _seed_entry(tmp_path, repo)

    clean_result = api.get_transcript(1)
    timed_result = api.get_transcript(1, timestamps=True)

    assert isinstance(clean_result, TranscriptResultDTO)
    assert clean_result.transcript_text == "Привет\nМир"
    assert isinstance(timed_result, TranscriptResultDTO)
    assert timed_result.transcript_text == "[00:00:01] Привет\n[00:00:03] Мир"


def test_get_file_paths_and_missing_download_errors(tmp_path: Path) -> None:
    api, repo = _make_api(tmp_path)
    entry = _seed_entry(tmp_path, repo)

    file_paths = api.get_file_paths(entry.id)
    missing = api.get_download(999)

    assert isinstance(file_paths, DownloadDetailsDTO)
    assert file_paths.output_dir and file_paths.output_dir.endswith("download-1")
    assert isinstance(missing, QueryErrorDTO)
    assert missing.error == "Download #999 not found"


def test_legacy_mcp_utils_shim_exports_expected_dict_shape(tmp_path: Path) -> None:
    _api, repo = _make_api(tmp_path)
    entry = _seed_entry(tmp_path, repo)

    short_payload = entry_to_dict_short(entry)
    full_payload = entry_to_dict_full(entry)

    assert short_payload["id"] == entry.id
    assert short_payload["status"] == DownloadStatus.DONE.value
    assert "video_path" not in short_payload
    assert full_payload["video_path"] and full_payload["video_path"].endswith("video.mp4")
    assert full_payload["description_path"]
    assert full_payload["description_path"].endswith("video.description")
