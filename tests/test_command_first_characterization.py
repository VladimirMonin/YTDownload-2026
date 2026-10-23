"""S1 normal-path baseline through the existing owners, before runtime migration.

Cancellation defects are deliberately not frozen as desired behavior here.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.application.api import ApplicationAPI
from src.application.download_coordinator import DownloadCoordinator
from src.application.dto import serialize_for_transport
from src.core.event_bus import EventBus
from src.domain.models.app_settings import AppSettings, DownloadType, QualityOption
from src.domain.models.download_task import DownloadStatus
from src.domain.models.history_entry import HistoryEntry
from src.infrastructure.repositories import JsonHistoryRepository, JsonSettingsRepository


@pytest.fixture
def history_api(tmp_path: Path) -> ApplicationAPI:
    repo = JsonHistoryRepository(tmp_path / "data")
    description = tmp_path / "sample.description"
    description.write_text("Distinctive description — описание", encoding="utf-8")
    for entry_id in range(1, 56):
        repo.add(
            HistoryEntry(
                id=entry_id,
                url=f"https://example.invalid/item/{entry_id}",
                title=f"Synthetic video {entry_id}",
                playlist_title="Distinctive series" if entry_id == 55 else "",
                quality=QualityOption.P720,
                download_type=DownloadType.VIDEO,
                status=DownloadStatus.FAILED if entry_id == 54 else DownloadStatus.DONE,
                description_path=description if entry_id == 55 else None,
                created_at=datetime(2026, 1, 2, 3, 4, 5),
            )
        )
    # Read through a fresh real repository, not the writer's mutable cache.
    return ApplicationAPI(JsonHistoryRepository(tmp_path / "data"))


def test_query_defaults_order_filter_and_wire_shape(history_api: ApplicationAPI) -> None:
    payload = json.loads(json.dumps(serialize_for_transport(history_api.list_downloads())))
    assert len(payload) == 50
    assert [item["id"] for item in payload] == list(range(55, 5, -1))
    assert payload[0] == {
        "id": 55,
        "url": "https://example.invalid/item/55",
        "title": "Synthetic video 55",
        "playlist_title": "Distinctive series",
        "is_playlist": True,
        "status": "done",
        "quality": "720p",
        "download_type": "video",
        "created_at": "2026-01-02T03:04:05",
        "finished_at": None,
        "error_message": "",
        "description_path": None,
        "description_text": None,
    }
    assert [item.id for item in history_api.list_downloads(limit=0)] == [55]
    assert [item.id for item in history_api.list_downloads(status="failed")] == [54]
    assert history_api.list_downloads(status="unknown") == []
    assert len(history_api.search_downloads("   ")) == 20
    assert [item.id for item in history_api.search_downloads("SERIES", limit=0)] == [55]
    assert [item.id for item in history_api.search_downloads("/ITEM/54")] == [54]


def test_description_query_uses_real_sidecar_and_transport(history_api: ApplicationAPI) -> None:
    matches = history_api.search_downloads("series", with_description=True)
    payload = json.loads(json.dumps(serialize_for_transport(matches)))
    assert len(payload) == 1
    assert payload[0]["id"] == 55
    assert payload[0]["description_path"].endswith("sample.description")
    assert payload[0]["description_text"] == "Distinctive description — описание"
    description = serialize_for_transport(history_api.read_description(55))
    assert description["description_text"] == "Distinctive description — описание"
    assert description["truncated"] is False
    assert description["hint"] is None


def test_gui_settings_defaults_and_json_roundtrip(tmp_path: Path) -> None:
    repo = JsonSettingsRepository(tmp_path / "config")
    defaults = repo.load()
    assert defaults.to_dict() == {
        "output_dir": str(Path.home() / "Downloads" / "YTDownloader"),
        "proxy": "",
        "quality": "best",
        "download_type": "video",
        "subtitle_lang": "ru",
        "save_subtitles": True,
        "save_description": True,
        "save_thumbnail": True,
        "max_concurrent": 2,
        "mcp_port": 8765,
        "theme": "dark",
    }
    defaults.output_dir = tmp_path / "output"
    defaults.save_description = False
    defaults.quality = QualityOption.P480
    defaults.theme = "light"
    repo.save(defaults)
    reopened = JsonSettingsRepository(tmp_path / "config").load()
    assert reopened.to_dict() == defaults.to_dict()
    assert AppSettings.from_dict(reopened.to_dict()).to_dict() == defaults.to_dict()


@pytest.mark.parametrize("consumer", ["api", "gui-owner"])
def test_add_defaults_reach_real_coordinator_and_history(
    tmp_path: Path, consumer: str
) -> None:
    observed: list[tuple] = []

    class SyntheticBackend:
        def __init__(self, **kwargs):
            pass

        def fetch_info(self, url, settings):
            return SimpleNamespace(title="Synthetic result", playlist_title="", is_playlist=False)

        def download(self, task, settings, callback):
            observed.append(
                (task.quality, task.download_type, task.subtitle_lang,
                 task.save_subtitles, task.save_description, task.save_thumbnail)
            )
            settings.output_dir.mkdir(parents=True, exist_ok=True)
            media = settings.output_dir / "synthetic.mp4"
            media.write_bytes(b"synthetic boundary artifact, not playable media")
            return {"video": media, "audio": None, "subtitles": []}

    # Only the external backend is replaced; API, coordinator and JSON are real.
    repo = JsonHistoryRepository(tmp_path / "data")
    coordinator = DownloadCoordinator(
        repo, AppSettings(output_dir=tmp_path / "output"), EventBus(),
        service_factory=SyntheticBackend,
    )
    api = ApplicationAPI(repo, coordinator)
    try:
        if consumer == "api":
            result = api.queue_add_download(url=" https://example.invalid/synthetic ")
            assert serialize_for_transport(result) == {"task_id": 1, "status": "queued"}
            task_id = result.task_id
        else:
            # Current GUI delegates to this owner with settings-derived options.
            task_id = coordinator.add(url="https://example.invalid/synthetic")
    finally:
        # Legacy shutdown(wait=False) is not a join; S3 will supply public lifecycle.
        coordinator._executor.shutdown(wait=True)

    expected_quality = QualityOption.P720 if consumer == "api" else QualityOption.BEST
    expected_flag = consumer == "gui-owner"
    assert observed == [
        (expected_quality, DownloadType.VIDEO, "ru", expected_flag, expected_flag, expected_flag)
    ]
    reopened = ApplicationAPI(JsonHistoryRepository(tmp_path / "data"))
    saved = serialize_for_transport(reopened.get_download(task_id))
    assert saved["status"] == "done"
    assert saved["quality"] == expected_quality.value
    assert saved["url"] == "https://example.invalid/synthetic"
    assert Path(saved["video_path"]).read_bytes() == (
        b"synthetic boundary artifact, not playable media"
    )
