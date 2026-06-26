from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from src.application.command_api import (
    ConflictError,
    DownloadCommandAPI,
    NotFoundError,
    ValidationError,
)
from src.domain.models.download_task import DownloadStatus, DownloadTask
from src.domain.models.history_entry import HistoryEntry
from src.infrastructure.repositories import JsonHistoryRepository
from src.interfaces.cli import main as cli_main
from src.ui.managers.history_manager import HistoryManager


class StubCoordinator:
    def __init__(self) -> None:
        self.add_calls: list[dict] = []
        self.cancel_calls: list[int] = []
        self.cancel_return_value = True
        self.tasks: dict[int, DownloadTask] = {}

    def add(self, **kwargs):  # type: ignore[no-untyped-def]
        self.add_calls.append(kwargs)
        return 17

    def get_task(self, task_id: int) -> DownloadTask | None:
        return self.tasks.get(task_id)

    def cancel(self, task_id: int) -> bool:
        self.cancel_calls.append(task_id)
        return self.cancel_return_value


class StubEventBus:
    def subscribe(self, *_args, **_kwargs) -> None:
        return None

    def unsubscribe(self, *_args, **_kwargs) -> None:
        return None


def make_command_api(
    tmp_path: Path,
) -> tuple[DownloadCommandAPI, StubCoordinator, JsonHistoryRepository]:
    coordinator = StubCoordinator()
    repo = JsonHistoryRepository(tmp_path)
    return DownloadCommandAPI(coordinator=coordinator, history_repo=repo), coordinator, repo


def test_queue_add_normalizes_audio_quality(tmp_path: Path) -> None:
    api, coordinator, _repo = make_command_api(tmp_path)

    result = api.queue_add_download(
        url=" https://youtu.be/example ",
        quality="audio",
        download_type="video",
        save_thumbnail=True,
    )

    assert result.task_id == 17
    assert result.status == "queued"
    assert coordinator.add_calls[0]["url"] == "https://youtu.be/example"
    assert coordinator.add_calls[0]["quality"].value == "best"
    assert coordinator.add_calls[0]["download_type"].value == "audio"
    assert coordinator.add_calls[0]["save_thumbnail"] is True


@pytest.mark.parametrize("url, quality, download_type", [
    ("notaurl", "720p", "video"),
    ("https://youtu.be/x", "144p", "video"),
    ("https://youtu.be/x", "720p", "torrent"),
])
def test_queue_add_validation_errors(
    tmp_path: Path,
    url: str,
    quality: str,
    download_type: str,
) -> None:
    api, _coordinator, _repo = make_command_api(tmp_path)

    with pytest.raises(ValidationError):
        api.queue_add_download(url=url, quality=quality, download_type=download_type)


def test_prepare_cancel_and_cancel_success(tmp_path: Path) -> None:
    api, coordinator, _repo = make_command_api(tmp_path)
    coordinator.tasks[5] = DownloadTask(id=5, url="https://youtu.be/x", title="Example")

    preview = api.prepare_cancel_download(5)
    result = api.cancel_download(5)

    assert preview.id == 5
    assert preview.title == "Example"
    assert preview.current_status == DownloadStatus.QUEUED.value
    assert result.status == "cancel_requested"
    assert coordinator.cancel_calls == [5]


def test_cancel_rejects_terminal_status(tmp_path: Path) -> None:
    api, coordinator, _repo = make_command_api(tmp_path)
    coordinator.tasks[9] = DownloadTask(
        id=9,
        url="https://youtu.be/x",
        status=DownloadStatus.DONE,
    )

    with pytest.raises(ConflictError):
        api.prepare_cancel_download(9)


def test_cancel_missing_download(tmp_path: Path) -> None:
    api, _coordinator, _repo = make_command_api(tmp_path)

    with pytest.raises(NotFoundError):
        api.prepare_cancel_download(99)


