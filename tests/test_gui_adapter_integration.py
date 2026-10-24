"""Connected, offscreen adapter proofs. Product events/signals are never invented."""

from __future__ import annotations

import asyncio
import json
import socket
from threading import Event

import pytest
from fastmcp import Client
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox, QPushButton

import app as desktop
from main import initialize_app
from src.application.command_api import CommandError
from src.bootstrap import create_runtime
from src.domain.models import HistoryEntry
from src.domain.models.download_task import DownloadStatus
from src.infrastructure.mcp.server import HTTPServerHandle
from src.ui.main_window import MainWindow
from src.ui.managers.history_manager import HistoryManager
from src.ui.widgets.settings_dialog import SettingsDialog
from tests.test_adapter_integration import GateEdge


class FixtureTrash:
    def __init__(self, root):
        self.root, self.moves = root, []

    def move_to_trash(self, path):
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / path.name
        path.rename(target)
        self.moves.append((path, target))
        return True

    def close(self):
        pass


def fixture_record(runtime, root, *, entry_id=10, title="Visible anchor"):
    folder = root / f"output/download-{entry_id}"
    folder.mkdir(parents=True, exist_ok=True)
    media, sidecar = folder / "owned.media", folder / "owned.description"
    media.write_bytes(b"distinct owned media")
    sidecar.write_bytes(b"distinct owned sidecar")
    (folder / "unlisted.bin").write_bytes(b"unlisted preservation")
    runtime.history_repo.add(
        HistoryEntry(
            id=entry_id,
            title=title,
            url="https://example.invalid/fixture",
            status=DownloadStatus.DONE,
            output_root=root / "output",
            output_dir=folder,
            video_path=media,
            description_path=sidecar,
            artifact_paths=[media, sidecar],
        )
    )
    return folder, [media, sidecar]


def test_real_gui_initial_snapshot_http_gui_add_cancel_and_preserved_history_filter(
    tmp_path, qtbot
):
    entered, release = Event(), Event()
    runtime = create_runtime(
        tmp_path / "profile",
        settings_overrides={"output_dir": tmp_path / "output"},
        backend_factory=lambda: GateEdge(entered, release),
    )
    window = handle = None
    try:
        fixture_record(runtime, tmp_path)
        early = runtime.api.queue_add_download(url="https://example.invalid/pre-window")
        assert entered.wait(3)
        window = MainWindow(runtime.as_services())
        qtbot.addWidget(window)
        window.show()
        assert early.task_id in window._item_widgets  # Restored, no synthetic queued event.
        window._history_widget._search_edit.setText("Visible anchor")
        handle = HTTPServerHandle(runtime.as_services(), port=0).start()

        async def add():
            async with Client(handle.endpoint, timeout=5) as client:
                return (
                    await client.call_tool(
                        "add_download", {"url": "https://example.invalid/from-http"}
                    )
                ).data

        remote = asyncio.run(add())["task_id"]
        qtbot.waitUntil(lambda: remote in window._item_widgets, timeout=3000)
        window._url_input._url_edit.setText("https://www.youtube.com/watch?v=GUI_OWNED_SYNTHETIC")
        window._url_input._add_btn.click()
        qtbot.waitUntil(lambda: len(window._item_widgets) == 3, timeout=3000)
        ids = {task.id for task in runtime.api.list_tasks()}
        assert set(window._item_widgets) == ids
        window._item_widgets[early.task_id]._cancel_btn.click()
        assert runtime.api.get_task(early.task_id).cancel_requested
        assert runtime.api.get_task(early.task_id).status not in {"done", "failed", "cancelled"}
        assert (
            window._item_widgets[early.task_id]._status_label.text()
            != DownloadStatus.CANCELLED.display_name()
        )
        release.set()
        for task_id in ids:
            expected = "cancelled" if task_id == early.task_id else "done"
            assert runtime.api.wait_for_download(task_id, timeout=4).status == expected
        qtbot.waitUntil(
            lambda: (
                window._item_widgets[early.task_id]._status_label.text()
                == DownloadStatus.CANCELLED.display_name()
            ),
            timeout=3000,
        )
        qtbot.waitUntil(lambda: len(window._history_widget._items) == 4, timeout=3000)
        assert window._history_widget._search_edit.text() == "Visible anchor"
        assert [
            item._entry.id for item in window._history_widget._items if not item.isHidden()
        ] == [10]
        for task_id in ids - {early.task_id}:
            entry = runtime.history_repo.get_by_id(task_id)
            assert entry.video_path.read_bytes() == f"owned bridge media {task_id}".encode()
        window.close()
        window.cleanup()
        assert not runtime.closed
        next_task = runtime.api.queue_add_download(url="https://example.invalid/after-window-close")
        assert runtime.api.wait_for_download(next_task.task_id, timeout=4).status == "done"
    finally:
        release.set()
        if handle is not None:
            assert handle.close(timeout=8)
        if window is not None:
            window.cleanup()
            window.close()
        assert runtime.close(cancel=True, wait=True).closed


