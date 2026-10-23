"""S2 connected runtime/lease/persistence proofs. Cancellation schedules belong to S3."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from contextlib import nullcontext
from pathlib import Path

import pytest

from main import initialize_app
from src.application.api import build_application_api
from src.application.command_api import CommandError
from src.application.dto import serialize_for_transport
from src.application.runtime import ApplicationRuntime
from src.bootstrap import create_runtime
from src.domain.models import AppSettings, HistoryEntry, VideoInfo
from src.domain.models.download_task import DownloadStatus
from src.domain.protocols.download_service import IDownloadService
from src.domain.protocols.history_repository import StorageError
from src.infrastructure.repositories import JsonHistoryRepository, JsonSettingsRepository


class BoundaryBackend(IDownloadService):
    def fetch_info(self, url, settings):
        return VideoInfo(title="Distinctive runtime result")

    def download(self, task, settings, progress_callback=None):
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        media = settings.output_dir / f"result-{task.id}.mp4"
        description = settings.output_dir / f"result-{task.id}.description"
        media.write_bytes(f"S2 synthetic artifact {task.id}".encode())
        description.write_text("S2 distinctive description — описание", encoding="utf-8")
        return {"video": media, "subtitles": [], "description": description,
                "scan_root": settings.output_dir}

    def cancel(self):
        pass


class BoundaryRemover:
    def __init__(self):
        self.closes = 0

    def move_to_trash(self, path):
        raise AssertionError("S2 must not introduce a new deletion effect")

    def close(self):
        self.closes += 1


def test_composed_api_defaults_settings_copies_and_real_reopen(tmp_path: Path) -> None:
    observed = []
    remover = BoundaryRemover()

    class ObservedBackend(BoundaryBackend):
        def download(self, task, settings, progress_callback=None):
            observed.append((task.quality.value, task.download_type.value, task.subtitle_lang,
                             task.save_subtitles, task.save_description, task.save_thumbnail))
            return super().download(task, settings, progress_callback)

    root = tmp_path / "profile"
    runtime = create_runtime(
        root, backend_factory=ObservedBackend, file_remover_factory=lambda: remover,
        settings_overrides={"output_dir": str(tmp_path / "output"), "quality": "1080p",
                            "theme": "light", "subtitle_lang": "en"},
    )
    try:
        initial = runtime.api.get_settings()
        initial.theme = "dark"
        assert runtime.api.get_settings().theme == "light"
        saved = runtime.api.update_settings(runtime.api.get_settings())
        saved.theme = "dark"
        assert runtime.api.get_settings().theme == "light"
        result = runtime.api.queue_add_download(
            url=" https://example.invalid/normal ", quality=None, download_type=None,
            save_subtitles=None, save_description=False, save_thumbnail=None,
        )
        assert serialize_for_transport(result) == {"task_id": 1, "status": "queued"}
    finally:
        shutdown = runtime.close(cancel=False, wait=True)
    assert shutdown.closed and not shutdown.error_codes
    assert remover.closes == 1
    assert observed == [("1080p", "video", "en", True, False, True)]
    assert runtime.close(cancel=False).closed
    assert remover.closes == 1
    with pytest.raises(CommandError) as closed:
        runtime.api.queue_add_download(url="https://example.invalid/after-close")
    assert closed.value.code == "RUNTIME_CLOSING"
    history = JsonHistoryRepository(root / "data")
    stored = history.get_by_id(1)
    assert stored.status == DownloadStatus.DONE
    assert stored.output_root == tmp_path / "output"
    assert stored.video_path.read_bytes() == b"S2 synthetic artifact 1"
    assert JsonSettingsRepository(root / "config").load().theme == "light"
    with create_runtime(root, read_only=True) as reader:
        paths = serialize_for_transport(reader.api.get_file_paths(1))
        assert paths["description_path"] == str(stored.description_path)
        assert reader.api.read_description(1).description_text == (
            "S2 distinctive description — описание"
        )
        assert reader.coordinator is None
        entry = reader.api.list_history_entries()[0]
        entry.title = "not an implicit update"
        assert reader.api.list_history_entries()[0].title == "Distinctive runtime result"


@pytest.mark.parametrize("quality_input", [None, " AUDIO "])
def test_local_audio_defaults_and_explicit_input_share_normalization(
    tmp_path: Path, quality_input,
) -> None:
    observed = []

    class AudioBackend(BoundaryBackend):
        def download(self, task, settings, progress_callback=None):
            observed.append((task.quality.value, task.download_type.value))
            settings.output_dir.mkdir(parents=True, exist_ok=True)
            audio = settings.output_dir / "audio.bin"
            audio.write_bytes(b"synthetic audio boundary bytes")
            return {"audio": audio, "subtitles": []}

    runtime = create_runtime(
        tmp_path / "profile", backend_factory=AudioBackend,
        settings_overrides={"output_dir": str(tmp_path / "output"), "quality": "audio"},
    )
    try:
        accepted = runtime.api.queue_add_download(
            url="https://example.invalid/audio", quality=quality_input, download_type=None,
        )
    finally:
        assert runtime.close(cancel=False, wait=True).closed
    assert observed == [("best", "audio")]
    saved = runtime.api.get_file_paths(accepted.task_id)
    assert Path(saved.audio_path).read_bytes() == b"synthetic audio boundary bytes"


def test_invalid_url_without_host_has_no_admission_effect(tmp_path: Path) -> None:
    runtime = create_runtime(
        tmp_path / "profile", backend_factory=BoundaryBackend,
        settings_overrides={"output_dir": str(tmp_path / "output")},
    )
    try:
        with pytest.raises(CommandError) as rejected:
            runtime.api.queue_add_download(url="https://")
        assert rejected.value.code == "INVALID_ARGUMENT"
        assert runtime.api.list_downloads() == []
        assert not (runtime.data_root / "data/history.json").exists()
        accepted = runtime.api.queue_add_download(url="https://example.invalid/next")
        assert accepted.task_id == 1
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_legacy_wrapper_aliases_and_current_smoke_consumer_join(tmp_path: Path) -> None:
    from scripts.smoke_support import close_services

    services = initialize_app(tmp_path / "profile", backend_factory=BoundaryBackend)
    try:
        assert {"coordinator", "history_repo", "settings_repo", "settings", "event_bus",
                "application_api", "command_api", "runtime"} <= services.keys()
        runtime = services["runtime"]
        assert services["application_api"] is services["command_api"] is runtime.api
        assert build_application_api(services) is runtime.api
        close_services(services)  # The existing accepted smoke's real cleanup consumer.
        assert runtime.closed
        with create_runtime(tmp_path / "profile", backend_factory=BoundaryBackend) as next_owner:
            assert next_owner.api.list_downloads() == []
    finally:
        services["runtime"].close(cancel=False, wait=True)


def test_borrowed_runtime_does_not_close_owner_or_its_ports(tmp_path: Path) -> None:
    remover = BoundaryRemover()
    owner = create_runtime(
        tmp_path / "profile", backend_factory=BoundaryBackend,
        file_remover_factory=lambda: remover,
        settings_overrides={"output_dir": str(tmp_path / "output")},
    )
    try:
        borrowed = ApplicationRuntime(
            data_root=owner.data_root, history_repo=owner.history_repo,
            settings_repo=owner.settings_repo, settings=owner.get_settings(),
            event_bus=owner.event_bus, coordinator=owner.coordinator, owns_coordinator=False,
        )
        settings = borrowed.api.get_settings()
        settings.theme = "light"
        borrowed.api.update_settings(settings)
        assert owner.api.get_settings().theme == "light"
        assert borrowed.close().closed
        assert not owner.closed and remover.closes == 0
        with pytest.raises(CommandError):
            borrowed.api.queue_add_download(url="https://example.invalid/closed-wrapper")
        result = owner.api.queue_add_download(url="https://example.invalid/still-owned")
    finally:
        shutdown = owner.close(cancel=False, wait=True)
    assert shutdown.closed and not shutdown.error_codes
    assert remover.closes == 1
    stored = JsonHistoryRepository(owner.data_root / "data").get_by_id(result.task_id)
    assert stored.video_path.exists()


def test_read_only_missing_store_creates_nothing_and_never_calls_effect_factories(
    tmp_path: Path,
) -> None:
    root = tmp_path / "does-not-exist"

    def forbidden():
        raise AssertionError("Read-only queries must not construct effect dependencies")

    with create_runtime(root, read_only=True, backend_factory=forbidden,
                        file_remover_factory=forbidden) as runtime:
        assert runtime.read_only
        assert runtime.coordinator is None
        assert runtime.api.list_downloads() == []
        with pytest.raises(CommandError) as owner_required:
            runtime.api.queue_add_download(url="https://example.invalid/not-admitted")
        assert owner_required.value.code == "OWNER_REQUIRED"
        with pytest.raises(StorageError) as read_only:
            runtime.history_repo.next_id()
        assert read_only.value.code == "OWNER_REQUIRED"
    assert not root.exists()


def test_root_priority_and_empty_environment_do_not_select_cwd(monkeypatch, tmp_path: Path) -> None:
    synthetic_cwd = tmp_path / "cwd"
    synthetic_cwd.mkdir()
    monkeypatch.chdir(synthetic_cwd)
    home, appdata, env_root = tmp_path / "home", tmp_path / "appdata", tmp_path / "env-root"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("YTDL_DATA_DIR", str(env_root))
    with create_runtime(tmp_path / "explicit", read_only=True) as runtime:
        assert runtime.data_root == (tmp_path / "explicit").resolve()
    with create_runtime(read_only=True) as runtime:
        assert runtime.data_root == env_root.resolve()
    monkeypatch.delenv("YTDL_DATA_DIR")
    with create_runtime(read_only=True) as runtime:
        assert runtime.data_root == (appdata / "YTDownloader").resolve()
    monkeypatch.delenv("APPDATA")
    with create_runtime(read_only=True) as runtime:
        assert runtime.data_root == (home / "YTDownloader").resolve()
    monkeypatch.setenv("APPDATA", "")
    monkeypatch.setenv("YTDL_DATA_DIR", "")
    with create_runtime(read_only=True) as runtime:
        assert runtime.data_root == (home / "YTDownloader").resolve()
    assert list(synthetic_cwd.iterdir()) == []
    assert not env_root.exists() and not appdata.exists() and not home.exists()


def test_recovery_is_writable_only_and_keeps_terminal_artifact_bytes(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    repo = JsonHistoryRepository(root / "data")
    media, partial = tmp_path / "existing.mp4", tmp_path / "existing.part"
    media.write_bytes(b"must remain exactly unchanged")
    partial.write_bytes(b"no startup cleanup")
    states = list(DownloadStatus)
    for entry_id, status in enumerate(states, 1):
        repo.add(HistoryEntry(id=entry_id, url=f"https://example.invalid/{entry_id}",
                              status=status, video_path=media))
    path = root / "data/history.json"
    before = path.read_bytes()
    terminal = {e.id: e.to_dict() for e in repo.get_all() if e.status.is_terminal()}
    calls = []

    def forbidden_backend():
        calls.append("backend")
        raise AssertionError("Recovery must not replay work")

    with create_runtime(root, read_only=True, backend_factory=forbidden_backend) as reader:
        assert path.read_bytes() == before
        assert {e.status for e in reader.api.list_history_entries()} == set(states)
        assert not (root / ".writer.lock").exists()
    runtime = create_runtime(root, backend_factory=forbidden_backend)
    try:
        for entry in runtime.api.list_history_entries():
            if entry.id in terminal:
                assert entry.to_dict() == terminal[entry.id]
            else:
                assert entry.status == DownloadStatus.FAILED
                assert entry.error_code == "INTERRUPTED"
                assert entry.finished_at is not None
    finally:
        assert runtime.close(cancel=False).closed
    assert calls == []
    assert media.read_bytes() == b"must remain exactly unchanged"
    assert partial.read_bytes() == b"no startup cleanup"
    assert (root / ".writer.lock").exists()  # Unlock never unlinks the protected file.
    recovered = path.read_bytes()
    with create_runtime(root, read_only=True):
        assert path.read_bytes() == recovered


def _fail_target_replace(monkeypatch, target: Path, *, when_entries: bool | None = None) -> None:
    original = os.replace

    def fault(source, destination):
        if Path(destination) == target:
            candidate = json.loads(Path(source).read_text(encoding="utf-8"))
            if when_entries is None or bool(candidate.get("entries")) == when_entries:
                raise OSError("S2 synthetic storage-fault sentinel")
        return original(source, destination)

    monkeypatch.setattr(os, "replace", fault)


def test_failed_recovery_releases_startup_owner_and_preserves_original_json(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "profile"
    repo = JsonHistoryRepository(root / "data")
    repo.add(HistoryEntry(id=4, url="https://example.invalid/orphan", status=DownloadStatus.QUEUED))
    target = root / "data/history.json"
    before = target.read_bytes()
    with monkeypatch.context() as fault:
        _fail_target_replace(fault, target)
        with pytest.raises(StorageError) as failed:
            with create_runtime(root, backend_factory=BoundaryBackend):
                pass  # Also close an incorrectly successful RED candidate.
        assert failed.value.code == "PERSISTENCE_FAILED"
        assert target.read_bytes() == before
    with create_runtime(root, backend_factory=BoundaryBackend) as next_owner:
        assert next_owner.api.get_download(4).status == "failed"
        assert next_owner.history_repo.get_by_id(4).error_code == "INTERRUPTED"


@pytest.mark.parametrize("kind", ["history", "settings"])
def test_corrupt_startup_preserves_bytes_and_releases_owner(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "profile"
    if kind == "history":
        repo = JsonHistoryRepository(root / "data")
        repo.add(HistoryEntry(
            id=12, url="https://example.invalid/old", status=DownloadStatus.DONE
        ))
        target = root / "data/history.json"
    else:
        repo = JsonSettingsRepository(root / "config")
        repo.save(AppSettings(output_dir=tmp_path / "output", theme="light"))
        target = root / "config/settings.json"
    original = target.read_bytes()
    damaged = b'{"synthetic-broken":'
    target.write_bytes(damaged)
    with pytest.raises(StorageError) as corrupt:
        with create_runtime(root, backend_factory=BoundaryBackend):
            pass
    assert corrupt.value.code == "STORAGE_CORRUPT"
    assert target.read_bytes() == damaged
    # Repair only this test's synthetic fixture, never a real user's damaged store.
    target.write_bytes(original)
    with create_runtime(root, backend_factory=BoundaryBackend) as next_owner:
        if kind == "history":
            assert next_owner.api.get_download(12).status == "done"
        else:
            assert next_owner.api.get_settings().theme == "light"


def test_bool_query_id_never_aliases_a_real_entry(tmp_path: Path) -> None:
    root = tmp_path / "profile"
    runtime = create_runtime(
        root, backend_factory=BoundaryBackend,
        settings_overrides={"output_dir": str(tmp_path / "output")},
    )
    try:
        accepted = runtime.api.queue_add_download(url="https://example.invalid/real-id-one")
        assert accepted.task_id == 1
    finally:
        assert runtime.close(cancel=False, wait=True).closed
    with create_runtime(root, read_only=True) as reader:
        for query in (reader.api.get_download, reader.api.get_file_paths,
                      reader.api.read_description, reader.api.get_transcript):
            assert query(True).code == "INVALID_ARGUMENT"
        assert reader.api.get_download(1).title == "Distinctive runtime result"


def test_partial_construction_failure_releases_lease(tmp_path: Path) -> None:
    def failed_factory():
        raise RuntimeError("synthetic external-port construction failure")

    root = tmp_path / "profile"
    with pytest.raises(RuntimeError, match="synthetic external-port"):
        with create_runtime(root, file_remover_factory=failed_factory):
            pass
    with create_runtime(root, backend_factory=BoundaryBackend) as runtime:
        assert runtime.api.list_downloads() == []


@pytest.mark.parametrize("phase", ["reservation", "acceptance"])
def test_admission_failure_has_no_task_or_backend_and_next_operation_works(
    monkeypatch, tmp_path: Path, phase: str
) -> None:
    calls = []

    def backend_factory():
        calls.append("constructed")
        return BoundaryBackend()

    root = tmp_path / "profile"
    runtime = create_runtime(root, backend_factory=backend_factory,
                             settings_overrides={"output_dir": str(tmp_path / "output")})
    try:
        with monkeypatch.context() as fault:
            _fail_target_replace(
                fault, root / "data/history.json", when_entries=phase == "acceptance"
            )
            with pytest.raises(StorageError) as failed:
                runtime.api.queue_add_download(url="https://example.invalid/must-not-start")
            assert failed.value.code == "PERSISTENCE_FAILED"
            assert calls == []
            assert runtime.api.list_downloads() == []
            assert runtime.coordinator.get_tasks() == []
        accepted = runtime.api.queue_add_download(url="https://example.invalid/next")
        assert accepted.task_id == (2 if phase == "acceptance" else 1)
    finally:
        shutdown = runtime.close(cancel=False, wait=True)
    assert shutdown.closed and not shutdown.error_codes
    assert calls == ["constructed"]
    stored = JsonHistoryRepository(root / "data").get_by_id(accepted.task_id)
    assert stored.status == DownloadStatus.DONE


def test_metadata_persistence_error_is_not_swallowed_as_fetch_failure(
    monkeypatch, tmp_path: Path,
) -> None:
    downloads = []

    class ObservedBackend(BoundaryBackend):
        def download(self, task, settings, progress_callback=None):
            downloads.append(task.id)
            return super().download(task, settings, progress_callback)

    root = tmp_path / "profile"
    runtime = create_runtime(
        root, backend_factory=ObservedBackend,
        settings_overrides={"output_dir": str(tmp_path / "output")},
    )
    original = os.replace

    def fail_title_save(source, destination):
        if Path(destination) == root / "data/history.json":
            rows = json.loads(Path(source).read_text(encoding="utf-8"))["entries"]
            if any(row["title"] == "Distinctive runtime result" for row in rows):
                raise OSError("Synthetic metadata-persistence fault")
        return original(source, destination)

    try:
        with monkeypatch.context() as fault:
            fault.setattr(os, "replace", fail_title_save)
            accepted = runtime.api.queue_add_download(url="https://example.invalid/title-save")
            shutdown = runtime.close(cancel=False, wait=True)
        assert shutdown.closed
        assert shutdown.persistence_error_ids == [accepted.task_id]
        assert "PERSISTENCE_FAILED" in shutdown.error_codes
        assert downloads == []
        assert not (tmp_path / "output").exists()
        assert runtime.api.get_download(accepted.task_id).status != "done"
    finally:
        runtime.close(cancel=False, wait=True)
    with create_runtime(root, backend_factory=BoundaryBackend) as next_owner:
        assert next_owner.api.get_download(accepted.task_id).status == "failed"


def test_settings_failure_does_not_publish_defaults_and_next_update_works(
    monkeypatch, tmp_path: Path,
) -> None:
    root = tmp_path / "profile"
    with create_runtime(root, backend_factory=BoundaryBackend) as runtime:
        initial = runtime.api.get_settings()
        runtime.api.update_settings(initial)
        target = root / "config/settings.json"
        before = target.read_bytes()
        changed = runtime.api.get_settings()
        changed.theme = "light"
        changed.save_description = False
        with monkeypatch.context() as fault:
            _fail_target_replace(fault, target)
            with pytest.raises(StorageError) as failed:
                runtime.api.update_settings(changed)
            assert failed.value.code == "PERSISTENCE_FAILED"
            assert target.read_bytes() == before
            assert runtime.api.get_settings().to_dict() == initial.to_dict()
        runtime.api.update_settings(changed)
        changed.theme = "dark"
        assert runtime.api.get_settings().theme == "light"
    reopened = JsonSettingsRepository(root / "config").load()
    assert reopened.theme == "light" and reopened.save_description is False


@pytest.mark.parametrize(("field", "bad_value"), [
    ("max_concurrent", 0), ("max_concurrent", True), ("mcp_port", 65536),
    ("theme", "invalid"), ("output_dir", ""), ("save_description", None),
])
def test_invalid_settings_never_write_or_publish_defaults(tmp_path: Path, field, bad_value) -> None:
    with create_runtime(tmp_path / "profile", backend_factory=BoundaryBackend) as runtime:
        before = runtime.api.get_settings().to_dict()
        invalid = runtime.api.get_settings()
        setattr(invalid, field, bad_value)
        with pytest.raises(CommandError) as rejected:
            runtime.api.update_settings(invalid)
        assert rejected.value.code == "INVALID_ARGUMENT"
        assert runtime.api.get_settings().to_dict() == before
        assert not (runtime.data_root / "config/settings.json").exists()


def test_nonblocking_close_retains_writer_until_real_backend_join(tmp_path: Path) -> None:
    started, release = threading.Event(), threading.Event()

    class HeldBackend(BoundaryBackend):
        def fetch_info(self, url, settings):
            started.set()
            if not release.wait(10):
                raise RuntimeError("Synthetic barrier deadline")
            return super().fetch_info(url, settings)

    root = tmp_path / "profile"
    runtime = create_runtime(root, backend_factory=HeldBackend,
                             settings_overrides={"output_dir": str(tmp_path / "output")})
    try:
        accepted = runtime.api.queue_add_download(url="https://example.invalid/held")
        assert started.wait(5)
        closing = runtime.close(cancel=False, wait=False)
        assert not closing.closed and closing.pending_task_ids == [accepted.task_id]
        with pytest.raises(StorageError) as busy:
            with create_runtime(root, backend_factory=BoundaryBackend):
                pass
        assert busy.value.code == "OWNER_BUSY"
        with pytest.raises(CommandError) as closed:
            runtime.api.queue_add_download(url="https://example.invalid/too-late")
        assert closed.value.code == "RUNTIME_CLOSING"
    finally:
        release.set()
        assert runtime.close(cancel=False, wait=True).closed
    with create_runtime(root, backend_factory=BoundaryBackend) as next_owner:
        assert next_owner.api.get_download(accepted.task_id).status == "done"
    # A stale legacy repository reference cannot write after another owner opens/closes.
    with pytest.raises(StorageError) as stale:
        runtime.history_repo.next_id()
    assert stale.value.code == "RUNTIME_CLOSING"


def test_smoke_child_never_recovers_competing_inherited_data_root(tmp_path: Path) -> None:
    profile = tmp_path / "preexisting-profile"
    repo = JsonHistoryRepository(profile / "data")
    repo.add(HistoryEntry(
        id=9, url="https://example.invalid/owned-orphan", title="Untouched profile",
        status=DownloadStatus.QUEUED,
    ))
    history = profile / "data/history.json"
    before = history.read_bytes()
    before_paths = sorted(path.relative_to(profile).as_posix() for path in profile.rglob("*"))
    smoke_parent = tmp_path / "smokes"
    smoke_parent.mkdir()
    env = os.environ.copy()  # Parent process already has pre-import owned roots.
    env.update(YTDL_DATA_DIR=profile.as_posix(), YTDL_SMOKE_ROOT=smoke_parent.as_posix())
    result = subprocess.run(
        [sys.executable, "-m", "scripts.smoke_mcp"], cwd=Path(__file__).resolve().parent.parent,
        env=env, capture_output=True, text=True, timeout=25,
    )
    (tmp_path / "smoke.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (tmp_path / "smoke.stderr.txt").write_text(result.stderr, encoding="utf-8")
    (tmp_path / "smoke.native-exit.txt").write_text(str(result.returncode), encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert "mcp-smoke ok tools=10 expected=10" in result.stdout
    assert history.read_bytes() == before
    assert not (profile / ".writer.lock").exists()
    assert sorted(
        path.relative_to(profile).as_posix() for path in profile.rglob("*")
    ) == before_paths
    assert list(smoke_parent.iterdir())  # Real smoke allocated its own subtree.


@pytest.mark.parametrize("prior_present", [False, True])
@pytest.mark.parametrize("consumer_failure", [False, True])
def test_smoke_data_root_restores_environment_and_closes_real_resources(
    monkeypatch, tmp_path: Path, prior_present: bool, consumer_failure: bool,
) -> None:
    from scripts.smoke_support import close_services, isolated_smoke

    prior = tmp_path / "prior-profile"
    if prior_present:
        monkeypatch.setenv("YTDL_DATA_DIR", str(prior))
    else:
        monkeypatch.delenv("YTDL_DATA_DIR", raising=False)
    previous = os.environ.get("YTDL_DATA_DIR")
    smoke_parent = tmp_path / "smokes"
    smoke_parent.mkdir()
    monkeypatch.setenv("YTDL_SMOKE_ROOT", str(smoke_parent))
    runtime = None
    handler = None
    expected = (
        pytest.raises(RuntimeError, match="R1 synthetic consumer failure")
        if consumer_failure else nullcontext()
    )
    with expected:
        with isolated_smoke() as smoke_root:
            selected = Path(os.environ["YTDL_DATA_DIR"]).resolve()
            assert selected.is_relative_to(smoke_root.resolve())
            services = None
            try:
                services = initialize_app()
                runtime = services["runtime"]
                assert runtime.data_root == selected
                handler = logging.FileHandler(smoke_root / "own-handler.log", encoding="utf-8")
                logging.getLogger().addHandler(handler)
                if consumer_failure:
                    raise RuntimeError("R1 synthetic consumer failure")
            finally:
                close_services(services)
    assert runtime is not None and runtime.closed
    assert handler is not None and handler.stream is None
    assert handler not in logging.getLogger().handlers
    assert os.environ.get("YTDL_DATA_DIR") == previous
    assert ("YTDL_DATA_DIR" in os.environ) == prior_present
    assert not prior.exists()
