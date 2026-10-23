"""S3 public API schedules; only the external download edge is synthetic."""

from __future__ import annotations

import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.application.api import ApplicationAPI
from src.application.command_api import CommandError
from src.bootstrap import create_runtime
from src.domain.models import HistoryEntry, VideoInfo
from src.domain.models.download_outcome import DownloadOutcome
from src.domain.models.download_task import DownloadStatus
from src.infrastructure.repositories import JsonHistoryRepository


def test_oracle_queued_and_blocked_fetch_cancellation(tmp_path: Path) -> None:
    entered, release = threading.Event(), threading.Event()
    downloads: list[int] = []
    factories: list[int] = []

    class Backend:
        def __init__(self):
            factories.append(1)

        def fetch_info(self, url, settings):
            entered.set()
            assert release.wait(5), "owned fetch barrier not released"
            return VideoInfo(title="Owned task")

        def cancel(self):
            pass  # Cannot interrupt this deliberately blocked external call.

        def download(self, task, settings, progress_callback=None):
            downloads.append(task.id)
            settings.output_dir.mkdir(parents=True, exist_ok=True)
            media = settings.output_dir / f"owned-{task.id}.mp4"
            media.write_bytes(f"task-{task.id}".encode())
            return {"video": media, "scan_root": settings.output_dir}

    root = tmp_path / "runtime"
    runtime = create_runtime(
        root,
        settings_overrides={
            "output_dir": tmp_path / "output",
            "max_concurrent": 1,
        },
        backend_factory=Backend,
    )
    try:
        api = runtime.api
        a = api.queue_add_download(url="https://example.invalid/a").task_id
        assert entered.wait(5)
        b = api.queue_add_download(url="https://example.invalid/b").task_id
        api.cancel_download(b)
        api.cancel_download(a)
        before = {
            "queued_task": runtime.coordinator.get_task(b).status.value,
            "queued_history": runtime.history_repo.get_by_id(b).status.value,
            "active_history": runtime.history_repo.get_by_id(a).status.value,
        }
    finally:
        release.set()
        closed = runtime.close(cancel=False, wait=True)
    assert closed.closed and not closed.pending_task_ids
    (tmp_path / "oracle-schedule.json").write_text(json.dumps(before), encoding="utf-8")
    assert before["queued_task"] == "cancelled"
    assert before["queued_history"] == "cancelled"
    assert before["active_history"] == "downloading"
    reopened = JsonHistoryRepository(root / "data")
    assert reopened.get_by_id(a).status == DownloadStatus.CANCELLED
    assert reopened.get_by_id(b).status == DownloadStatus.CANCELLED
    assert downloads == []
    assert len(factories) == 1


class Edge:
    """Synthetic external effect, never a substitute for the queue/repository/API."""

    def fetch_info(self, url, settings):
        return VideoInfo(title=url.rsplit("/", 1)[-1])

    def cancel(self):
        pass

    def download(self, task, settings, progress_callback=None):
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        media = settings.output_dir / f"owned-{task.id}.mp4"
        media.write_bytes(f"owned-media-{task.id}".encode())
        return DownloadOutcome.from_paths({"video": media, "scan_root": settings.output_dir})


def make_runtime(tmp_path, factory=Edge, cap=1):
    return create_runtime(
        tmp_path / "runtime",
        backend_factory=factory,
        settings_overrides={
            "output_dir": tmp_path / "output",
            "max_concurrent": cap,
            "quality": "720p",
            "save_description": False,
            "proxy": "",
        },
    )