@pytest.mark.parametrize(
    "mode,answer,stale",
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (True, True, False),
        (False, True, True),
        (True, True, True),
    ],
)
def test_actual_modal_modes_no_yes_stale_tokens_and_physical_preservation(
    tmp_path, qtbot, monkeypatch, mode, answer, stale
):
    trash = FixtureTrash(tmp_path / "recoverable")
    runtime = create_runtime(
        tmp_path / "profile",
        settings_overrides={"output_dir": tmp_path / "output"},
        file_remover_factory=lambda: trash,
    )
    window = None
    errors, previews, failures = [], [], []
    try:
        folder, files = fixture_record(runtime, tmp_path)
        history = runtime.data_root / "data/history.json"
        before = history.read_bytes()
        original = type(runtime.api).prepare_delete_download

        def observe(owner, *args, **kwargs):
            plan = original(owner, *args, **kwargs)
            if owner is runtime.api:
                previews.append((kwargs["delete_files"], plan.plan_token))
            return plan

        monkeypatch.setattr(type(runtime.api), "prepare_delete_download", observe)
        original_delete = type(runtime.api).delete_download

        def observe_apply(owner, *args, **kwargs):
            try:
                return original_delete(owner, *args, **kwargs)
            except CommandError as error:
                if owner is runtime.api:
                    failures.append(error)
                raise

        monkeypatch.setattr(type(runtime.api), "delete_download", observe_apply)
        window = MainWindow(runtime.as_services())
        qtbot.addWidget(window)
        window.show()
        item = window._history_widget._items[0]
        sent = []
        window._history_widget.delete_requested.connect(lambda *values: sent.append(values))

        def choose():
            box = QApplication.activeModalWidget()
            try:
                assert isinstance(box, QMessageBox)
                assert [row[0] for row in previews] == [False, True]
                assert history.read_bytes() == before and not trash.moves
                box.checkBox().setChecked(mode)
                if stale:
                    updated = runtime.history_repo.get_by_id(10)
                    updated.title = "Changed while the actual modal is open"
                    runtime.history_repo.update(updated)
                box.button(
                    QMessageBox.StandardButton.Yes if answer else QMessageBox.StandardButton.No
                ).click()
            except BaseException as error:
                errors.append(error)
                if isinstance(box, QMessageBox):
                    box.reject()

        QTimer.singleShot(0, choose)
        button = next(
            button
            for button in item.findChildren(QPushButton)
            if button.toolTip() == "Удалить из истории"
        )
        button.click()  # Real clicked → modal exec → real button callback → Qt signal → API.
        if errors:
            raise errors[0]
        assert (
            folder / "unlisted.bin"
        ).read_bytes() == b"unlisted preservation" and folder.is_dir()
        if not answer:
            assert sent == [] and history.read_bytes() == before and not trash.moves
        else:
            assert sent == [(10, mode, dict(previews)[mode])]
            if stale:
                assert runtime.history_repo.get_by_id(10).title.startswith("Changed while")
                assert not trash.moves and len(failures) == 1 and failures[0].code == "STALE_PLAN"
                assert window._status_bar.currentMessage() == failures[0].message
            else:
                assert runtime.history_repo.get_by_id(10) is None
                with create_runtime(runtime.data_root, read_only=True) as view:
                    assert view.api.list_history_entries() == []
                assert len(trash.moves) == (2 if mode else 0)
        for index, path in enumerate(files):
            expected = (b"distinct owned media", b"distinct owned sidecar")[index]
            actual = trash.root / path.name if answer and mode and not stale else path
            assert actual.read_bytes() == expected
        (tmp_path / "modal-observation.json").write_text(
            json.dumps(
                {
                    "mode": mode,
                    "answer": answer,
                    "stale": stale,
                    "preview_count_before_modal_choice": len(previews),
                    "real_moves": len(trash.moves),
                    "signal_count": len(sent),
                    "history_retained": runtime.history_repo.get_by_id(10) is not None,
                }
            ),
            encoding="utf-8",
        )
    finally:
        if window is not None:
            window.cleanup()
            window.close()
        assert runtime.close(cancel=False, wait=True).closed


