"""S5 real adapter/process/protocol proofs; external effects are replaced at their edges."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from queue import Queue
from threading import Event, Thread

import pytest

from src.bootstrap import create_runtime
from src.domain.models import HistoryEntry, VideoInfo
from src.domain.models.download_outcome import DownloadOutcome
from src.domain.models.download_task import DownloadStatus

PROJECT = Path(__file__).resolve().parents[1]


def child_env(root: Path, profile: Path) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    names = {
        "APPDATA": "competing-appdata",
        "LOCALAPPDATA": "local",
        "HOME": "home",
        "USERPROFILE": "home",
        "TMP": "temp",
        "TEMP": "temp",
        "TMPDIR": "temp",
        "UV_CACHE_DIR": "cache/uv",
        "RUFF_CACHE_DIR": "cache/ruff",
        "MYPY_CACHE_DIR": "cache/mypy",
        "XDG_CACHE_HOME": "cache/xdg",
        "YTDL_LOG_DIR": "logs",
        "YTDL_OUTPUT_DIR": "output",
    }
    for key, relative in names.items():
        path = root / relative
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path.resolve())
    env.update(
        {
            "YTDL_DATA_DIR": str(profile.resolve()),
            "PYTHONPATH": str(PROJECT),
            "UV_OFFLINE": "1",
            "UV_NO_SYNC": "1",
            "UV_PYTHON_DOWNLOADS": "never",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUTF8": "1",
            "QT_QPA_PLATFORM": "offscreen",
            "FASTMCP_CHECK_FOR_UPDATES": "off",
            "DO_NOT_TRACK": "1",
        }
    )
    return env


def native_cli(root: Path, profile: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", "src.interfaces.cli", *argv],
        cwd=PROJECT,
        env=child_env(root, profile),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    (root / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (root / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    (root / "native-exit.txt").write_text(str(result.returncode), encoding="utf-8")
    return result


def test_native_cli_readonly_keeps_writer_and_saved_nonterminal_snapshot(tmp_path):
    profile, output = tmp_path / "profile", tmp_path / "output"
    runtime = create_runtime(profile, settings_overrides={"output_dir": output})
    try:
        runtime.history_repo.add(
            HistoryEntry(
                id=1,
                url="https://example.invalid/saved",
                title="Saved result",
                status=DownloadStatus.DONE,
                output_root=output,
            )
        )
        runtime.history_repo.add(
            HistoryEntry(
                id=2,
                url="https://example.invalid/orphan",
                title="Saved queued",
                status=DownloadStatus.QUEUED,
                output_root=output,
            )
        )
        history = profile / "data/history.json"
        before = history.read_bytes()
        result = native_cli(tmp_path / "query-child", profile, "--json", "history", "list")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert {row["id"]: row["status"] for row in payload} == {1: "done", 2: "queued"}
        assert history.read_bytes() == before
        assert runtime.history_repo.get_by_id(2).status == DownloadStatus.QUEUED
        assert not (tmp_path / "query-child/competing-appdata/YTDownloader").exists()
        assert not result.stderr or "OWNER_BUSY" not in result.stderr
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def seed_artifacts(root: Path, *, hold: bool = False):
    profile, output = root / "profile", root / "output"
    runtime = create_runtime(profile, settings_overrides={"output_dir": output})
    try:
        folder = output / "download-1"
        folder.mkdir(parents=True)
        media, description, subtitle = (
            folder / "owned.mp4",
            folder / "owned.description",
            folder / "owned.ru.vtt",
        )
        media.write_bytes(b"owned fixture media")
        description.write_text("Owned description: distinct useful text", encoding="utf-8")
        subtitle.write_text(
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nOwned transcript line\n", encoding="utf-8"
        )
        runtime.history_repo.add(
            HistoryEntry(
                id=1,
                url="https://example.invalid/owned",
                title="Useful owned result",
                status=DownloadStatus.DONE,
                output_root=output,
                output_dir=folder,
                video_path=media,
                description_path=description,
                subtitle_paths=[subtitle],
                artifact_paths=[media, description, subtitle],
            )
        )
        return runtime if hold else profile
    finally:
        if not hold:
            assert runtime.close(cancel=False, wait=True).closed


def test_native_cli_queries_tokens_wrappers_and_exact_error_channels(tmp_path):
    profile = seed_artifacts(tmp_path / "store")
    before = (profile / "data/history.json").read_bytes()
    queries = [
        ("get", ["get", "1"], "title", "Useful owned result"),
        ("description", ["description", "1"], "description_text", "Owned description"),
        ("transcript", ["transcript", "1"], "transcript_text", "Owned transcript line"),
        ("paths", ["file-paths", "1"], "video_path", "owned.mp4"),
    ]
    for name, leaf, key, expected in queries:
        result = native_cli(
            tmp_path / name, profile, "--json", "--data-dir", str(profile), "history", *leaf
        )
        assert result.returncode == 0, result.stderr
        assert expected in json.loads(result.stdout)[key]
        assert (profile / "data/history.json").read_bytes() == before
    missing = native_cli(tmp_path / "missing", profile, "--json", "history", "get", "999")
    assert missing.returncode == 1 and missing.stdout == ""
    assert json.loads(missing.stderr)["code"] == "NOT_FOUND"
    usage = native_cli(tmp_path / "usage", profile, "history", "unknown-command")
    assert usage.returncode == 2 and usage.stdout == "" and "usage:" in usage.stderr
    for name, args in (("help", ["--help"]), ("stdio-help", ["server", "stdio", "--help"])):
        result = native_cli(tmp_path / name, profile, *args)
        assert result.returncode == 0 and "usage:" in result.stdout
    preview = native_cli(
        tmp_path / "preview",
        profile,
        "--json",
        "history",
        "delete",
        "1",
        "--keep-files",
        "--preview",
        "--confirm",
    )
    plan = json.loads(preview.stdout)
    assert preview.returncode == 0 and plan["confirmation_required"] and plan["plan_token"]
    assert (profile / "data/history.json").read_bytes() == before
    refused = native_cli(
        tmp_path / "no-token",
        profile,
        "--json",
        "history",
        "delete",
        "1",
        "--keep-files",
        "--confirm",
    )
    assert refused.returncode == 1 and refused.stdout == ""
    assert json.loads(refused.stderr)["code"] == "CONFIRMATION_REQUIRED"
    assert (profile / "data/history.json").read_bytes() == before
    applied = native_cli(
        tmp_path / "apply",
        profile,
        "--json",
        "history",
        "delete",
        "1",
        "--keep-files",
        "--confirm",
        "--plan-token",
        plan["plan_token"],
    )
    assert applied.returncode == 0 and json.loads(applied.stdout)["deleted"] is True
    with create_runtime(profile, read_only=True) as reader:
        assert reader.api.list_history_entries() == []
    assert (tmp_path / "store/output/download-1/owned.mp4").read_bytes() == b"owned fixture media"


def test_standalone_cancel_does_not_create_a_profile_or_empty_queue(tmp_path):
    profile = tmp_path / "never-created-profile"
    result = native_cli(tmp_path / "cancel", profile, "--json", "queue", "cancel", "1", "--confirm")
    assert result.returncode == 1 and result.stdout == ""
    assert json.loads(result.stderr)["code"] == "OWNER_REQUIRED"
    assert not profile.exists()


def test_native_legacy_stdio_and_http_wrapper_help_never_initializes_a_profile(tmp_path):
    for name, arguments in (
        ("stdio", ["mcp_stdio_server.py", "--help"]),
        ("http", ["-m", "src.infrastructure.mcp.server", "--help"]),
    ):
        profile = tmp_path / name / "profile"
        result = subprocess.run(
            [sys.executable, *arguments],
            cwd=PROJECT,
            env=child_env(tmp_path / name / "selectors", profile),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        assert result.returncode == 0 and "usage:" in result.stdout and "--help" in result.stdout
        assert not profile.exists()
        (tmp_path / name / "wrapper-result.json").write_text(
            json.dumps(
                {"native_exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
            ),
            encoding="utf-8",
        )


def controlled_add(root: Path, scenario: str):
    profile, control = root / "profile", root / "control"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests.adapter_child",
            scenario,
            str(control),
            "--json",
            "--data-dir",
            str(profile),
            "queue",
            "add",
            "https://example.invalid/PRIVATE_URL_SENTINEL",
        ],
        cwd=PROJECT,
        env=child_env(root / "selectors", profile),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    lines = Queue()
    reader = Thread(
        target=lambda: lines.put(process.stdout.readline()), name="acceptance-reader", daemon=False
    )
    reader.start()
    first, tail, stderr = "", "", ""
    emergency = False
    try:
        first = lines.get(timeout=10)
        acceptance = json.loads(first)
        assert acceptance == {"task_id": 1, "status": "queued"}
        assert process.poll() is None  # Acceptance is flushed while the real backend is held.
        held = native_cli(root / "while-held", profile, "--json", "history", "get", "1")
        assert held.returncode == 0
        assert json.loads(held.stdout)["status"] in {"queued", "downloading", "merging"}
        process.stdin.write("release\n")
        process.stdin.flush()
        reader.join(5)
        assert not reader.is_alive()
        tail, stderr = process.communicate(timeout=15)
    finally:
        if process.poll() is None:
            try:
                process.stdin.write("release\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass
            try:
                reader.join(5)
                leftover, error = process.communicate(timeout=15)
                tail += leftover
                stderr += error
            except subprocess.TimeoutExpired:
                emergency = True
                process.kill()  # Only the exact child created here, only failed teardown.
                process.communicate(timeout=5)
        reader.join(5)
        assert not reader.is_alive()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        (root / "stdout.txt").write_text(first + tail, encoding="utf-8")
        (root / "stderr.txt").write_text(stderr, encoding="utf-8")
        (root / "child-result.json").write_text(
            json.dumps(
                {
                    "native_exit": process.returncode,
                    "emergency_cleanup": emergency,
                    "acceptance_flushed_before_release": bool(first),
                    "reader_joined": not reader.is_alive(),
                }
            ),
            encoding="utf-8",
        )
    assert not emergency and tail == ""  # No replacement/second terminal JSON in stdout.
    return process.returncode, stderr, profile, control


@pytest.mark.parametrize(
    "scenario",
    [
        "done",
        "failed",
        "cancelled",
        pytest.param(
            "persistence",
            marks=pytest.mark.skipif(
                os.name != "nt", reason="native Windows delete-sharing refusal"
            ),
        ),
    ],
)
def test_owned_cli_acceptance_flush_terminal_exit_and_real_cleanup(tmp_path, scenario):
    code, stderr, profile, control = controlled_add(tmp_path, scenario)
    receipt = json.loads((control / "harness-release.json").read_text(encoding="utf-8"))
    assert receipt["business_facade_replaced"] is False
    assert receipt["native_storage_handles_closed"] == (1 if scenario == "persistence" else 0)
    if scenario == "done":
        assert code == 0 and stderr == ""
    else:
        assert code == 1
        failure = json.loads(stderr)
        assert failure["task_id"] == 1
        assert (
            failure["code"]
            == {
                "failed": "DOWNLOAD_FAILED",
                "cancelled": "INTERRUPTED",
                "persistence": "PERSISTENCE_FAILED",
            }[scenario]
        )
        assert (
            failure["result"]["status"]
            == {"failed": "failed", "cancelled": "cancelled", "persistence": "failed"}[scenario]
        )
        assert "PRIVATE_RAW_ERROR_SENTINEL" not in stderr and "PRIVATE_URL_SENTINEL" not in stderr
    with create_runtime(profile, read_only=True) as view:
        entry = view.history_repo.get_by_id(1)
        if scenario == "persistence":
            assert entry.status != DownloadStatus.DONE
        else:
            assert (
                entry.status.value
                == {"done": "done", "failed": "failed", "cancelled": "cancelled"}[scenario]
            )
    # The OS lease really released; the next writer can acquire/recover, without media cleanup.
    with create_runtime(profile) as next_owner:
        assert next_owner.api.get_settings() is not None
    media = list((tmp_path / "selectors/home/Downloads/YTDownloader/download-1").glob("*.mp4"))
    assert len(media) == 1 and media[0].read_bytes() == b"owned-cli-media-1"


def test_real_stdio_tools_confirmation_keep_files_and_graceful_child_exit(tmp_path, monkeypatch):
    import anyio
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    from src.infrastructure.mcp.manifest import EXPECTED_MCP_TOOL_SET

    profile = seed_artifacts(tmp_path / "store")
    history = profile / "data/history.json"
    before = history.read_bytes()
    processes = []
    open_process = anyio.open_process

    async def observe_process(*args, **kwargs):
        process = await open_process(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(anyio, "open_process", observe_process)
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "src.interfaces.cli", "--data-dir", str(profile), "server", "stdio"],
        env=child_env(tmp_path / "stdio-selectors", profile),
        cwd=str(PROJECT),
        keep_alive=False,
        log_file=tmp_path / "stdio-stderr.txt",
    )

    async def exercise():
        with anyio.fail_after(25):
            async with Client(transport, timeout=5) as client:
                assert {t.name for t in await client.list_tools()} == EXPECTED_MCP_TOOL_SET
                listed = await client.call_tool("list_downloads")
                # Read the actual protocol payload, not SDK-generated schema dataclass items.
                assert not listed.is_error and set(listed.structured_content) == {"result"}
                rows = listed.structured_content["result"]
                assert len(rows) == 1 and rows[0]["id"] == 1
                detail = (await client.call_tool("get_download", {"id": 1})).data
                assert detail["title"] == "Useful owned result"
                description = (await client.call_tool("read_description", {"id": 1})).data
                assert "distinct useful text" in description["description_text"]
                missing = (await client.call_tool("get_download", {"id": 999})).data
                assert missing["code"] == "NOT_FOUND"
                preview = (
                    await client.call_tool("delete_download", {"id": 1, "delete_files": False})
                ).data
                assert preview["confirmation_required"] and preview["plan_token"]
                assert history.read_bytes() == before
                refused = (
                    await client.call_tool(
                        "delete_download", {"id": 1, "delete_files": False, "confirm": True}
                    )
                ).data
                assert refused["code"] == "CONFIRMATION_REQUIRED" and history.read_bytes() == before
                done = (
                    await client.call_tool(
                        "delete_download",
                        {
                            "id": 1,
                            "delete_files": False,
                            "confirm": True,
                            "plan_token": preview["plan_token"],
                        },
                    )
                ).data
                assert done["deleted"] and not done["files_removed"]

    async def managed_exercise():
        try:
            await exercise()
        finally:
            await transport.close()

    asyncio.run(managed_exercise())
    assert len(processes) == 1 and processes[0].returncode == 0
    (tmp_path / "stdio-process.json").write_text(
        json.dumps(
            {"pid": processes[0].pid, "native_exit": processes[0].returncode, "real_protocol": True}
        ),
        encoding="utf-8",
    )
    with create_runtime(profile) as reopened:
        assert reopened.api.list_history_entries() == []
    assert (tmp_path / "store/output/download-1/owned.mp4").read_bytes() == b"owned fixture media"


class GateEdge:
    def __init__(self, entered, release):
        self.entered, self.release = entered, release

    def fetch_info(self, url, settings):
        self.entered.set()
        assert self.release.wait(8)
        return VideoInfo(title="Actual bridge result")

    def cancel(self):
        pass

    def download(self, task, settings, progress_callback=None):
        folder = settings.output_dir / f"download-{task.id}"
        folder.mkdir(parents=True, exist_ok=True)
        media = folder / "owned.mp4"
        media.write_bytes(f"owned bridge media {task.id}".encode())
        return DownloadOutcome.from_paths({"video": media, "scan_root": folder})


def test_managed_http_one_owner_disconnect_intent_quiescence_and_port_reuse(tmp_path):
    from fastmcp import Client

    from src.infrastructure.mcp.server import HTTPServerHandle

    entered, release = Event(), Event()
    runtime = create_runtime(
        tmp_path / "profile",
        settings_overrides={"output_dir": tmp_path / "output"},
        backend_factory=lambda: GateEdge(entered, release),
    )
    handle = None
    try:
        handle = HTTPServerHandle(runtime.as_services(), port=0).start()
        port = handle.port

        async def add_and_disconnect():
            async with Client(handle.endpoint, timeout=5) as client:
                accepted = (
                    await client.call_tool(
                        "add_download", {"url": "https://example.invalid/http-owned"}
                    )
                ).data
                assert accepted["task_id"] == 1 and accepted["status"] == "queued"
                assert entered.wait(3)
                detail = (await client.call_tool("get_download", {"id": 1})).data
                assert detail["status"] in {"queued", "downloading"}

        asyncio.run(add_and_disconnect())
        assert not runtime.api.get_task(1).cancel_requested
        assert runtime.api.get_task(1).status not in {"done", "cancelled", "failed"}

        async def cancel():
            async with Client(handle.endpoint, timeout=5) as client:
                result = (
                    await client.call_tool("cancel_download", {"id": 1, "confirm": True})
                ).data
                assert result == {"id": 1, "status": "cancel_requested"}

        asyncio.run(cancel())
        snapshot = runtime.api.get_task(1)
        assert snapshot.cancel_requested and snapshot.status not in {"cancelled", "done", "failed"}
        release.set()
        assert runtime.api.wait_for_download(1, timeout=4).status == "cancelled"
        assert handle.close(timeout=5) and handle.closed and not handle.thread.is_alive()
        assert handle.close(timeout=5)
        with socket.socket() as reusable:
            reusable.bind(("127.0.0.1", port))
        assert not runtime.closed  # Listener borrowed, never closes its application owner.
        next_task = runtime.api.queue_add_download(url="https://example.invalid/next-owned")
        assert runtime.api.wait_for_download(next_task.task_id, timeout=4).status == "done"
        with create_runtime(runtime.data_root, read_only=True) as view:
            assert (
                view.history_repo.get_by_id(next_task.task_id).video_path.read_bytes()
                == b"owned bridge media 2"
            )
    finally:
        release.set()
        if handle is not None:
            assert handle.close(timeout=8)
        assert runtime.close(cancel=True, wait=True).closed


def test_borrowed_cli_returns_acceptance_without_waiting_or_closing_owner(tmp_path, capsys):
    from src.interfaces.cli import main

    entered, release = Event(), Event()
    runtime = create_runtime(
        tmp_path / "profile",
        settings_overrides={"output_dir": tmp_path / "output"},
        backend_factory=lambda: GateEdge(entered, release),
    )
    try:
        assert (
            main(
                ["--json", "queue", "add", "https://example.invalid/borrowed"],
                services=runtime.as_services(),
            )
            == 0
        )
        assert json.loads(capsys.readouterr().out) == {"task_id": 1, "status": "queued"}
        assert entered.wait(3) and not runtime.closed
        assert runtime.api.get_task(1).status not in {"done", "cancelled", "failed"}
        release.set()
        assert runtime.api.wait_for_download(1, timeout=4).status == "done"
        assert runtime.api.get_settings() is not None
    finally:
        release.set()
        assert runtime.close(cancel=True, wait=True).closed


def test_owned_stdio_eof_cancels_and_persists_before_native_zero_exit(tmp_path, monkeypatch):
    import anyio
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    profile, control = tmp_path / "profile", tmp_path / "control"
    processes = []
    open_process = anyio.open_process

    async def observe(*args, **kwargs):
        process = await open_process(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(anyio, "open_process", observe)
    transport = StdioTransport(
        command=sys.executable,
        args=[
            "-m",
            "tests.adapter_child",
            "stdio-owned",
            str(control),
            "--data-dir",
            str(profile),
            "server",
            "stdio",
        ],
        env=child_env(tmp_path / "selectors", profile),
        cwd=str(PROJECT),
        keep_alive=False,
        log_file=tmp_path / "stdio-stderr.txt",
    )

    async def exercise():
        try:
            async with Client(transport, timeout=5) as client:
                accepted = (
                    await client.call_tool(
                        "add_download", {"url": "https://example.invalid/owned-stdio"}
                    )
                ).data
                assert accepted["task_id"] == 1
                with anyio.fail_after(4):
                    while not (control / "backend-entered.json").exists():
                        await anyio.sleep(0.01)
                current = (await client.call_tool("get_download", {"id": 1})).data
                assert current["status"] not in {"done", "failed", "cancelled"}
        finally:
            await transport.close()

    asyncio.run(exercise())
    assert len(processes) == 1 and processes[0].returncode == 0
    assert (
        json.loads((control / "harness-release.json").read_text(encoding="utf-8"))[
            "business_facade_replaced"
        ]
        is False
    )
    with create_runtime(profile, read_only=True) as reader:
        entry = reader.history_repo.get_by_id(1)
        assert entry.status == DownloadStatus.CANCELLED
        assert entry.video_path.read_bytes() == b"owned-cli-media-1"
    with create_runtime(profile) as next_owner:
        assert next_owner.api.get_settings() is not None
    (tmp_path / "stdio-exit.json").write_text(
        json.dumps(
            {
                "pid": processes[0].pid,
                "native_exit": processes[0].returncode,
                "terminal_saved": "cancelled",
            }
        ),
        encoding="utf-8",
    )


def test_managed_http_bind_failure_leaves_foreign_listener_and_borrowed_owner_usable(tmp_path):
    from src.application.command_api import CommandError
    from src.infrastructure.mcp.server import HTTPServerHandle

    runtime = create_runtime(tmp_path / "profile")
    handle = None
    try:
        with socket.socket() as foreign:
            foreign.bind(("127.0.0.1", 0))
            foreign.listen()
            port = foreign.getsockname()[1]
            handle = HTTPServerHandle(runtime.as_services(), port=port)
            with pytest.raises(CommandError) as denied:
                handle.start()
            assert (
                denied.value.code == "EXECUTION_UNAVAILABLE"
                and denied.value.result["stage"] == "bind"
            )
            assert handle.closed and handle.thread is None and not runtime.closed
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                connection, _ = foreign.accept()
                connection.close()
            assert foreign.getsockname()[1] == port
        assert runtime.api.get_settings() is not None
    finally:
        if handle is not None:
            assert handle.close(timeout=5)
        assert runtime.close(cancel=False, wait=True).closed


def test_mcp_partial_result_is_real_moved_bytes_and_retained_history(tmp_path):
    from fastmcp import Client

    from src.infrastructure.mcp.server import create_mcp_server

    moved = []

    class Trash:
        def move_to_trash(self, path):
            if moved:
                raise OSError("PRIVATE_RAW_ERROR_SENTINEL")
            target = tmp_path / ("recoverable-" + path.name)
            path.rename(target)
            moved.append((path, target))
            return True

        def close(self):
            pass

    runtime = create_runtime(
        tmp_path / "profile",
        settings_overrides={"output_dir": tmp_path / "output"},
        file_remover_factory=Trash,
    )
    try:
        folder = tmp_path / "output/download-1"
        folder.mkdir(parents=True)
        files = [folder / "a.media", folder / "b.sidecar"]
        for index, path in enumerate(files):
            path.write_bytes(f"partial-byte-{index}".encode())
        runtime.history_repo.add(
            HistoryEntry(
                id=1,
                url="https://example.invalid/partial",
                title="Partial",
                status=DownloadStatus.DONE,
                output_root=tmp_path / "output",
                output_dir=folder,
                artifact_paths=files,
            )
        )
        before = (runtime.data_root / "data/history.json").read_bytes()
        server = create_mcp_server(runtime.api)

        async def exercise():
            async with Client(server, timeout=5) as client:
                preview = (await client.call_tool("delete_download", {"id": 1})).data
                result = (
                    await client.call_tool(
                        "delete_download",
                        {"id": 1, "confirm": True, "plan_token": preview["plan_token"]},
                    )
                ).data
                assert result["code"] == "PARTIAL_DELETE" and result["result"]["moved_count"] == 1
                assert result["result"]["history_deleted"] is False
                assert "PRIVATE_RAW_ERROR_SENTINEL" not in json.dumps(result)

        asyncio.run(exercise())
        assert (
            moved[0][1].read_bytes() == b"partial-byte-0"
            and files[1].read_bytes() == b"partial-byte-1"
        )
        assert (runtime.data_root / "data/history.json").read_bytes() == before
        assert runtime.api.get_download(1).id == 1
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_native_readonly_absent_and_corrupt_profiles_never_write_or_leak(tmp_path):
    absent = tmp_path / "absent-profile"
    env = child_env(tmp_path / "readonly-selectors", absent)
    env.pop("YTDL_LOG_DIR")
    result = subprocess.run(
        [sys.executable, "-m", "src.interfaces.cli", "--json", "history", "list"],
        cwd=PROJECT,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0 and json.loads(result.stdout) == [] and result.stderr == ""
    assert not absent.exists()
    corrupt = tmp_path / "corrupt-profile"
    (corrupt / "data").mkdir(parents=True)
    history = corrupt / "data/history.json"
    history.write_bytes(b'{"PRIVATE_RAW_ERROR_SENTINEL"')
    before = {p.relative_to(corrupt) for p in corrupt.rglob("*")}
    result = native_cli(tmp_path / "corrupt-child", corrupt, "--json", "history", "list")
    assert result.returncode == 1 and result.stdout == ""
    assert json.loads(result.stderr)["code"] == "STORAGE_CORRUPT"
    assert "PRIVATE_RAW_ERROR_SENTINEL" not in result.stderr and str(corrupt) not in result.stderr
    assert history.read_bytes() == b'{"PRIVATE_RAW_ERROR_SENTINEL"'
    assert {p.relative_to(corrupt) for p in corrupt.rglob("*")} == before


def test_inprocess_mcp_add_cancel_shares_the_borrowed_application_owner(tmp_path):
    from fastmcp import Client

    from src.infrastructure.mcp.server import create_mcp_server

    entered, release = Event(), Event()
    runtime = create_runtime(
        tmp_path / "profile",
        settings_overrides={"output_dir": tmp_path / "output"},
        backend_factory=lambda: GateEdge(entered, release),
    )
    try:

        async def exercise():
            async with Client(create_mcp_server(runtime.as_services()), timeout=5) as client:
                accepted = (
                    await client.call_tool(
                        "add_download", {"url": "https://example.invalid/inprocess"}
                    )
                ).data
                assert accepted["task_id"] == 1 and entered.wait(3)
                intent = (
                    await client.call_tool("cancel_download", {"id": 1, "confirm": True})
                ).data
                assert intent["status"] == "cancel_requested"
                assert runtime.api.get_task(1).cancel_requested
                assert runtime.api.get_task(1).status not in {"done", "failed", "cancelled"}

        asyncio.run(exercise())
        assert not runtime.closed
        release.set()
        assert runtime.api.wait_for_download(1, timeout=4).status == "cancelled"
        with create_runtime(runtime.data_root, read_only=True) as view:
            assert view.history_repo.get_by_id(1).status == DownloadStatus.CANCELLED
    finally:
        release.set()
        assert runtime.close(cancel=True, wait=True).closed


def test_partial_http_startup_releases_bound_socket_without_closing_owner(tmp_path, monkeypatch):
    from src.application.command_api import CommandError
    from src.infrastructure.mcp.server import HTTPServerHandle

    entered, release = Event(), Event()
    release.set()
    runtime = create_runtime(
        tmp_path / "profile",
        settings_overrides={"output_dir": tmp_path / "output"},
        backend_factory=lambda: GateEdge(entered, release),
    )
    handle = None
    try:
        handle = HTTPServerHandle(runtime.as_services(), port=0)

        def fail_at_sdk_boundary(*args, **kwargs):
            raise RuntimeError("PRIVATE_HTTP_STARTUP_SENTINEL")

        monkeypatch.setattr(handle.mcp, "http_app", fail_at_sdk_boundary)
        with pytest.raises(CommandError) as denied:
            handle.start()
        assert (
            denied.value.code == "EXECUTION_UNAVAILABLE"
            and denied.value.result["stage"] == "startup"
        )
        assert handle.closed and handle.thread is None and not runtime.closed
        assert "PRIVATE_HTTP_STARTUP_SENTINEL" not in str(denied.value)
        with socket.socket() as reusable:
            reusable.bind(("127.0.0.1", handle.port))
        task = runtime.api.queue_add_download(url="https://example.invalid/still-usable")
        assert runtime.api.wait_for_download(task.task_id, timeout=4).status == "done"
        assert handle.close() and handle.close()
    finally:
        release.set()
        if handle is not None:
            assert handle.close(timeout=5)
        assert runtime.close(cancel=True, wait=True).closed


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_borrowed_cli_preserves_early_and_queued_late_caller_handlers(
    tmp_path, monkeypatch, capsys, cleanup_failure
):
    import logging

    from src.interfaces.cli import main

    logger = logging.getLogger()
    original, level = logger.handlers[:], logger.level
    logs = tmp_path / "owned-logs"
    monkeypatch.setenv("YTDL_LOG_DIR", str(logs))
    monkeypatch.setenv("YTDL_LOG_LEVEL", "INFO")
    entered, release = Event(), Event()
    runtime = None
    early = late = None
    owned, callback_ran, close_faults = [], [], []
    observation = {}

    def record(text):
        return logging.LogRecord("caller.ownership", logging.ERROR, __file__, 0, text, (), None)

    def attach_late(**_):
        owned.extend(logger.handlers)
        if cleanup_failure:
            handler = next(h for h in owned if isinstance(h, logging.FileHandler))
            close = handler.close

            def close_then_fail():
                close()  # Actual owned OS handle is closed even on the controlled failure.
                close_faults.append(True)
                raise OSError("PRIVATE_OWNED_CLOSE_SENTINEL")

            monkeypatch.setattr(handler, "close", close_then_fail)
        logger.addHandler(late)  # Real caller subscriber to the genuine queued event.
        logger.handle(record("during id=1"))
        callback_ran.append(True)

    try:
        early = logging.FileHandler(tmp_path / "caller-early.log", mode="w", encoding="utf-8")
        late = logging.FileHandler(tmp_path / "caller-late.log", mode="w", encoding="utf-8")
        early_stream, late_stream = early.stream, late.stream
        for handler in (early, late):
            handler.handle(record("before id=1"))
            handler.flush()
        logger.addHandler(early)
        runtime = create_runtime(
            tmp_path / "profile",
            settings_overrides={"output_dir": tmp_path / "output"},
            backend_factory=lambda: GateEdge(entered, release),
        )
        runtime.event_bus.subscribe("download.queued", attach_late)
        code = main(
            ["--json", "queue", "add", "https://example.invalid/owned-r1"],
            services=runtime.as_services(),
        )
        output = capsys.readouterr()
        assert json.loads(output.out) == {"task_id": 1, "status": "queued"}
        assert code == int(cleanup_failure) and callback_ran == [True]
        if cleanup_failure:
            assert json.loads(output.err)["code"] == "INTERNAL_ERROR"
            assert "PRIVATE_OWNED_CLOSE_SENTINEL" not in output.err
            assert close_faults == [True]
        else:
            assert output.err == "" and close_faults == []
        assert entered.wait(3) and not runtime.closed and logger.level == level
        runtime.event_bus.unsubscribe("download.queued", attach_late)
        observation.update(
            {
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
                "cli_exit": code,
                "cleanup_failure": cleanup_failure,
            }
        )
        logger.handle(record("after id=1"))
        for handler in (early, late):
            handler.flush()
        for name in ("early", "late"):
            observation[name + "_bytes"] = (tmp_path / f"caller-{name}.log").read_text(
                encoding="utf-8"
            )
        release.set()
        terminal = runtime.api.wait_for_download(1, timeout=4)
        assert terminal.status == "done" and terminal.result_persisted
        assert Path(terminal.artifact_paths[0]).read_bytes() == b"owned bridge media 1"
        following = runtime.api.queue_add_download(url="https://example.invalid/following-r1")
        assert runtime.api.wait_for_download(following.task_id, timeout=4).result_persisted
        assert (
            runtime.history_repo.get_by_id(following.task_id).video_path.read_bytes()
            == b"owned bridge media 2"
        )
        observation["useful_terminal"] = "done/persisted + following real job"
        for path in logs.glob("*.log"):
            assert path.read_bytes()
            path.rename(path.with_suffix(".closed"))  # Actual owned file handles released.
    finally:
        release.set()
        if runtime is not None:
            runtime.event_bus.unsubscribe("download.queued", attach_late)
            assert runtime.close(cancel=True, wait=True).closed
            with create_runtime(tmp_path / "profile", read_only=True) as view:
                assert len(view.api.list_history_entries()) == 2
            with create_runtime(tmp_path / "profile") as next_owner:
                assert next_owner.api.get_settings() is not None
            observation["runtime_closed_and_reopened"] = True
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
        "CLI must retain the SAME caller-owned handler attached during the real queued event"
    )
    assert observation["owned_unregistered"] and observation["owned_file_streams_closed"]
    assert (
        "before id=1" in observation["early_bytes"] and "after id=1" in observation["early_bytes"]
    )
    assert all(
        marker in observation["late_bytes"]
        for marker in ("before id=1", "during id=1", "after id=1")
    )