@pytest.mark.parametrize("operation", ["list", "search"])
def test_selection_keeps_one_projection_when_worker_finishes_before_mapping(
    tmp_path: Path,
    operation: str,
) -> None:
    entered, release = threading.Event(), threading.Event()

    class Held(Edge):
        def download(self, task, settings, progress_callback=None):
            if task.url.endswith("/selected"):
                entered.set()
                assert release.wait(5)
            return super().download(task, settings, progress_callback)

    runtime = make_runtime(tmp_path, Held)
    previous_trace = sys.gettrace()
    checkpoints = []
    try:
        api = runtime.api
        older = api.queue_add_download(url="https://example.invalid/other").task_id
        assert api.wait_for_download(older, timeout=5).status == "done"
        selected = api.queue_add_download(url="https://example.invalid/selected").task_id
        assert entered.wait(5)
        queued = api.queue_add_download(url="https://example.invalid/other-queued").task_id
        assert api.get_task(selected).status == "downloading"
        mapper = ApplicationAPI._annotate.__code__

        def trace(frame, event, arg):
            if event == "call" and frame.f_code is mapper and not checkpoints:
                checkpoints.append("selection complete; ordinary worker completion before mapping")
                release.set()
                completed = api.wait_for_download(selected, timeout=5)
                assert completed.status == "done" and completed.result_persisted
            return trace

        sys.settrace(trace)
        try:
            rows = (
                api.list_downloads(status="downloading", limit=1)
                if operation == "list"
                else api.search_downloads("selected", limit=1, with_description=True)
            )
        finally:
            sys.settrace(previous_trace)
        assert len(checkpoints) == len(rows) == 1
        assert rows[0].id == selected and rows[0].status == "downloading"
        assert rows[0].title == "selected" and rows[0].cancel_requested is False
        assert rows[0].result_persisted is None and rows[0].error_code is None
        assert rows[0].artifact_paths == []
        terminal = api.wait_for_download(selected, timeout=5)
        assert terminal.status == "done" and terminal.result_persisted
        assert Path(terminal.artifact_paths[0]).read_bytes() == f"owned-media-{selected}".encode()
        assert api.wait_for_download(queued, timeout=5).status == "done"
        useful = api.queue_add_download(url="https://example.invalid/useful-after-query").task_id
        assert api.wait_for_download(useful, timeout=5).status == "done"
    finally:
        sys.settrace(previous_trace)
        release.set()
        closed = runtime.close(cancel=False, wait=True)
    assert closed.closed and not closed.pending_task_ids and not closed.error_codes
    stored = JsonHistoryRepository(tmp_path / "runtime/data").get_by_id(selected)
    assert stored.status == DownloadStatus.DONE
    assert stored.artifact_paths == [Path(p) for p in terminal.artifact_paths]


def test_cancel_before_service_registration_and_next_useful_task(tmp_path: Path) -> None:
    entered, release = threading.Event(), threading.Event()
    fetched, downloaded, signals = [], [], []

    class Observed(Edge):
        def fetch_info(self, url, settings):
            fetched.append(url)
            return super().fetch_info(url, settings)

        def download(self, task, settings, progress_callback=None):
            downloaded.append(task.id)
            return super().download(task, settings, progress_callback)

        def cancel(self):
            signals.append(1)

    def factory():
        entered.set()
        assert release.wait(5)
        return Observed()

    runtime = make_runtime(tmp_path, factory)
    events = []
    for name in ("queued", "started", "cancelled", "done"):
        runtime.event_bus.subscribe(
            "download." + name, lambda _name=name, **kw: events.append((_name, kw["task_id"]))
        )
    try:
        api = runtime.api
        a = api.queue_add_download(url="https://example.invalid/a").task_id
        assert entered.wait(5)
        assert api.cancel_download(a).status == "cancel_requested"
        assert api.cancel_download(a).status == "cancel_requested"
        current = api.wait_for_download(a, timeout=0)
        assert current.cancel_requested and current.status == "downloading"
        assert runtime.history_repo.get_by_id(a).status == DownloadStatus.DOWNLOADING
        release.set()
        terminal = api.wait_for_download(a, timeout=5)
        assert terminal.status == "cancelled" and terminal.result_persisted
        assert fetched == downloaded == []
        assert signals == [1]
        assert api.cancel_download(a).status == "cancelled"
        b = api.queue_add_download(url="https://example.invalid/b").task_id
        assert api.wait_for_download(b, timeout=5).status == "done"
        assert downloaded == [b]
        assert [name for name, ident in events if ident == a] == ["queued", "started", "cancelled"]
    finally:
        release.set()
        closed = runtime.close(cancel=False, wait=True)
    assert closed.closed and not closed.pending_task_ids
    assert (
        JsonHistoryRepository(tmp_path / "runtime/data").get_by_id(a).status
        == DownloadStatus.CANCELLED
    )


