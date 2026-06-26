from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.application.api import ApplicationAPI
from src.domain.models import HistoryEntry
from src.domain.models.app_settings import DownloadType, QualityOption
from src.domain.models.download_task import DownloadStatus
from src.infrastructure.repositories import JsonHistoryRepository
from src.interfaces.cli import main as run_cli


@pytest.fixture
def history_api(tmp_path: Path) -> ApplicationAPI:
    repo = JsonHistoryRepository(tmp_path)

    download_dir = tmp_path / "python-video"
    download_dir.mkdir()
    video_path = download_dir / "python-video.mp4"
    video_path.write_text("video", encoding="utf-8")
    audio_path = download_dir / "python-video.m4a"
    audio_path.write_text("audio", encoding="utf-8")
    subtitle_path = download_dir / "python-video.ru.vtt"
    subtitle_path.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:03.000\n"
        "Привет\n\n"
        "00:00:03.500 --> 00:00:06.000\n"
        "<i>Мир</i>\n",
        encoding="utf-8",
    )
    description_path = download_dir / "python-video.description"
    description_path.write_text("Подробное описание курса Python", encoding="utf-8")
    thumbnail_path = download_dir / "python-video.webp"
    thumbnail_path.write_text("thumb", encoding="utf-8")
    info_json_path = download_dir / "python-video.info.json"
    info_json_path.write_text("{}", encoding="utf-8")

    repo.add(
        HistoryEntry(
            id=1,
            url="https://example.com/python",
            title="Python tutorial",
            playlist_title="",
            quality=QualityOption.P720,
            download_type=DownloadType.VIDEO,
            status=DownloadStatus.DONE,
            video_path=video_path,
            audio_path=audio_path,
            subtitle_paths=[subtitle_path],
            description_path=description_path,
            thumbnail_path=thumbnail_path,
            info_json_path=info_json_path,
            output_dir=download_dir,
        )
    )
    repo.add(
        HistoryEntry(
            id=2,
            url="https://example.com/failed",
            title="Broken download",
            playlist_title="",
            quality=QualityOption.BEST,
            download_type=DownloadType.VIDEO,
            status=DownloadStatus.FAILED,
            error_message="boom",
        )
    )

    return ApplicationAPI(history_repo=repo)


def test_history_query_search_with_description(history_api: ApplicationAPI) -> None:
    results = history_api.search_downloads("python", with_description=True)
    assert len(results) == 1
    assert results[0].title == "Python tutorial"
    assert "Python" in (results[0].description_text or "")
    assert (results[0].description_path or "").endswith("python-video.description")


def test_history_query_transcript_with_timestamps(history_api: ApplicationAPI) -> None:
    result = history_api.get_transcript(1, lang="ru", timestamps=True)
    assert result.lang_detected == "ru"
    assert result.available_langs == ["ru"]
    assert result.transcript_text == "[00:00:01] Привет\n[00:00:03] Мир"


def test_history_query_file_paths(history_api: ApplicationAPI) -> None:
    result = history_api.get_file_paths(1)
    assert (result.video_path or "").endswith("python-video.mp4")
    assert (result.audio_path or "").endswith("python-video.m4a")
    assert result.subtitle_paths == [str(Path(result.subtitle_paths[0]))]
    assert (result.output_dir or "").endswith("python-video")


def test_cli_history_list_json(
    history_api: ApplicationAPI,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_cli(
        ["history", "list", "--format", "json"],
        services={"application_api": history_api},
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert [item["id"] for item in payload] == [2, 1]
    assert captured.err == ""


def test_cli_history_search_table_with_description(
    history_api: ApplicationAPI,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_cli(
        ["history", "search", "python", "--with-description", "--format", "table"],
        services={"application_api": history_api},
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    output = captured.out
    assert "DESCRIPTION" in output
    assert "Python tutorial" in output
    assert captured.err == ""


def test_cli_history_get_missing_id_returns_nonzero(
    history_api: ApplicationAPI,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_cli(["history", "get", "404"], services={"application_api": history_api})
    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Download #404 not found" in captured.err
