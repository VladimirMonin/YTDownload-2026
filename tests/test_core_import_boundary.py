"""Fresh-interpreter dependency boundary and genuine cross-process writer lease."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from src.domain.models import HistoryEntry
from src.domain.models.download_task import DownloadStatus
from src.infrastructure.repositories import JsonHistoryRepository

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _environment(root: Path) -> dict[str, str]:
    overrides = {
        "APPDATA": root / "appdata", "LOCALAPPDATA": root / "localappdata",
        "HOME": root / "home", "USERPROFILE": root / "home", "TMP": root / "temp",
        "TEMP": root / "temp", "TMPDIR": root / "temp", "UV_CACHE_DIR": root / "cache/uv",
        "RUFF_CACHE_DIR": root / "cache/ruff", "MYPY_CACHE_DIR": root / "cache/mypy",
        "XDG_CACHE_HOME": root / "cache/xdg", "YTDL_LOG_DIR": root / "logs",
        "YTDL_DATA_DIR": root / "appdata/YTDownloader", "YTDL_SMOKE_ROOT": root / "smokes",
    }
    for path in overrides.values():
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({key: path.as_posix() for key, path in overrides.items()})
    env.update(UV_OFFLINE="1", UV_NO_SYNC="1", UV_PYTHON_DOWNLOADS="never",
               PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", QT_QPA_PLATFORM="offscreen",
               FASTMCP_CHECK_FOR_UPDATES="off", DO_NOT_TRACK="1")
    (root / "isolation.json").write_text(
        json.dumps({key: env[key] for key in overrides}), encoding="utf-8"
    )
    return env


def _receipt(directory: Path, result: subprocess.CompletedProcess[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (directory / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    (directory / "native-exit.txt").write_text(str(result.returncode), encoding="utf-8")


def _run(code: str, directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-c", code, *args], cwd=PROJECT_ROOT, env=_environment(directory),
        text=True, capture_output=True, timeout=20,
    )
    _receipt(directory, result)
    assert result.returncode == 0, result.stderr
    return result


BLOCK_IMPORTS = r'''
import json, sys
from pathlib import Path
blocked = {"PySide6", "PyQt5", "fastmcp", "uvicorn", "argparse", "yt_dlp"}
assert not (blocked & set(sys.modules))
class Blocker:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in blocked:
            raise AssertionError("Forbidden dependency imported: " + fullname)
sys.meta_path.insert(0, Blocker())
'''


def test_core_import_and_useful_direct_read_without_ui_transport_or_backend(tmp_path: Path) -> None:
    root = tmp_path / "store"
    description = tmp_path / "description.txt"
    description.write_text("Distinctive blocked-import description", encoding="utf-8")
    repo = JsonHistoryRepository(root / "data")
    repo.add(HistoryEntry(id=23, url="https://example.invalid/direct", title="Headless query",
                          status=DownloadStatus.DONE, description_path=description))
    before = (root / "data/history.json").read_bytes()
    result = _run(BLOCK_IMPORTS + r'''
from src.application.api import ApplicationAPI
from src.application.dto import serialize_for_transport
from src.infrastructure.repositories import JsonHistoryRepository
from src.bootstrap import create_runtime
root = Path(sys.argv[1])
api = ApplicationAPI(JsonHistoryRepository(root / "data", read_only=True))
assert api.get_download(23).title == "Headless query"
assert api.read_description(23).description_text == "Distinctive blocked-import description"
with create_runtime(root, read_only=True) as reader:
    assert reader.coordinator is None
    assert reader.api.get_file_paths(23).description_path is not None
assert not (blocked & set(sys.modules))
print(json.dumps(serialize_for_transport(api.list_downloads())))
''', tmp_path / "child", str(root))
    assert json.loads(result.stdout)[0]["id"] == 23
    assert (root / "data/history.json").read_bytes() == before
    assert not (root / ".writer.lock").exists()
    assert not (root / "config").exists()


def test_composed_writable_core_executes_only_injected_ports_without_qapplication(
    tmp_path: Path,
) -> None:
    result = _run(BLOCK_IMPORTS + r'''
from src.bootstrap import create_runtime
from src.domain.models import VideoInfo
from src.domain.protocols.download_service import IDownloadService
from src.application.dto import serialize_for_transport
class Backend(IDownloadService):
    def fetch_info(self, url, settings):
        return VideoInfo(title="Injected direct runtime")
    def download(self, task, settings, progress_callback=None):
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        path = settings.output_dir / "direct.bin"
        path.write_bytes(b"distinctive composed result")
        return {"video": path, "subtitles": []}
    def cancel(self):
        pass
class Remover:
    closes = 0
    def move_to_trash(self, path):
        raise AssertionError("No S2 deletion")
    def close(self):
        self.closes += 1
root = Path(sys.argv[1])
remover = Remover()
runtime = create_runtime(root, backend_factory=Backend, file_remover_factory=lambda: remover,
                         settings_overrides={"output_dir": str(root / "output")})
try:
    accepted = runtime.api.queue_add_download(url="https://example.invalid/injected")
finally:
    closed = runtime.close(cancel=False, wait=True)
assert closed.closed and not closed.error_codes
assert remover.closes == 1
with create_runtime(root, read_only=True) as reader:
    saved = reader.api.get_download(accepted.task_id)
    assert saved.status == "done"
    assert Path(saved.video_path).read_bytes() == b"distinctive composed result"
assert not (blocked & set(sys.modules))
print(json.dumps(serialize_for_transport(saved)))
''', tmp_path / "child", str(tmp_path / "store"))
    assert json.loads(result.stdout)["title"] == "Injected direct runtime"


def test_changed_storage_and_backend_errors_have_real_safe_diagnostics(tmp_path: Path) -> None:
    result = _run(r'''
import json, logging, os, sys
from pathlib import Path
from src.bootstrap import create_runtime
from src.core.logging_setup import setup_logging
from src.domain.models import VideoInfo
from src.domain.protocols.download_service import IDownloadService
from src.domain.protocols.history_repository import StorageError
class FailedBackend(IDownloadService):
    def fetch_info(self, url, settings):
        return VideoInfo(title="S2_TITLE_SENTINEL")
    def download(self, task, settings, progress_callback=None):
        raise RuntimeError("S2_EXCEPTION_SENTINEL S2_URL_SENTINEL S2_PROXY_SENTINEL")
    def cancel(self):
        pass
root = Path(sys.argv[1])
setup_logging(stream=sys.stderr)
runtime = None
try:
    runtime = create_runtime(root, backend_factory=FailedBackend, settings_overrides={
        "output_dir": str(root / "S2_PATH_SENTINEL"), "proxy": "S2_PROXY_SENTINEL",
    })
    try:
        accepted = runtime.api.queue_add_download(url="https://example.invalid/S2_URL_SENTINEL")
    finally:
        assert runtime.close(cancel=False, wait=True).closed
    assert runtime.api.get_download(accepted.task_id).status == "failed"
    with create_runtime(root) as next_owner:
        original = os.replace
        def fail(source, destination):
            if Path(destination) == root / "config/settings.json":
                raise OSError("S2_EXCEPTION_SENTINEL S2_PATH_SENTINEL S2_PROXY_SENTINEL")
            return original(source, destination)
        os.replace = fail
        try:
            try:
                next_owner.api.update_settings(next_owner.api.get_settings())
            except StorageError as exc:
                assert exc.code == "PERSISTENCE_FAILED"
            else:
                raise AssertionError("Expected storage fault")
        finally:
            os.replace = original
    for handler in logging.getLogger().handlers:
        handler.flush()
finally:
    if runtime is not None:
        runtime.close(cancel=False, wait=True)
    logging.shutdown()
log_root = Path(os.environ["YTDL_LOG_DIR"])
normal = (log_root / "app.log").read_text(encoding="utf-8")
errors = (log_root / "app.error.log").read_text(encoding="utf-8")
assert normal and errors
assert "coordinator.failed id=1 reason_code=DOWNLOAD_FAILED" in errors
assert "repository.write.failed reason_code=PERSISTENCE_FAILED" in errors
for marker in ("S2_TITLE_SENTINEL", "S2_URL_SENTINEL", "S2_PROXY_SENTINEL",
               "S2_PATH_SENTINEL", "S2_EXCEPTION_SENTINEL"):
    assert marker not in normal and marker not in errors
print(json.dumps({"normal_bytes": len(normal), "error_bytes": len(errors), "id": 1}))
''', tmp_path / "child", str(tmp_path / "store"))
    assert json.loads(result.stdout)["error_bytes"] > 0
    assert "id=1 reason_code=DOWNLOAD_FAILED" in result.stderr
    for category in ("TITLE", "URL", "PROXY", "PATH", "EXCEPTION"):
        assert f"S2_{category}_SENTINEL" not in result.stderr


OWNER = r'''
import json, sys
from pathlib import Path
from src.bootstrap import create_runtime
from src.domain.models import HistoryEntry
from src.domain.models.download_task import DownloadStatus
from src.application.dto import serialize_for_transport
root, ready = Path(sys.argv[1]), Path(sys.argv[2])
runtime = create_runtime(root)
try:
    settings = runtime.api.get_settings()
    settings.theme = "light"
    runtime.api.update_settings(settings)
    runtime.history_repo.add(HistoryEntry(id=7, url="https://example.invalid/owner",
                                         title="First writer record", status=DownloadStatus.DONE))
    ready.write_text(
        json.dumps(serialize_for_transport(runtime.api.list_downloads())), encoding="utf-8"
    )
    sys.stdin.readline()
finally:
    result = runtime.close(cancel=False, wait=True)
    print(json.dumps(serialize_for_transport(result)), flush=True)
'''

PROBE = r'''
import json, sys
from pathlib import Path
from src.bootstrap import create_runtime
from src.domain.protocols.history_repository import StorageError
root, mode = Path(sys.argv[1]), sys.argv[2]
try:
    runtime = create_runtime(root, read_only=mode == "read")
except StorageError as exc:
    print(json.dumps({"code": exc.code}))
else:
    try:
        print(json.dumps({"code": "OPEN", "ids": [item.id for item in runtime.api.list_downloads()],
                          "read_only": runtime.read_only,
                          "no_coordinator": runtime.coordinator is None,
                          "theme": runtime.api.get_settings().theme}))
    finally:
        assert runtime.close(cancel=False, wait=True).closed
'''


def test_two_real_writers_read_only_snapshot_and_next_process_after_close(tmp_path: Path) -> None:
    root, ready = tmp_path / "store", tmp_path / "ready.json"
    directory = tmp_path / "first-process"
    owner = subprocess.Popen(
        [sys.executable, "-c", OWNER, str(root), str(ready)], cwd=PROJECT_ROOT,
        env=_environment(directory), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )
    timed_out = False
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and owner.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), "Writer did not reach its owned readiness boundary"
        assert json.loads(ready.read_text(encoding="utf-8"))[0]["title"] == "First writer record"
        history = root / "data/history.json"
        before = history.read_bytes()
        lock_identity = (root / ".writer.lock").stat().st_ino
        busy = _run(PROBE, tmp_path / "second-process", str(root), "write")
        assert json.loads(busy.stdout) == {"code": "OWNER_BUSY"}
        assert history.read_bytes() == before
        reader = _run(PROBE, tmp_path / "read-process", str(root), "read")
        assert json.loads(reader.stdout) == {
            "code": "OPEN", "ids": [7], "read_only": True, "no_coordinator": True, "theme": "light",
        }
        assert history.read_bytes() == before
    finally:
        try:
            stdout, stderr = owner.communicate(input="close\n", timeout=15)
        except subprocess.TimeoutExpired:
            timed_out = True
            owner.kill()  # Only this explicitly owned child, never another process.
            stdout, stderr = owner.communicate(timeout=5)
        _receipt(
            directory, subprocess.CompletedProcess(owner.args, owner.returncode, stdout, stderr)
        )
    assert not timed_out and owner.returncode == 0, stderr
    assert json.loads(stdout)["closed"] is True
    following = _run(PROBE, tmp_path / "next-process", str(root), "write")
    assert json.loads(following.stdout) == {
        "code": "OPEN", "ids": [7], "read_only": False, "no_coordinator": False, "theme": "light",
    }
    assert (root / ".writer.lock").stat().st_ino == lock_identity