def test_immediate_completion_done_after_save_late_progress_and_monotonic_cancel(
    tmp_path: Path,
) -> None:
    callbacks, events, durable_at_done = [], [], []

    class Immediate(Edge):
        def download(self, task, settings, progress_callback=None):
            callbacks.append(progress_callback)
            return super().download(task, settings, progress_callback)

    runtime = make_runtime(tmp_path, Immediate)
    for name in ("queued", "started", "done"):
        runtime.event_bus.subscribe(
            "download." + name, lambda _name=name, **kw: events.append((_name, kw["task_id"]))
        )
    runtime.event_bus.subscribe(
        "download.done",
        lambda task_id, entry_id: durable_at_done.append(
            JsonHistoryRepository(tmp_path / "runtime/data").get_by_id(entry_id).status
        ),
    )
    try:
        api = runtime.api
        a = api.queue_add_download(url="https://example.invalid/instant").task_id
        terminal = api.wait_for_download(a, timeout=5)
        assert terminal.status == "done" and terminal.result_persisted
        assert [name for name, ident in events if ident == a] == ["queued", "started", "done"]
        assert durable_at_done == [DownloadStatus.DONE]
        with pytest.raises(CommandError) as rejected:
            api.cancel_download(a)
        assert rejected.value.code == "ALREADY_TERMINAL"
        callbacks[0](1.0, 2.0, 99)
        assert api.get_task(a) == terminal
        terminal.artifact_paths.clear()
        assert len(api.get_task(a).artifact_paths) == 1
        b = api.queue_add_download(url="https://example.invalid/next").task_id
        assert api.wait_for_download(b, timeout=5).status == "done"
        first = api.get_file_paths(a)
        second = api.get_file_paths(b)
        assert first.video_path != second.video_path
        assert Path(first.video_path).read_bytes() == f"owned-media-{a}".encode()
        assert Path(second.video_path).read_bytes() == f"owned-media-{b}".encode()
    finally:
        closed = runtime.close(cancel=False, wait=True)
    assert closed.closed and not closed.pending_task_ids


@pytest.mark.parametrize("independent_failure", [False, True])
def test_cancel_wins_before_completion_but_does_not_hide_failure(
    tmp_path: Path, independent_failure: bool
) -> None:
    entered, release = threading.Event(), threading.Event()

    class Held(Edge):
        def download(self, task, settings, progress_callback=None):
            outcome = super().download(task, settings, progress_callback)
            entered.set()
            assert release.wait(5)
            if independent_failure:
                return DownloadOutcome.from_paths(
                    {"video": outcome.video}, status="failed", error_code="DOWNLOAD_FAILED"
                )
            return outcome

    runtime = make_runtime(tmp_path, Held)
    try:
        api = runtime.api
        ident = api.queue_add_download(url="https://example.invalid/held").task_id
        assert entered.wait(5)
        api.cancel_download(ident)
        assert api.get_task(ident).cancel_requested
        assert api.wait_for_download(ident, timeout=0).status == "downloading"
        assert runtime.history_repo.get_by_id(ident).status == DownloadStatus.DOWNLOADING
        release.set()
        result = api.wait_for_download(ident, timeout=5)
        assert result.status == ("failed" if independent_failure else "cancelled")
        assert result.result_persisted
        assert len(result.artifact_paths) == 1
        assert Path(result.artifact_paths[0]).read_bytes() == f"owned-media-{ident}".encode()
    finally:
        release.set()
        runtime.close(cancel=False, wait=True)
    stored = JsonHistoryRepository(tmp_path / "runtime/data").get_by_id(ident)
    assert stored.status.value == result.status
    assert stored.artifact_paths == [Path(p) for p in result.artifact_paths]


def test_empty_and_unrelated_artifacts_fail_with_genuine_positive_admission(tmp_path: Path) -> None:
    foreign = tmp_path / "foreign/newer/movie.mp4"
    foreign.parent.mkdir(parents=True)
    foreign.write_bytes(b"unrelated existing bytes")

    class Selected(Edge):
        def download(self, task, settings, progress_callback=None):
            if task.url.endswith("empty"):
                return DownloadOutcome("completed")
            if task.url.endswith("foreign"):
                return DownloadOutcome.from_paths({"video": foreign})
            return super().download(task, settings, progress_callback)

    runtime = make_runtime(tmp_path, Selected)
    try:
        for label in ("empty", "foreign", "useful"):
            ident = runtime.api.queue_add_download(url="https://example.invalid/" + label).task_id
            result = runtime.api.wait_for_download(ident, timeout=5)
            assert result.status == ("done" if label == "useful" else "failed")
            assert result.result_persisted
            assert len(result.artifact_paths) == (1 if label == "useful" else 0)
        assert foreign.read_bytes() == b"unrelated existing bytes"
    finally:
        runtime.close(cancel=False, wait=True)