def test_gui_detached_settings_cancel_save_theme_and_no_repository_fallback(tmp_path, qtbot):
    runtime = create_runtime(
        tmp_path / "profile", settings_overrides={"output_dir": tmp_path / "output"}
    )
    services = runtime.as_services()
    window = None
    errors = []
    try:
        window = MainWindow(services)
        qtbot.addWidget(window)
        window.show()
        initial = runtime.api.get_settings()
        for save in (False, True):

            def choose(save=save):
                dialog = QApplication.activeModalWidget()
                try:
                    assert isinstance(dialog, SettingsDialog)
                    dialog._concurrent_spin.setValue(initial.max_concurrent + 1)
                    assert runtime.api.get_settings().max_concurrent == initial.max_concurrent
                    if save:
                        dialog.findChild(QDialogButtonBox).button(
                            QDialogButtonBox.StandardButton.Ok
                        ).click()
                    else:
                        dialog.reject()
                except BaseException as error:
                    errors.append(error)
                    dialog.reject()

            QTimer.singleShot(0, choose)
            window._settings_btn.click()
            if errors:
                raise errors[0]
            assert runtime.api.get_settings().max_concurrent == initial.max_concurrent + int(save)
        window._theme_btn.click()
        assert runtime.api.get_settings().theme != initial.theme
        assert (
            services["settings"].theme == initial.theme
        )  # Original detached object did not mutate.
        assert services["settings"].max_concurrent == initial.max_concurrent
        with create_runtime(runtime.data_root, read_only=True) as view:
            assert view.api.get_settings().theme == runtime.api.get_settings().theme
            assert view.api.get_settings().max_concurrent == initial.max_concurrent + 1
        with pytest.raises(CommandError) as denied:
            HistoryManager(runtime.history_repo, runtime.event_bus)
        assert denied.value.code == "OWNER_REQUIRED"
    finally:
        if window is not None:
            window.cleanup()
            window.close()
        assert runtime.close(cancel=False, wait=True).closed