def test_delete_preview_and_confirm_cleanup(tmp_path: Path) -> None:
    api, _coordinator, repo = make_command_api(tmp_path)
    output_dir = tmp_path / "download-1"
    output_dir.mkdir()
    (output_dir / "video.mp4").write_text("video", encoding="utf-8")
    (output_dir / "meta.txt").write_text("meta", encoding="utf-8")

    entry = HistoryEntry(
        id=1,
        url="https://youtu.be/x",
        title="Clip",
        status=DownloadStatus.DONE,
        output_dir=output_dir,
    )
    repo.add(entry)

    preview = api.prepare_delete_download(1, delete_files=True)
    result = api.delete_download(1, delete_files=True)

    assert preview.output_dir == str(output_dir)
    assert preview.file_count == 2
    assert result.deleted is True
    assert result.files_removed is True
    assert not output_dir.exists()
    assert repo.get_by_id(1) is None


def test_delete_keep_files_only_removes_history(tmp_path: Path) -> None:
    api, _coordinator, repo = make_command_api(tmp_path)
    output_dir = tmp_path / "download-2"
    output_dir.mkdir()
    (output_dir / "audio.m4a").write_text("audio", encoding="utf-8")

    entry = HistoryEntry(
        id=2,
        url="https://youtu.be/y",
        title="Audio",
        status=DownloadStatus.DONE,
        output_dir=output_dir,
    )
    repo.add(entry)

    result = api.delete_download(2, delete_files=False)

    assert result.deleted is True
    assert result.files_removed is False
    assert output_dir.exists()
    assert repo.get_by_id(2) is None


def test_history_manager_delete_uses_shared_command_api(tmp_path: Path) -> None:
    api, _coordinator, repo = make_command_api(tmp_path)
    output_dir = tmp_path / "download-4"
    output_dir.mkdir()
    (output_dir / "clip.mp4").write_text("clip", encoding="utf-8")
    repo.add(
        HistoryEntry(
            id=4,
            url="https://youtu.be/gui-delete",
            title="GUI delete",
            status=DownloadStatus.DONE,
            output_dir=output_dir,
        )
    )
    manager = HistoryManager(repo, cast(Any, StubEventBus()), command_api=api)

    result = manager.delete(4, delete_files=True)

    assert result is not None
    assert result.deleted is True
    assert result.files_removed is True
    assert repo.get_by_id(4) is None
    assert not output_dir.exists()


def test_cli_help_smoke() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.interfaces.cli", "queue", "add", "--help"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--quality" in result.stdout
    assert "--subtitle-lang" in result.stdout


def test_cli_queue_cancel_preview_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    api, coordinator, _repo = make_command_api(tmp_path)
    coordinator.tasks[12] = DownloadTask(id=12, url="https://youtu.be/z", title="Queued clip")

    exit_code = cli_main(
        ["--json", "queue", "cancel", "12"],
        services={"command_api": api, "application_api": api},
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["confirmation_required"] is True
    assert payload["id"] == 12


def test_cli_history_delete_confirm_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api, _coordinator, repo = make_command_api(tmp_path)
    output_dir = tmp_path / "download-3"
    output_dir.mkdir()
    (output_dir / "thumb.webp").write_text("thumb", encoding="utf-8")
    repo.add(
        HistoryEntry(
            id=3,
            url="https://youtu.be/delete-me",
            title="Delete me",
            status=DownloadStatus.DONE,
            output_dir=output_dir,
        )
    )

    exit_code = cli_main(
        ["--json", "history", "delete", "3", "--confirm"],
        services={"command_api": api, "application_api": api},
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["deleted"] is True
    assert payload["files_removed"] is True
    assert not output_dir.exists()


def test_cli_returns_non_zero_on_validation_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api, _coordinator, _repo = make_command_api(tmp_path)

    exit_code = cli_main(
        ["--json", "queue", "add", "notaurl"],
        services={"command_api": api, "application_api": api},
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert exit_code == 1
    assert payload["error"] == "Invalid URL"