def test_terminal_save_fault_after_media_effect_live_overlay_and_next_operation(
    monkeypatch, tmp_path: Path
) -> None:
    runtime = make_runtime(tmp_path)
    target = (tmp_path / "runtime/data/history.json").resolve()
    original = os.replace
    enabled = True

    def refuse_done(source, destination):
        if (
            enabled
            and Path(destination).resolve() == target
            and b'"status": "done"' in Path(source).read_bytes()
        ):
            raise OSError("OWNED_SYNTHETIC_STORAGE_SECRET")
        return original(source, destination)

    monkeypatch.setattr(os, "replace", refuse_done)
    done = []
    runtime.event_bus.subscribe("download.done", lambda task_id, entry_id: done.append(task_id))
    try:
        api = runtime.api
        a = api.queue_add_download(url="https://example.invalid/persist-fault").task_id
        result = api.wait_for_download(a, timeout=5)
        assert result.status == "failed" and result.result_persisted is False
        assert result.error_code == "PERSISTENCE_FAILED"
        assert done == []
        assert len(result.artifact_paths) == 1
        assert Path(result.artifact_paths[0]).read_bytes() == f"owned-media-{a}".encode()
        details = api.get_file_paths(a)
        assert details.status == "failed" and details.result_persisted is False
        assert details.error_code == "PERSISTENCE_FAILED"
        assert details.artifact_paths == result.artifact_paths
        assert details.video_path == result.artifact_paths[0]
        assert [row.id for row in api.list_downloads(status="failed")] == [a]
        assert runtime.history_repo.get_by_id(a).status == DownloadStatus.DOWNLOADING
        enabled = False
        b = api.queue_add_download(url="https://example.invalid/next").task_id
        assert api.wait_for_download(b, timeout=5).status == "done"
        assert done == [b]
    finally:
        enabled = False
        closed = runtime.close(cancel=False, wait=True)
    assert closed.closed and closed.persistence_error_ids == [a]
    assert closed.error_codes == ["PERSISTENCE_FAILED"]
    assert Path(result.artifact_paths[0]).is_file()
    with create_runtime(tmp_path / "runtime", read_only=True) as reader:
        assert reader.api.get_download(a).result_persisted is None
        assert reader.api.get_download(a).status == "downloading"


def test_admission_snapshots_and_real_pool_cap_only_after_full_drain(tmp_path: Path) -> None:
    labels = "abcde"
    entered = {key: threading.Event() for key in labels}
    release = {key: threading.Event() for key in labels}
    observations, active, peak = {}, 0, 0
    mutex = threading.Lock()

    class SnapshotEdge(Edge):
        def fetch_info(self, url, settings):
            key = url.rsplit("/", 1)[-1]
            observations[key + "-fetch"] = (settings.output_dir, settings.proxy)
            settings.proxy = "backend-local mutation must not change admission"
            return VideoInfo(title=key)

        def download(self, task, settings, progress_callback=None):
            nonlocal active, peak
            key = task.title
            with mutex:
                active += 1
                peak = max(peak, active)
            try:
                observations[key] = (
                    settings.output_dir,
                    settings.proxy,
                    task.save_description,
                    task.quality.value,
                )
                entered[key].set()
                assert release[key].wait(5)
                return super().download(task, settings, progress_callback)
            finally:
                with mutex:
                    active -= 1

    runtime = make_runtime(tmp_path, SnapshotEdge)
    args = dict(quality=None, download_type=None, save_description=None)
    try:
        api = runtime.api
        a = api.queue_add_download(url="https://example.invalid/a", **args).task_id
        assert entered["a"].wait(5)
        b = api.queue_add_download(url="https://example.invalid/b", **args).task_id
        settings = api.get_settings()
        settings.output_dir = tmp_path / "new-output"
        settings.proxy = "https://example.invalid/owned-new-proxy"
        settings.save_description = True
        settings.quality = type(settings.quality)("1080p")
        settings.max_concurrent = 2
        api.update_settings(settings)
        c = api.queue_add_download(url="https://example.invalid/c", **args).task_id
        assert not entered["b"].is_set() and not entered["c"].is_set()
        release["a"].set()
        assert api.wait_for_download(a, timeout=5).status == "done"
        assert entered["b"].wait(5) and not entered["c"].is_set()
        release["b"].set()
        assert api.wait_for_download(b, timeout=5).status == "done"
        assert entered["c"].wait(5)
        assert peak == 1
        release["c"].set()
        assert api.wait_for_download(c, timeout=5).status == "done"
        d = api.queue_add_download(url="https://example.invalid/d", **args).task_id
        e = api.queue_add_download(url="https://example.invalid/e", **args).task_id
        assert entered["d"].wait(5) and entered["e"].wait(5)
        assert active == peak == 2
        release["d"].set()
        release["e"].set()
        assert api.wait_for_download(d, timeout=5).status == "done"
        assert api.wait_for_download(e, timeout=5).status == "done"
        for key in "ab":
            assert observations[key] == (tmp_path / "output", "", False, "720p")
            assert observations[key + "-fetch"] == (tmp_path / "output", "")
        for key in "cde":
            assert observations[key] == (settings.output_dir, settings.proxy, True, "1080p")
            assert observations[key + "-fetch"] == (settings.output_dir, settings.proxy)
        assert api.get_settings().proxy == settings.proxy
    finally:
        for signal in release.values():
            signal.set()
        closed = runtime.close(cancel=False, wait=True)
    assert active == 0 and closed.closed
    readback = JsonHistoryRepository(tmp_path / "runtime/data")
    assert readback.get_by_id(a).output_root == tmp_path / "output"
    assert readback.get_by_id(c).output_root == settings.output_dir