def test_desktop_early_http_admission_follows_window_subscription_and_restoration(
    tmp_path, qapp, monkeypatch
):
    entered, release = Event(), Event()
    runtime = create_runtime(
        tmp_path / "profile",
        settings_overrides={"output_dir": tmp_path / "output"},
        backend_factory=lambda: GateEdge(entered, release),
    )
    early = runtime.api.queue_add_download(url="https://example.invalid/before-desktop")
    assert entered.wait(3)
    windows, handles, remote_ids, errors = [], [], [], []
    original_init, original_start = MainWindow.__init__, desktop._start_mcp_safe

    def observe_window(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        windows.append(self)

    def start(services, host, port):
        assert len(windows) == 1 and early.task_id in windows[0]._item_widgets
        handle = original_start(services, host, port)
        handles.append(handle)

        async def add():
            async with Client(handle.endpoint, timeout=5) as client:
                return (
                    await client.call_tool(
                        "add_download", {"url": "https://example.invalid/early-http"}
                    )
                ).data

        remote_ids.append(asyncio.run(add())["task_id"])
        return handle

    monkeypatch.setattr(MainWindow, "__init__", observe_window)
    monkeypatch.setattr(desktop, "_start_mcp_safe", start)

    def finish():
        try:
            qapp.processEvents()
            assert set(windows[0]._item_widgets) == {early.task_id, remote_ids[0]}
            windows[0]._item_widgets[early.task_id]._cancel_btn.click()
            assert runtime.api.get_task(early.task_id).status != "cancelled"
            release.set()
            assert runtime.api.wait_for_download(early.task_id, timeout=4).status == "cancelled"
            assert runtime.api.wait_for_download(remote_ids[0], timeout=4).status == "done"
        except BaseException as error:
            errors.append(error)
        finally:
            release.set()
            qapp.quit()

    QTimer.singleShot(0, finish)
    try:
        code = desktop.run_desktop(qapp, runtime.as_services(), port=0)
        if errors:
            raise errors[0]
        assert (
            code == 0 and runtime.closed and handles[0].closed and not handles[0].thread.is_alive()
        )
        assert handles[0].close()
        with socket.socket() as reusable:
            reusable.bind(("127.0.0.1", handles[0].port))
        with create_runtime(runtime.data_root) as next_owner:
            assert (
                next_owner.history_repo.get_by_id(early.task_id).status == DownloadStatus.CANCELLED
            )
            assert next_owner.history_repo.get_by_id(remote_ids[0]).status == DownloadStatus.DONE
    finally:
        release.set()
        for handle in handles:
            assert handle.close(timeout=8)
        for window in windows:
            window.cleanup()
            window.close()
        assert runtime.close(cancel=True, wait=True).closed


def test_desktop_window_construction_failure_unsubscribes_and_releases_own_profile(
    tmp_path, qapp, monkeypatch
):
    runtime = create_runtime(tmp_path / "profile")
    subscribed, unsubscribed = [], []
    original_subscribe, original_unsubscribe = (
        runtime.event_bus.subscribe,
        runtime.event_bus.unsubscribe,
    )

    def subscribe(event, callback):
        original_subscribe(event, callback)
        subscribed.append((event, callback))

    def unsubscribe(event, callback):
        original_unsubscribe(event, callback)
        unsubscribed.append((event, callback))

    monkeypatch.setattr(runtime.event_bus, "subscribe", subscribe)
    monkeypatch.setattr(runtime.event_bus, "unsubscribe", unsubscribe)
    original = MainWindow._init_ui

    def fail_after_actual_ui(self):
        original(self)
        raise RuntimeError("PRIVATE_GUI_CONSTRUCTION_SENTINEL")

    monkeypatch.setattr(MainWindow, "_init_ui", fail_after_actual_ui)
    assert desktop.run_desktop(qapp, runtime.as_services(), port=0) == 1
    assert runtime.closed and len(subscribed) == 10 and set(subscribed) <= set(unsubscribed)
    with create_runtime(runtime.data_root) as next_owner:
        assert next_owner.api.get_settings() is not None
    assert runtime.close().closed


def test_desktop_bind_failure_preserves_foreign_listener_and_releases_runtime(tmp_path, qapp):
    runtime = create_runtime(tmp_path / "profile")
    with socket.socket() as foreign:
        foreign.bind(("127.0.0.1", 0))
        foreign.listen()
        port = foreign.getsockname()[1]
        assert desktop.run_desktop(qapp, runtime.as_services(), port=port) == 1
        assert runtime.closed
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            connection, _ = foreign.accept()
            connection.close()
        assert foreign.getsockname()[1] == port
    with create_runtime(runtime.data_root) as next_owner:
        assert next_owner.api.get_settings() is not None


def test_partial_composition_and_reported_close_error_leave_no_lease_or_listener(tmp_path, qapp):
    profile = tmp_path / "profile"

    def broken_port():
        raise RuntimeError("PRIVATE_PARTIAL_DEPENDENCY_SENTINEL")

    with pytest.raises(RuntimeError):
        initialize_app(profile, file_remover_factory=broken_port)
    attempts, allow_cleanup = [], Event()

    class FailingClose:
        def __init__(self):
            self.stream = (tmp_path / "owned-resource.bin").open("wb")

        def move_to_trash(self, path):
            raise AssertionError("unused boundary")

        def close(self):
            self.stream.close()
            attempts.append(True)
            if not allow_cleanup.is_set():
                raise RuntimeError("PRIVATE_CLOSE_ERROR_SENTINEL")

    services = initialize_app(profile, file_remover_factory=FailingClose)
    try:
        QTimer.singleShot(0, qapp.quit)
        assert desktop.run_desktop(qapp, services, port=0) == 1
        # Accepted owner deliberately retains the lease after a resource-close error.
        assert not services["runtime"].closed and attempts
        again = services["runtime"].close()
        assert not again.closed and again.error_codes
        with pytest.raises(Exception) as busy:
            create_runtime(profile)
        assert getattr(busy.value, "code", None) == "OWNER_BUSY"
    finally:
        allow_cleanup.set()  # Repair only the controlled external resource failure.
        assert services["runtime"].close(cancel=True, wait=True).closed
    final = services["runtime"].close()
    assert final.closed and final.error_codes  # Historical error is not relabelled clean.
    with create_runtime(profile) as next_owner:
        assert next_owner.api.get_settings() is not None


def test_actual_gui_mcp_cli_diagnostics_have_nonempty_safe_file_and_stderr_sinks(
    tmp_path, qtbot, qapp, monkeypatch, capsys
):
    from src.domain.models import VideoInfo
    from src.infrastructure.mcp.server import create_mcp_server
    from src.interfaces.cli import main as cli_main

    sentinels = [
        "DIAG_URL_SENTINEL",
        "DIAG_PROXY_SENTINEL",
        "DIAG_TITLE_SENTINEL",
        "DIAG_PATH_SENTINEL",
        "DIAG_RAW_ERROR_SENTINEL",
    ]

    class NetworkFailure:
        def fetch_info(self, url, settings):
            assert sentinels[1] in settings.proxy
            return VideoInfo(title=sentinels[2])

        def download(self, task, settings, progress_callback=None):
            raise RuntimeError(" ".join(sentinels))

        def cancel(self):
            pass

    logs = tmp_path / "logs"
    monkeypatch.setenv("YTDL_LOG_DIR", str(logs))
    runtime = create_runtime(
        tmp_path / "profile",
        settings_overrides={
            "output_dir": tmp_path / sentinels[3],
            "proxy": "http://DIAG_PROXY_SENTINEL:8080",
        },
        backend_factory=NetworkFailure,
    )
    window = None
    try:
        fixture_record(runtime, tmp_path, title=sentinels[2])
        with desktop._logging():
            window = MainWindow(runtime.as_services())
            qtbot.addWidget(window)
            window.show()
            window._url_input._url_edit.setText("https://www.youtube.com/watch?v=DIAG_URL_SENTINEL")
            window._url_input._add_btn.click()
            task = runtime.api.list_tasks()[0]
            assert runtime.api.wait_for_download(task.id, timeout=4).status == "failed"
            # Prior desktop-loop tests legitimately quit their QApplication loop.
            # Run an actual new bounded loop, not a nested wait inheriting its quit flag.
            gui_errors, inspected = [], []

            def inspect_terminal():
                try:
                    qapp.processEvents()
                    inspected.append(True)
                    assert (
                        window._item_widgets[task.id]._status_label.text()
                        == DownloadStatus.FAILED.display_name()
                    )
                except BaseException as error:
                    gui_errors.append(error)
                finally:
                    qapp.quit()

            QTimer.singleShot(0, inspect_terminal)
            qapp.exec()
            assert inspected == [True]
            if gui_errors:
                raise gui_errors[0]

            async def exercise():
                async with Client(create_mcp_server(runtime.api), timeout=5) as client:
                    detail = (await client.call_tool("get_download", {"id": 10})).data
                    assert (
                        detail["title"] == sentinels[2]
                    )  # Useful data is a RESULT, not diagnostic.
                    desc = (await client.call_tool("read_description", {"id": 10})).data
                    assert desc["description_text"] == "distinct owned sidecar"
                    await client.call_tool("search_downloads", {"query": sentinels[2]})
                    denied = (
                        await client.call_tool(
                            "add_download",
                            {
                                "url": "https://example.invalid/DIAG_URL_SENTINEL",
                                "quality": "invalid-quality",
                            },
                        )
                    ).data
                    assert denied["code"] == "INVALID_ARGUMENT"

            asyncio.run(exercise())
            gui_output = capsys.readouterr()
            assert gui_output.out == "" and gui_output.err
            assert all(marker not in gui_output.err for marker in sentinels)
            assert (
                cli_main(
                    ["--json", "queue", "cancel", "999", "--confirm"],
                    services=runtime.as_services(),
                )
                == 1
            )
            cli_output = capsys.readouterr()
            assert cli_output.out == "" and json.loads(cli_output.err)["code"] == "NOT_FOUND"
            assert all(marker not in cli_output.err for marker in sentinels)
        main_log = (logs / "app.log").read_text(encoding="utf-8")
        error_log = (logs / "app.error.log").read_text(encoding="utf-8")
        for sink in (main_log, error_log):
            assert sink and all(marker not in sink for marker in sentinels)
        assert "ui.add_url task_id=" in main_log and "mcp.get_download id=10" in main_log
        assert (
            "mcp.search_downloads count=" in main_log
            and "reason_code=INVALID_ARGUMENT" in error_log
        )
        (tmp_path / "sink-observation.json").write_text(
            json.dumps(
                {
                    "main_bytes": len(main_log.encode()),
                    "error_bytes": len(error_log.encode()),
                    "stderr_bytes": len(gui_output.err.encode()),
                    "cli_error_bytes": len(cli_output.err.encode()),
                    "stdout_bytes": 0,
                    "sentinels_absent": True,
                    "useful_tool_result_title_verified": True,
                }
            ),
            encoding="utf-8",
        )
    finally:
        if window is not None:
            window.cleanup()
            window.close()
        assert runtime.close(cancel=True, wait=True).closed


def test_real_partial_log_open_failure_closes_only_own_handlers(tmp_path, monkeypatch, capsys):
    import logging

    from src.interfaces.cli import main as cli_main

    root = logging.getLogger()
    previous, level = root.handlers[:], root.level
    for entry in ("cli", "desktop"):
        directory = tmp_path / entry
        (directory / "app.error.log").mkdir(
            parents=True
        )  # Actual native open refusal, no handler fake.
        monkeypatch.setenv("YTDL_LOG_DIR", str(directory))
        code = cli_main(["--json", "history", "list"]) if entry == "cli" else desktop.main()
        assert code == 1
        captured = capsys.readouterr()
        assert captured.out == "" and str(directory) not in captured.err
        assert root.handlers == previous and root.level == level
        path = directory / "app.log"
        renamed = path.with_name("closed-handler.log")
        path.rename(renamed)  # Windows rename proves the successful earlier handle really closed.
        assert renamed.is_file()


@pytest.mark.parametrize("failure_mode", ["none", "body", "cleanup"])
def test_desktop_logging_preserves_same_early_and_late_caller_handlers(
    tmp_path, monkeypatch, capsys, failure_mode
):
    import logging

    logger = logging.getLogger()
    original, level = logger.handlers[:], logger.level
    logs = tmp_path / "owned-logs"
    monkeypatch.setenv("YTDL_LOG_DIR", str(logs))
    monkeypatch.setenv("YTDL_LOG_LEVEL", "INFO")
    early = late = None
    owned, close_faults = [], []
    observation = {}
    body_error = ValueError("CONTROLLED_BODY_FAILURE")

    def record(text):
        return logging.LogRecord("caller.desktop", logging.ERROR, __file__, 0, text, (), None)

    try:
        early = logging.FileHandler(tmp_path / "caller-early.log", mode="w", encoding="utf-8")
        late = logging.FileHandler(tmp_path / "caller-late.log", mode="w", encoding="utf-8")
        early_stream, late_stream = early.stream, late.stream
        for handler in (early, late):
            handler.handle(record("before id=2"))
            handler.flush()
        logger.addHandler(early)
        caught = None
        try:
            with desktop._logging():
                owned.extend(logger.handlers)
                if failure_mode == "cleanup":
                    handler = next(h for h in owned if isinstance(h, logging.FileHandler))
                    close = handler.close

                    def close_then_fail():
                        close()
                        close_faults.append(True)
                        raise OSError("PRIVATE_OWNED_CLOSE_SENTINEL")

                    monkeypatch.setattr(handler, "close", close_then_fail)
                logger.addHandler(late)
                logger.error("caller.desktop.during id=2 reason_code=INTERNAL_ERROR")
                if failure_mode == "body":
                    raise body_error
        except Exception as error:
            caught = error
        if failure_mode == "cleanup":
            assert isinstance(caught, CommandError) and caught.code == "INTERNAL_ERROR"
            assert close_faults == [True]
        elif failure_mode == "body":
            assert caught is body_error and close_faults == []
        else:
            assert caught is None and close_faults == []
        captured = capsys.readouterr()
        assert captured.out == "" and "id=2 reason_code=INTERNAL_ERROR" in captured.err
        assert "PRIVATE_OWNED_CLOSE_SENTINEL" not in captured.err
        assert logger.level == level
        observation.update(
            {
                "boundary": "actual desktop logging context, not visual GUI",
                "failure_mode": failure_mode,
                "early_same_stream": early.stream is early_stream and not early_stream.closed,
                "late_same_stream": late.stream is late_stream and not late_stream.closed,
                "early_registered": any(h is early for h in logger.handlers),
                "late_registered": any(h is late for h in logger.handlers),
                "owned_unregistered": all(
                    all(h is not ours for h in logger.handlers) for ours in owned
                ),
                "owned_file_streams_closed": all(
                    h.stream is None for h in owned if isinstance(h, logging.FileHandler)
                ),
            }
        )
        logger.handle(record("after id=2"))
        for handler in (early, late):
            handler.flush()
        for name in ("early", "late"):
            observation[name + "_bytes"] = (tmp_path / f"caller-{name}.log").read_text(
                encoding="utf-8"
            )
        for path in logs.glob("*.log"):
            assert "id=2 reason_code=INTERNAL_ERROR" in path.read_text(encoding="utf-8")
            path.rename(path.with_suffix(".closed"))
        with desktop._logging():
            logger.error("caller.desktop.next id=3 reason_code=INTERNAL_ERROR")
        assert "next id=3" in (logs / "app.error.log").read_text(encoding="utf-8")
        logger.handle(record("after-next id=3"))
        for handler in (early, late):
            handler.flush()
        observation["next_context_useful"] = True
        observation["late_after_next_bytes"] = (tmp_path / "caller-late.log").read_text(
            encoding="utf-8"
        )
    finally:
        logger.handlers = original
        logger.setLevel(level)
        for handler in (early, late):
            if handler is not None:
                handler.close()
        (tmp_path / "logging-ownership.json").write_text(
            json.dumps(observation, indent=2), encoding="utf-8"
        )
    assert observation["early_same_stream"] and observation["early_registered"]
    assert observation["late_same_stream"] and observation["late_registered"], (
        "app._logging must retain the SAME caller-owned handler attached during the context"
    )
    assert observation["owned_unregistered"] and observation["owned_file_streams_closed"]
    assert (
        "before id=2" in observation["early_bytes"] and "after id=2" in observation["early_bytes"]
    )
    assert all(
        marker in observation["late_bytes"]
        for marker in ("before id=2", "during id=2", "after id=2")
    )
    assert (
        "before id=2" in observation["late_after_next_bytes"]
        and "after-next id=3" in observation["late_after_next_bytes"]
    )
