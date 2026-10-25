"""Exercise a relocated console bundle through native public commands, never a fake CLI.

The only source Application API usage prepares explicitly labelled synthetic stores,
closed before the EXE runs. Network use is strictly this runner's tiny loopback server.
External YouTube, user profiles, GUI and restoration/bin inspection are not performed.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import hashlib
import json
import os
import socket
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LEAVES = (
    "queue add",
    "queue cancel",
    "history list",
    "history get",
    "history search",
    "history transcript",
    "history description",
    "history file-paths",
    "history delete",
    "server stdio",
    "server http",
)


def native_environment(root: Path, profile: Path) -> dict[str, str]:
    """Windows essentials plus owned selectors; no dev/Python/FFmpeg PATH assistance."""
    env = {
        k: os.environ[k]
        for k in (
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "SYSTEMDRIVE",
            "OS",
            "PROCESSOR_ARCHITECTURE",
            "NUMBER_OF_PROCESSORS",
        )
        if k in os.environ
    }
    windows = Path(env.get("SYSTEMROOT", r"C:\Windows"))
    env["PATH"] = os.pathsep.join(str(p) for p in (windows / "System32", windows))
    for key, relative in {
        "APPDATA": "appdata",
        "LOCALAPPDATA": "local",
        "HOME": "home",
        "USERPROFILE": "home",
        "TMP": "temp",
        "TEMP": "temp",
        "TMPDIR": "temp",
        "XDG_CONFIG_HOME": "config",
        "XDG_DATA_HOME": "xdg-data",
        "XDG_CACHE_HOME": "cache",
        "YTDL_LOG_DIR": "logs",
        "YTDL_SMOKE_ROOT": "smokes",
        "UV_CACHE_DIR": "cache/uv",
        "RUFF_CACHE_DIR": "cache/ruff",
        "MYPY_CACHE_DIR": "cache/mypy",
    }.items():
        p = root / relative
        p.mkdir(parents=True, exist_ok=True)
        env[key] = str(p.resolve())
    home = (root / "home").resolve()
    env["HOMEDRIVE"] = home.drive
    env["HOMEPATH"] = str(home)[len(home.drive) :]
    (root / "home/Downloads/YTDownloader").mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "YTDL_DATA_DIR": str(profile.resolve()),
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "QT_QPA_PLATFORM": "offscreen",
            "FASTMCP_CHECK_FOR_UPDATES": "off",
            "DO_NOT_TRACK": "1",
            "UV_OFFLINE": "1",
            "UV_NO_SYNC": "1",
            "NO_PROXY": "127.0.0.1,localhost",
            "HTTP_PROXY": "",
            "HTTPS_PROXY": "",
            "ALL_PROXY": "",
            "UV_PYTHON_DOWNLOADS": "never",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
    )
    assert not any(
        k in env
        for k in (
            "PYTHONPATH",
            "PYTHONHOME",
            "VIRTUAL_ENV",
            "YTDL_FFMPEG_PATH",
            "YTDL_FFPROBE_PATH",
        )
    )
    return env


def seed_profile(profile: Path, root: Path) -> dict[int, Path]:
    # Preparation only. No owner from this function survives into native CLI use.
    from dataclasses import replace

    from src.bootstrap import create_runtime
    from src.domain.models import HistoryEntry
    from src.domain.models.download_task import DownloadStatus

    output = root / "seed-output"
    output.mkdir(parents=True)
    media = output / "owned.media"
    description = output / "owned.description"
    transcript = output / "owned.en.vtt"
    media.write_bytes(b"distinct sidecar-query fixture, not downloaded codec media")
    description.write_text("Distinct CLI description", encoding="utf-8")
    transcript.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nDistinct CLI transcript\n",
        encoding="utf-8",
    )
    trash = output / "tiny-trash-candidate.bin"
    trash.write_bytes(b"owned native trash candidate")
    with create_runtime(profile) as owner:
        owner.api.update_settings(replace(owner.api.get_settings(), output_dir=output))
        for identity, title, status in [
            (7, "Owned CLI result", DownloadStatus.DONE),
            (8, "Owned failed result", DownloadStatus.FAILED),
            (9, "Owned keep result", DownloadStatus.DONE),
            (10, "Owned trash result", DownloadStatus.DONE),
            (11, "Owned missing result", DownloadStatus.DONE),
        ]:
            paths = (
                [media, description, transcript]
                if identity == 7
                else (
                    [trash]
                    if identity == 10
                    else [output / "recorded-but-missing.bin"]
                    if identity == 11
                    else []
                )
            )
            owner.history_repo.add(
                HistoryEntry(
                    id=identity,
                    url=f"https://example.invalid/owned-cli-{identity}",
                    title=title,
                    status=status,
                    output_dir=output,
                    output_root=output,
                    artifact_paths=paths,
                    video_path=media if identity == 7 else trash if identity == 10 else None,
                    description_path=description if identity == 7 else None,
                    subtitle_paths=[transcript] if identity == 7 else [],
                    created_at=datetime(2026, 1, identity),
                )
            )
    return {7: media, 10: trash}


class NativeProof:
    def __init__(self, exe: Path, root: Path):
        self.exe, self.root = exe.resolve(), root.resolve()
        self.cwd = self.root / "external cwd"
        self.cwd.mkdir()
        self.rows: list[dict] = []
        self.boundaries: list[dict] = []

    def env(self, profile: Path) -> dict[str, str]:
        return native_environment(self.root / "contexts" / profile.name, profile)

    def call(self, label, args, profile, *, expected=0, json_output=True, cwd=None):
        command = [str(self.exe)] + (["--json"] if json_output else [])
        command += ["--data-dir", str(profile), *args]
        return self.raw(label, command, profile, expected=expected, cwd=cwd)

    def raw(self, label, command, profile, *, expected=0, cwd=None):
        directory = self.root / "commands" / label
        directory.mkdir(parents=True, exist_ok=False)
        env = self.env(profile)
        process = subprocess.Popen(
            command,
            cwd=cwd or self.cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = process.communicate(timeout=25)
        except BaseException:
            process.kill()  # Only this owned child, timeout remains a failure.
            process.communicate(timeout=5)
            raise
        (directory / "stdout.bin").write_bytes(stdout)
        (directory / "stderr.bin").write_bytes(stderr)
        row = {
            "label": label,
            "argv": command,
            "cwd": str(cwd or self.cwd),
            "pid": process.pid,
            "native_exit": process.returncode,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "sanitized_env": env,
            "expected_exit": expected,
        }
        self.rows.append(row)
        (directory / "receipt.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
        acceptable = (expected,) if isinstance(expected, int) else expected
        assert process.returncode in acceptable, (
            label,
            process.returncode,
            stderr.decode(errors="replace"),
        )
        assert b"Traceback" not in stderr and b"[PYI-" not in stderr
        text = stdout.decode("utf-8")
        if process.returncode == 1:
            error = json.loads(stderr)
            assert "code" in error and isinstance(error["error"], str) and error["error"]
            if stdout:
                # Owned add accepts once before a later genuine transfer failure.
                accepted = json.loads(stdout)
                assert "queue" in command and "add" in command
                assert accepted["task_id"] == error["task_id"]
            return error
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def queries_and_refusals(self):
        profile = self.root / "seeded-profile"
        files = seed_profile(profile, self.root)
        store = profile / "data/history.json"
        saved = store.read_bytes()
        for group in [[], ["queue"], ["history"], ["server"]] + [x.split() for x in LEAVES]:
            value = self.call(
                "help-" + ("-".join(group) or "root"),
                [*group, "--help"],
                profile,
                json_output=False,
            )
            assert "usage:" in value and "ytdl" in value
        absent = self.root / "absent-profile"
        assert self.call("absent-readonly", ["history", "list"], absent) == []
        assert not absent.exists()
        rows = self.call("list", ["history", "list"], profile)
        assert len(rows) == 5 and {r["id"] for r in rows} == {7, 8, 9, 10, 11}
        filtered = self.call(
            "list-status-limit", ["history", "list", "--status", "done", "--limit", "1"], profile
        )
        assert len(filtered) == 1 and filtered[0]["id"] == 11
        detail = self.call("get", ["history", "get", "7"], profile)
        assert detail["title"] == "Owned CLI result" and detail["video_path"] == str(files[7])
        other_cwd = self.root / "another external cwd"
        other_cwd.mkdir()
        assert self.call("reopen", ["history", "get", "7"], profile, cwd=other_cwd) == detail
        for fmt in ("pretty", "text"):
            rendered = self.call(
                "get-" + fmt, ["history", "get", "7", "--format", fmt], profile, json_output=False
            )
            assert "Owned CLI result" in str(rendered)
        for fmt in ("table", "text"):
            text = self.call(
                "list-" + fmt, ["history", "list", "--format", fmt], profile, json_output=False
            )
            assert "Owned CLI result" in text
        assert (
            self.call(
                "search-description",
                ["history", "search", "Owned CLI", "--with-description"],
                profile,
            )[0]["description_text"]
            == "Distinct CLI description"
        )
        assert (
            self.call("search-empty", ["history", "search", "no-matching-own-marker"], profile)
            == []
        )
        assert self.call("paths", ["history", "file-paths", "7"], profile)["video_path"] == str(
            files[7]
        )
        assert (
            self.call("description", ["history", "description", "7"], profile)["description_text"]
            == "Distinct CLI description"
        )
        clean = self.call("transcript", ["history", "transcript", "7", "--lang", "en"], profile)
        assert (
            "Distinct CLI transcript" in clean["transcript_text"]
            and "WEBVTT" not in clean["transcript_text"]
        )
        raw = self.call("transcript-raw", ["history", "transcript", "7", "--raw"], profile)
        assert raw["transcript_text"].startswith("WEBVTT")
        timed = self.call(
            "transcript-timestamps", ["history", "transcript", "7", "--timestamps"], profile
        )
        assert "00:00" in timed["transcript_text"]
        for leaf in ("get", "file-paths", "description", "transcript"):
            error = self.call(
                "missing-" + leaf, ["history", leaf, "2147483001"], profile, expected=1
            )
            # Existing sidecar query DTOs intentionally retain their legacy null code.
            # Check the exact domain payload, not an invented uniform error schema.
            assert error == {
                "error": "Download #2147483001 not found",
                "hint": "Use list_downloads() to see valid IDs",
                "code": "NOT_FOUND" if leaf in ("get", "file-paths") else None,
            }
        assert (
            self.call("invalid-id", ["history", "get", "0"], profile, expected=1)["code"]
            == "INVALID_ARGUMENT"
        )
        for flag in ("--preview", "--confirm"):
            cancellation = self.root / ("cancel-" + flag[2:])
            error = self.call(
                "cancel-" + flag[2:],
                ["queue", "cancel", "2147483001", flag],
                cancellation,
                expected=1,
            )
            assert error["code"] == "OWNER_REQUIRED" and not cancellation.exists()
        self.call("usage-error", ["history", "get", "not-an-int"], profile, expected=2)
        assert store.read_bytes() == saved and files[7].read_bytes().startswith(b"distinct")
        assert self.call("next-useful-query", ["history", "get", "7"], profile) == detail
        self.deletions(profile, files)

    def deletions(self, profile, files):
        store = profile / "data/history.json"
        before = store.read_bytes()
        plan = self.call(
            "delete-keep-preview", ["history", "delete", "9", "--keep-files", "--preview"], profile
        )
        assert plan["plan_token"] and plan["confirmation_required"]
        self.call(
            "delete-forced-preview",
            ["history", "delete", "9", "--keep-files", "--preview", "--confirm"],
            profile,
        )
        assert store.read_bytes() == before
        assert (
            self.call(
                "delete-no-token",
                ["history", "delete", "9", "--keep-files", "--confirm"],
                profile,
                expected=1,
            )["code"]
            == "CONFIRMATION_REQUIRED"
        )
        kept = self.call(
            "delete-keep",
            [
                "history",
                "delete",
                "9",
                "--keep-files",
                "--confirm",
                "--plan-token",
                plan["plan_token"],
            ],
            profile,
        )
        assert kept["deleted"] and not kept["files_removed"]
        assert (
            self.call(
                "delete-replay",
                [
                    "history",
                    "delete",
                    "9",
                    "--keep-files",
                    "--confirm",
                    "--plan-token",
                    plan["plan_token"],
                ],
                profile,
                expected=1,
            )["code"]
            == "NOT_FOUND"
        )
        plan = self.call(
            "delete-file-preview",
            ["history", "delete", "10", "--delete-files", "--preview"],
            profile,
        )
        files[10].write_bytes(b"owned native trash candidate changed identity facts")
        before = store.read_bytes()
        assert (
            self.call(
                "delete-stale",
                ["history", "delete", "10", "--confirm", "--plan-token", plan["plan_token"]],
                profile,
                expected=1,
            )["code"]
            == "STALE_PLAN"
        )
        assert files[10].exists() and store.read_bytes() == before
        plan = self.call("delete-file-repreview", ["history", "delete", "10", "--preview"], profile)
        # Actual OS edge, only this tiny own file. No bin enumeration/restore experiment.
        result = self.call(
            "delete-file-native",
            ["history", "delete", "10", "--confirm", "--plan-token", plan["plan_token"]],
            profile,
            expected=(0, 1),
        )
        if "error" in result:
            # A native unknown outcome is NOT successful deletion. Keep its exact
            # result and retained history visible; never retry or inspect the bin.
            assert result["code"] == "PARTIAL_DELETE"
            detail = result["result"]
            assert not detail["history_deleted"] and detail["unknown_count"] == 1
            assert detail["moved_count"] == detail["failed_count"] == 0
            assert detail["files"][0]["code"] == "TRASH_UNAVAILABLE"
            assert store.read_bytes() == before
            assert (
                self.call("trash-retained-history", ["history", "get", "10"], profile)["id"] == 10
            )
            self.boundaries.append(
                {
                    "operation": "native Trash",
                    "effect": "unknown",
                    "native_exit": 1,
                    "result": result,
                    "source_exists_after": files[10].exists(),
                    "bin_inspection_or_restore": "NOT_RUN",
                }
            )
        else:
            assert result["deleted"] and result["files_removed"] and not files[10].exists()
        assert files[7].exists() and files[7].parent.exists()
        plan = self.call(
            "delete-recorded-missing-preview", ["history", "delete", "11", "--preview"], profile
        )
        missing = self.call(
            "delete-recorded-missing",
            ["history", "delete", "11", "--confirm", "--plan-token", plan["plan_token"]],
            profile,
        )
        assert missing["deleted"] and not missing["files_removed"]
        assert self.call("after-deletions", ["history", "get", "7"], profile)["id"] == 7

    def media(self):
        binary = self.exe.parent / "vendor/ffmpeg/bin/ffmpeg.exe"
        probe = binary.with_name("ffprobe.exe")
        profile = self.root / "media-profile"
        self.raw("bundled-ffmpeg", [str(binary), "-version"], profile)
        self.raw("bundled-ffprobe", [str(probe), "-version"], profile)
        fixture = self.root / "fixture.mp4"
        self.raw(
            "generate-tiny-media",
            [
                str(binary),
                "-v",
                "error",
                "-n",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=320x180:rate=12",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=44100",
                "-t",
                "1",
                "-c:v",
                "mpeg4",
                "-q:v",
                "5",
                "-c:a",
                "aac",
                str(fixture),
            ],
            profile,
        )
        payload = fixture.read_bytes()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_HEAD(self):
                self.do_GET(head=True)

            def do_GET(self, head=False):
                if self.path != "/fixture.mp4":
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if not head:
                    self.wfile.write(payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, name="owned-fixture-http")
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/fixture.mp4"
            for kind, quality in (("video", "720p"), ("audio", "audio")):
                owned = self.root / ("download-" + kind)
                accepted = self.call(
                    "download-" + kind,
                    [
                        "queue",
                        "add",
                        url,
                        "--quality",
                        quality,
                        "--type",
                        kind,
                        "--subtitle-lang",
                        "en",
                        "--save-subtitles",
                        "--save-description",
                        "--save-thumbnail",
                        "--format",
                        "json",
                    ],
                    owned,
                )
                assert accepted["status"] == "queued" and isinstance(accepted["task_id"], int)
                identity = str(accepted["task_id"])
                result = self.call(
                    "download-" + kind + "-reopen", ["history", "get", identity], owned
                )
                assert result["status"] == "done"
                paths = self.call(
                    "download-" + kind + "-paths", ["history", "file-paths", identity], owned
                )
                media = Path(paths["video_path"] if kind == "video" else paths["audio_path"])
                assert media.is_file() and media.stat().st_size > 0
                streams = self.raw(
                    "probe-" + kind,
                    [
                        str(probe),
                        "-v",
                        "error",
                        "-show_streams",
                        "-show_format",
                        "-of",
                        "json",
                        str(media),
                    ],
                    owned,
                )
                types = {s["codec_type"] for s in streams["streams"]}
                assert (types >= {"video", "audio"}) if kind == "video" else ("audio" in types)
                assert float(streams["format"]["duration"]) > 0
                assert (
                    self.call(
                        "download-" + kind + "-second-reopen", ["history", "get", identity], owned
                    )
                    == result
                )
            bad = self.root / "invalid-add"
            assert (
                self.call(
                    "invalid-quality",
                    ["queue", "add", url, "--quality", "not-a-quality"],
                    bad,
                    expected=1,
                )["code"]
                == "INVALID_ARGUMENT"
            )
            failed = self.root / "failed-transfer"
            failure = self.call(
                "local-http-404",
                ["queue", "add", url.replace("fixture.mp4", "missing.mp4")],
                failed,
                expected=1,
            )
            assert failure["code"] == "DOWNLOAD_FAILED"
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            assert not thread.is_alive()

    async def stdio(self, profile, label="stdio"):
        import anyio
        from fastmcp import Client
        from fastmcp.client.transports import StdioTransport

        environment = self.env(profile)
        transport = StdioTransport(
            command=str(self.exe),
            args=["--data-dir", str(profile), "server", "stdio"],
            env=environment,
            cwd=str(self.cwd),
            keep_alive=False,
            log_file=self.root / (label + "-stderr.txt"),
        )
        original = anyio.open_process
        processes = []
        observed_commands = []

        async def observe(*args, **kwargs):
            # Inspect the SDK's final process boundary, not just constructor options.
            assert kwargs["env"] == environment
            command = list(args[0] if args else kwargs["command"])
            assert command == [str(self.exe), "--data-dir", str(profile), "server", "stdio"]
            observed_commands.append(command)
            process = await original(*args, **kwargs)
            processes.append(process)
            return process

        anyio.open_process = observe
        try:
            with anyio.fail_after(20):
                async with Client(transport, timeout=8) as client:
                    tools = await client.list_tools()
                    assert len(tools) == 10
                    row = (await client.call_tool("get_download", {"id": 7})).structured_content
                    assert row["title"] == "Owned CLI result"
                    description = (
                        await client.call_tool("read_description", {"id": 7})
                    ).structured_content
                    assert description["description_text"] == "Distinct CLI description"
        finally:
            await transport.close()
            anyio.open_process = original
        assert len(processes) == 1 and processes[0].returncode == 0
        self.rows.append(
            {
                "label": label,
                "native_exit": processes[0].returncode,
                "pid": processes[0].pid,
                "cwd": str(self.cwd),
                "sanitized_env": environment,
                "tool_names": sorted(t.name for t in tools),
                "get_result": row,
                "description_result": description,
                "argv": observed_commands[0],
                "actual_sdk_process_env_matches_sanitized_env": True,
                "useful_object": True,
                "EOF_joined": True,
                "stdout_channel": "Real SDK consumed MCP protocol; results recorded above",
                "stderr_sha256": hashlib.sha256(
                    (self.root / (label + "-stderr.txt")).read_bytes()
                ).hexdigest(),
            }
        )

    def servers(self):
        from fastmcp import Client

        profile = self.root / "stdio-profile"
        seed_profile(profile, self.root / "stdio-fixture")
        asyncio.run(self.stdio(profile))
        http_profile = self.root / "http-profile"
        seed_profile(http_profile, self.root / "http-fixture")
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        startup = subprocess.STARTUPINFO() if os.name == "nt" else None
        if startup is not None:
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            # Windows can inherit an ignore-Ctrl+C flag from a process supervisor.
            # Enable it in THIS owned verifier before creating its separate console.
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            if not kernel.SetConsoleCtrlHandler(None, False):
                raise ctypes.WinError(ctypes.get_last_error())
        argv = [
            str(self.exe),
            "--data-dir",
            str(http_profile),
            "server",
            "http",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
        with (
            (self.root / "http-stdout.txt").open("wb") as out,
            (self.root / "http-stderr.txt").open("wb") as err,
        ):
            process = subprocess.Popen(
                argv,
                cwd=self.cwd,
                env=self.env(http_profile),
                stdout=out,
                stderr=err,
                stdin=subprocess.DEVNULL,
                creationflags=flags,
                startupinfo=startup,
            )
            try:
                deadline = time.monotonic() + 15
                while True:
                    assert process.poll() is None
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            break
                    except OSError:
                        assert time.monotonic() < deadline
                        time.sleep(0.05)

                async def query():
                    async with Client(f"http://127.0.0.1:{port}/mcp", timeout=8) as client:
                        rows = (await client.call_tool("list_downloads")).structured_content[
                            "result"
                        ]
                        assert len(rows) == 5 and any(r["id"] == 7 for r in rows)
                        obj = (await client.call_tool("get_download", {"id": 7})).structured_content
                        assert obj["title"] == "Owned CLI result"
                        return {"list_downloads": rows, "get_download": obj}

                http_results = asyncio.run(query())
                interrupt_owned_console(process.pid)
                # The canonical CLI maps a cooperative keyboard interrupt to
                # native1 / INTERRUPTED, not successful command completion.
                assert process.wait(timeout=10) == 1
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
        shutdown_stderr = (self.root / "http-stderr.txt").read_text(encoding="utf-8")
        assert "reason_code=INTERRUPTED" in shutdown_stderr
        assert "mcp.server.stopped" in shutdown_stderr and "Traceback" not in shutdown_stderr
        assert (self.root / "http-stdout.txt").read_bytes() == b""
        with socket.socket() as reuse:
            reuse.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            reuse.bind(("127.0.0.1", port))
        self.rows.append(
            {
                "label": "http",
                "argv": argv,
                "pid": process.pid,
                "native_exit": process.returncode,
                "expected_interrupt_exit": 1,
                "interrupt_code": "INTERRUPTED",
                "graceful_stop_observed": True,
                "cwd": str(self.cwd),
                "useful_objects": True,
                "client_results": http_results,
                "sanitized_env": self.env(http_profile),
                "port_reusable": True,
                "shutdown": "Ctrl+C sent only to a newly created owned hidden console",
                "stdout_sha256": hashlib.sha256(
                    (self.root / "http-stdout.txt").read_bytes()
                ).hexdigest(),
                "stderr_sha256": hashlib.sha256(
                    (self.root / "http-stderr.txt").read_bytes()
                ).hexdigest(),
            }
        )
        # A new writable EXE owner after HTTP join; no source-owner replacement.
        asyncio.run(self.stdio(http_profile, "stdio-after-http"))


def interrupt_owned_console(pid: int) -> None:
    """Signal ONLY the hidden console created by this runner, never the agent console."""
    if os.name != "nt":
        import signal

        os.kill(pid, signal.SIGINT)
        return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.FreeConsole()
    if not kernel.AttachConsole(pid):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel.SetConsoleCtrlHandler(None, True):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.GenerateConsoleCtrlEvent(0, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        time.sleep(0.2)
    finally:
        kernel.FreeConsole()
        kernel.SetConsoleCtrlHandler(None, False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument(
        "--sections",
        nargs="+",
        choices=("queries", "media", "servers"),
        default=["queries", "media", "servers"],
        help="Bounded phase selection; omitted phases are explicitly NOT_RUN in this receipt.",
    )
    args = parser.parse_args(argv)
    root = args.work_root
    if not root.is_absolute() or root.exists():
        parser.error("--work-root must be a NEW absolute owned directory")
    if not args.exe.is_absolute() or not args.exe.is_file():
        parser.error("--exe must be the existing relocated native executable")
    root.mkdir(parents=True)
    # Own process imports/SDK/fixture setup are isolated too, before product imports.
    environment = native_environment(root / "supervisor", root / "supervisor-profile")
    os.environ.clear()
    os.environ.update(environment)
    proof = NativeProof(args.exe, root)
    try:
        for section in args.sections:
            {"queries": proof.queries_and_refusals, "media": proof.media, "servers": proof.servers}[
                section
            ]()
    finally:
        (root / "functional-matrix.json").write_text(
            json.dumps(
                {
                    "public_leaves": LEAVES,
                    "rows": proof.rows,
                    "requested_sections": args.sections,
                    "unrequested_sections": [
                        x for x in ("queries", "media", "servers") if x not in args.sections
                    ],
                    "declared_boundaries": proof.boundaries,
                    "boundary": (
                        "Native relocated bundle; source API seeds own fixtures; own HTTP only"
                    ),
                    "external_YouTube": "WAITING_FOR_USER_URL",
                    "GUI": "not exposed/outside scope",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "status": (
                    "FUNCTIONAL_WITH_DECLARED_BOUNDARIES"
                    if proof.boundaries
                    else "LOCAL_FUNCTIONAL_PASS"
                    if set(args.sections) == {"queries", "media", "servers"}
                    else "SCOPED_FUNCTIONAL_PASS"
                ),
                "sections": args.sections,
                "declared_boundaries": proof.boundaries,
                "native_rows": len(proof.rows),
                "public_leaves": len(LEAVES),
                "external": "WAITING_FOR_USER_URL",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