def test_submit_refusal_and_history_only_require_owner(monkeypatch, tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    try:
        api = runtime.api
        runtime.history_repo.add(
            HistoryEntry(
                id=90, url="https://example.invalid/history-only", status=DownloadStatus.DONE
            )
        )
        for operation in (api.prepare_cancel_download, api.cancel_download, api.wait_for_download):
            with pytest.raises(CommandError) as refusal:
                operation(90)
            assert refusal.value.code == "OWNER_REQUIRED"
        assert api.get_task(90).code == "OWNER_REQUIRED"
        assert api.get_task(999).code == "NOT_FOUND"
        with pytest.raises(CommandError) as invalid:
            api.wait_for_download(0, timeout=0)
        assert invalid.value.code == "INVALID_ARGUMENT"

        def refuse_submit(*args, **kwargs):
            raise RuntimeError("OWNED_SYNTHETIC_EXECUTOR_REFUSAL")

        # Technical fault at the native executor boundary, not a successful fake queue.
        with monkeypatch.context() as fault:
            fault.setattr(ThreadPoolExecutor, "submit", refuse_submit)
            with pytest.raises(CommandError) as unavailable:
                api.queue_add_download(url="https://example.invalid/refused-execution")
        assert unavailable.value.code == "EXECUTION_UNAVAILABLE"
        ident = unavailable.value.task_id
        assert ident is not None and unavailable.value.result["status"] == "failed"
        assert api.wait_for_download(ident, timeout=0).status == "failed"
        assert api.get_task(ident).result_persisted
        assert runtime.history_repo.get_by_id(ident).error_code == "EXECUTION_UNAVAILABLE"
        useful = api.queue_add_download(url="https://example.invalid/useful-after-refusal").task_id
        assert api.wait_for_download(useful, timeout=5).status == "done"
    finally:
        closed = runtime.close(cancel=False, wait=True)
    assert closed.closed and not closed.pending_task_ids and not closed.error_codes


def test_close_active_queued_subscriber_failure_and_reopen(tmp_path: Path) -> None:
    entered, release = threading.Event(), threading.Event()
    threads, outside_lock = [], []

    class Held(Edge):
        def fetch_info(self, url, settings):
            entered.set()
            assert release.wait(5)
            return super().fetch_info(url, settings)

    runtime = make_runtime(tmp_path, Held)

    def broken(**kwargs):
        raise RuntimeError("PRIVATE_SUBSCRIBER_CONTENT")

    def observe(**kwargs):
        finished = threading.Event()

        def read():
            runtime.api.get_task(kwargs["task_id"])
            runtime.event_bus.subscribe("unused", lambda: None)
            finished.set()

        thread = threading.Thread(target=read)
        threads.append(thread)
        thread.start()
        outside_lock.append(finished.wait(2))

    runtime.event_bus.subscribe("download.queued", broken)
    runtime.event_bus.subscribe("download.queued", observe)
    try:
        api = runtime.api
        a = api.queue_add_download(url="https://example.invalid/a").task_id
        assert entered.wait(5)
        b = api.queue_add_download(url="https://example.invalid/b").task_id
        closing = runtime.close(cancel=True, wait=False)
        assert not closing.closed and a in closing.pending_task_ids
        assert api.get_task(a).cancel_requested and api.get_task(a).status == "downloading"
        assert api.get_task(b).status == "cancelled"
        with pytest.raises(CommandError) as refused:
            api.queue_add_download(url="https://example.invalid/refused")
        assert refused.value.code == "RUNTIME_CLOSING"
    finally:
        release.set()
        closed = runtime.close(cancel=True, wait=True)
        for thread in threads:
            thread.join(5)
    assert all(outside_lock) and all(not thread.is_alive() for thread in threads)
    assert closed.closed and not closed.pending_task_ids and not closed.error_codes
    assert runtime.close() == closed
    with create_runtime(tmp_path / "runtime", backend_factory=Edge) as next_owner:
        assert next_owner.api.get_download(a).status == "cancelled"
        assert next_owner.api.get_download(b).status == "cancelled"
