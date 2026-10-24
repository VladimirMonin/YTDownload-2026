from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from src.application.command_api import (
    CommandError,
    ConflictError,
    DownloadCommandAPI,
    NotFoundError,
    ValidationError,
)
from src.bootstrap import create_runtime
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
    trash = tmp_path / "synthetic-trash"
    trash.mkdir()
    class Remover:
        def move_to_trash(self, path):
            path.rename(trash / path.name)
            return True
        def close(self):
            pass
    runtime = create_runtime(
        tmp_path / "profile", settings_overrides={"output_dir": tmp_path / "output"},
        file_remover_factory=Remover,
    )
    try:
        api, repo = runtime.api, runtime.history_repo
        output_dir = tmp_path / "output/download-1"
        output_dir.mkdir(parents=True)
        video, meta = output_dir / "video.mp4", output_dir / "meta.txt"
        video.write_text("video", encoding="utf-8")
        meta.write_text("meta", encoding="utf-8")
        entry = HistoryEntry(
            id=1, url="https://youtu.be/x", title="Clip", status=DownloadStatus.DONE,
            output_root=tmp_path / "output", output_dir=output_dir,
            video_path=video, artifact_paths=[video, meta],
        )
        repo.add(entry)
        preview = api.prepare_delete_download(1, delete_files=True)
        result = api.delete_download(1, delete_files=True, expected_plan=preview.plan_token)
        assert preview.output_dir == str(output_dir)
        assert preview.file_count == 2
        assert result.deleted is True
        assert result.files_removed is True
        assert output_dir.is_dir()  # S4 deliberately preserves directories, not recursive cleanup.
        assert not video.exists() and not meta.exists()
        assert (trash / "video.mp4").read_text(encoding="utf-8") == "video"
        assert (trash / "meta.txt").read_text(encoding="utf-8") == "meta"
        assert repo.get_by_id(1) is None
        with create_runtime(runtime.data_root, read_only=True) as reader:
            assert reader.api.list_history_entries() == []
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_delete_keep_files_only_removes_history(tmp_path: Path) -> None:
    runtime = create_runtime(
        tmp_path / "profile", settings_overrides={"output_dir": tmp_path / "output"}
    )
    try:
        api, repo = runtime.api, runtime.history_repo
        output_dir = tmp_path / "output/download-2"
        output_dir.mkdir(parents=True)
        (output_dir / "audio.m4a").write_text("audio", encoding="utf-8")
        entry = HistoryEntry(
            id=2, url="https://youtu.be/y", title="Audio", status=DownloadStatus.DONE,
            output_dir=output_dir,
        )
        repo.add(entry)
        preview = api.prepare_delete_download(2, delete_files=False)
        result = api.delete_download(2, delete_files=False, expected_plan=preview.plan_token)
        assert result.deleted is True
        assert result.files_removed is False
        assert output_dir.exists()
        assert (output_dir / "audio.m4a").read_text(encoding="utf-8") == "audio"
        assert repo.get_by_id(2) is None
        with create_runtime(runtime.data_root, read_only=True) as reader:
            assert reader.api.list_history_entries() == []
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_history_manager_delete_uses_shared_command_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, coordinator, repo = make_command_api(tmp_path)
    output_dir = tmp_path / "download-4"
    output_dir.mkdir()
    media = output_dir / "clip.mp4"
    media.write_bytes(b"clip")
    unlisted, sibling, parent_marker = (
        output_dir / "unlisted.keep", tmp_path / "sibling.keep", tmp_path / "parent.keep"
    )
    unlisted.write_bytes(b"unlisted preserve")
    sibling.write_bytes(b"sibling preserve")
    parent_marker.write_bytes(b"parent preserve")
    repo.add(
        HistoryEntry(
            id=4,
            url="https://youtu.be/gui-delete",
            title="GUI delete",
            status=DownloadStatus.DONE,
            output_dir=output_dir,
        )
    )
    cache_before = repo.get_all()
    files = (media, unlisted, sibling, parent_marker, tmp_path / "history.json")
    bytes_before = {path: path.read_bytes() for path in files}
    real_delete = api.delete_download
    calls: list[tuple[int, bool, str | None]] = []

    def observe_delete(
        download_id: int, delete_files: bool = True, *, expected_plan: str | None = None,
    ) -> Any:
        calls.append((download_id, delete_files, expected_plan))
        return real_delete(download_id, delete_files=delete_files, expected_plan=expected_plan)

    monkeypatch.setattr(api, "delete_download", observe_delete)
    manager = HistoryManager(repo, cast(Any, StubEventBus()), command_api=api)
    with pytest.raises(CommandError) as denied:
        manager.delete(4, delete_files=True)

    assert calls == [(4, True, None)]  # Actual shared API, not the legacy repo fallback.
    assert denied.value.code == "CONFIRMATION_REQUIRED"
    assert denied.value.result is None
    assert coordinator.add_calls == [] and coordinator.cancel_calls == []
    assert repo.get_all() == cache_before
    assert repo.get_by_id(4) == cache_before[0]
    assert {path: path.read_bytes() for path in files} == bytes_before
    reopened = JsonHistoryRepository(tmp_path, read_only=True)
    assert reopened.get_all() == cache_before and reopened.get_by_id(4) == cache_before[0]
    assert output_dir.is_dir() and output_dir.parent.is_dir()


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, coordinator, repo = make_command_api(tmp_path)
    output_dir = tmp_path / "download-3"
    output_dir.mkdir()
    media = output_dir / "thumb.webp"
    media.write_bytes(b"thumb")
    unlisted, sibling, parent_marker = (
        output_dir / "unlisted.keep", tmp_path / "sibling.keep", tmp_path / "parent.keep"
    )
    unlisted.write_bytes(b"unlisted preserve")
    sibling.write_bytes(b"sibling preserve")
    parent_marker.write_bytes(b"parent preserve")
    repo.add(
        HistoryEntry(
            id=3,
            url="https://youtu.be/delete-me",
            title="Delete me",
            status=DownloadStatus.DONE,
            output_dir=output_dir,
        )
    )
    cache_before = repo.get_all()
    files = (media, unlisted, sibling, parent_marker, tmp_path / "history.json")
    bytes_before = {path: path.read_bytes() for path in files}
    real_delete = api.delete_download
    calls: list[tuple[int, bool, str | None]] = []
    failures: list[CommandError] = []

    def observe_delete(
        download_id: int, delete_files: bool = True, *, expected_plan: str | None = None,
    ) -> Any:
        calls.append((download_id, delete_files, expected_plan))
        try:
            return real_delete(download_id, delete_files=delete_files, expected_plan=expected_plan)
        except CommandError as error:
            failures.append(error)
            raise

    monkeypatch.setattr(api, "delete_download", observe_delete)
    root = logging.getLogger()
    previous_handlers, previous_level = root.handlers[:], root.level
    previous_yt_level = logging.getLogger("yt_dlp").level
    root.handlers = []  # Preserve borrowed pytest/caller handlers across real CLI setup_logging.
    try:
        exit_code = cli_main(
            ["--json", "history", "delete", "3", "--confirm"],
            services={"command_api": api, "application_api": api},
        )
        captured = capsys.readouterr()
        assert calls == [(3, True, None)]
        assert len(failures) == 1 and failures[0].code == "CONFIRMATION_REQUIRED"
        assert failures[0].result is None
        assert exit_code == 1 and captured.out == ""
        assert captured.err.strip()
        payload = json.loads(captured.err)
        assert payload == {
            "error": failures[0].message, "hint": failures[0].hint,
            "code": "CONFIRMATION_REQUIRED",
        }
        assert not {"deleted", "files_removed"} & payload.keys()
        for sensitive in ("https://youtu.be/delete-me", "Delete me", str(tmp_path), media.name):
            assert sensitive not in captured.err
        assert coordinator.add_calls == [] and coordinator.cancel_calls == []
        assert repo.get_all() == cache_before and repo.get_by_id(3) == cache_before[0]
        assert {path: path.read_bytes() for path in files} == bytes_before
        reopened = JsonHistoryRepository(tmp_path, read_only=True)
        assert reopened.get_all() == cache_before and reopened.get_by_id(3) == cache_before[0]
        assert output_dir.is_dir() and output_dir.parent.is_dir()
    finally:
        for handler in root.handlers:
            handler.flush()
            handler.close()
        root.handlers = previous_handlers
        root.setLevel(previous_level)
        logging.getLogger("yt_dlp").setLevel(previous_yt_level)


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
