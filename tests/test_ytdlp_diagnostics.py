"""Real public API -> installed yt-dlp -> owned HTTP403 -> durable failure.

The loopback HTML/media/subtitle source is explicitly synthetic, not YouTube proof.
No production emitter/terminal/repository is replaced with a canned success.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("failed_edge", ["media", "subtitle"])
def test_real_backend_403_retains_sidecars_and_safe_actionable_diagnostics(
    tmp_path: Path, failed_edge: str
):
    script = r"""
import base64, json, logging, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
root = Path(sys.argv[1]).resolve()
edge = sys.argv[2]
for key, relative in {"HOME":"home", "USERPROFILE":"home", "APPDATA":"appdata",
                      "LOCALAPPDATA":"local", "TEMP":"temp", "TMP":"temp",
                      "YTDL_DATA_DIR":"profile", "YTDL_LOG_DIR":"logs"}.items():
    target = root/relative
    target.mkdir(parents=True, exist_ok=True)
    os.environ[key] = str(target)
from src.bootstrap import create_runtime
from src.core.logging_setup import setup_logging
marker = "PRIVATE_Q3_CONTENT_URL_TOKEN_PATH_TITLE_ERROR"
counts = {"media":0,"subtitle":0}
html = ("<html><head><title>PRIVATE_Q3_T</title>"
        '<meta property="og:description" content="' + marker + '">'
        '<meta property="og:image" content="OWN_ORIGIN/thumb.png"></head><body>'
        '<video controls><source src="/media.mp4?token=' + marker + '" type="video/mp4">'
        '<track kind="subtitles" src="/ru.vtt" srclang="ru" label="Russian">'
        '</video></body></html>').encode()
image = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lE"
    "QVR42mP8/x8AAwMCAO+a8X8AAAAASUVORK5CYII=")
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        path = self.path.split("?",1)[0]
        if path == "/owned.html":
            origin = f"http://127.0.0.1:{self.server.server_port}".encode()
            status, kind, data = 200,"text/html",html.replace(b"OWN_ORIGIN",origin)
        elif path == "/ru.vtt":
            counts["subtitle"] += 1
            if edge == "subtitle":status,kind,data = 403,"text/plain",b""
            else:
                status,kind,data = 200,"text/vtt",(
                    b"WEBVTT\n\n00:00.000 --> 00:00.500\nOwned Russian fixture\n")
        elif path == "/thumb.png":status,kind,data = 200,"image/png",image
        else:
            counts["media"] += 1
            status,kind,data = 403,"text/plain",b""
        self.send_response(status, marker if status == 403 else "OK")
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        if data:self.wfile.write(data)
server = ThreadingHTTPServer(("127.0.0.1",0),Handler)
thread = threading.Thread(target=server.serve_forever)
thread.start()
runtime = None
setup_logging(log_dir=root/"logs",stream=sys.stderr)
try:
    runtime = create_runtime(root/"profile",settings_overrides={"output_dir":root/"output"})
    accepted = runtime.api.queue_add_download(
        url=f"http://127.0.0.1:{server.server_port}/owned.html", quality="1080p",
        download_type="video", subtitle_lang="ru", save_subtitles=True,
        save_description=True, save_thumbnail=True,
    )
    terminal = runtime.api.wait_for_download(accepted.task_id,timeout=10)
    assert terminal and terminal.status == "failed" and terminal.error_code == "DOWNLOAD_FAILED"
    assert terminal.result_persisted
finally:
    closed = runtime.close(cancel=True,wait=True) if runtime else None
    server.shutdown()
    server.server_close()
    thread.join(5)
    logging.shutdown()
assert closed and closed.closed and not closed.error_codes and not thread.is_alive()
with create_runtime(root/"profile",read_only=True) as reopened:
    row = reopened.api.get_download(accepted.task_id)
    assert row.status == "failed" and row.error_code == "DOWNLOAD_FAILED"
    recorded = {Path(p).resolve() for p in row.artifact_paths or []}
physical = {p.resolve() for p in (root/"output").rglob("*") if p.is_file()}
assert counts[edge] > 0
descriptions = [p for p in physical if p.suffix == ".description"]
assert len(descriptions) == 1 and descriptions[0].read_text(encoding="utf-8").strip() == marker
assert row.description_path == str(descriptions[0])
if edge == "media":
    assert len(physical) == 4, "Description/RU/thumbnail/info must precede the media403"
else:
    assert counts["media"] == 0, "A failed requested subtitle must stop before media"
    assert physical == {descriptions[0]}, "The real early description must survive subtitle403"
assert recorded == physical, (
    "lost physical sidecars after backend failure", len(recorded),len(physical))
assert all(p.is_relative_to(root/"output") for p in recorded)
print(json.dumps({"status":"failed","code":row.error_code,"http403_edge":edge,
                  "persisted_readback":True,"recorded_sidecars":len(recorded),
                  "physical_files":len(physical),"owned_server_joined":True}))
"""
    child = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), failed_edge],
        cwd=Path(__file__).resolve().parent.parent,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=25,
    )
    (tmp_path / "child.stdout.txt").write_text(child.stdout, encoding="utf-8")
    (tmp_path / "child.stderr.txt").write_text(child.stderr, encoding="utf-8")
    (tmp_path / "child.native-exit.txt").write_text(str(child.returncode), encoding="utf-8")
    assert child.returncode == 0, child.stderr
    for output in (
        child.stderr,
        (tmp_path / "logs/app.log").read_text(encoding="utf-8"),
        (tmp_path / "logs/app.error.log").read_text(encoding="utf-8"),
    ):
        assert output
        assert "reason_code=HTTP_FORBIDDEN http_status=403" in output
        assert "coordinator.failed id=1 reason_code=DOWNLOAD_FAILED" in output
        assert "PRIVATE_Q3_" not in output and "token=" not in output
        assert str(tmp_path) not in output


def test_exact_sdk_sidecar_preimages_are_not_failed_attempt_artifacts(tmp_path: Path):
    script = r'''
import hashlib, json, logging, os, socket, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
root = Path(sys.argv[1]).resolve()
for key, relative in {"HOME":"home", "USERPROFILE":"home", "APPDATA":"appdata",
                      "LOCALAPPDATA":"local", "TEMP":"temp", "TMP":"temp",
                      "YTDL_DATA_DIR":"initial-profile", "YTDL_LOG_DIR":"logs"}.items():
    target = root/relative
    target.mkdir(parents=True,exist_ok=True)
    os.environ[key] = str(target)
from src.bootstrap import create_runtime
from src.core.logging_setup import setup_logging
from src.infrastructure.ffmpeg import find_ffmpeg
ffmpeg = find_ffmpeg()
assert ffmpeg and ffmpeg.is_file()
source = root/"source"
source.mkdir()
images = {}
for name, color in [("remote.jpeg","red"),("old.jpeg","blue"),("old.png","blue")]:
    destination = source/name
    proc = subprocess.run([str(ffmpeg),"-v","error","-n","-f","lavfi","-i",
        f"color=c={color}:s=32x18","-frames:v","1","-threads","1","-update","1",
        str(destination)],capture_output=True,timeout=15)
    assert proc.returncode == 0,proc.stderr
    images[name] = destination.read_bytes()
assert images["remote.jpeg"][:2] == images["old.jpeg"][:2] == bytes.fromhex("ffd8")
assert images["remote.jpeg"] != images["old.jpeg"]
assert images["old.png"].startswith(bytes.fromhex("89504e470d0a1a0a"))
description = "PRIVATE_Q3_R1_NEW_DESCRIPTION_NOT_PREEXISTING"
state = {"case":None,"extension":"jpeg"}
counts = {}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        path = self.path.split("?",1)[0]
        label = state["case"]
        counts[label][path] = counts[label].get(path,0)+1
        if path == "/owned.html":
            origin = f"http://127.0.0.1:{self.server.server_port}"
            data = (f'<html><head><title>OwnedR1</title><meta property="og:description" '
                    f'content="{description}"><meta property="og:image" '
                    f'content="{origin}/thumb.{state["extension"]}"></head><body>'
                    '<video controls><source src="/media.mp4" type="video/mp4">'
                    '<track kind="subtitles" src="/ru.vtt" srclang="ru">'
                    '</video></body></html>').encode()
            status,kind = 200,"text/html"
        elif path == "/thumb.jpeg":status,kind,data = 200,"image/jpeg",images["remote.jpeg"]
        elif path == "/thumb.png":status,kind,data = 200,"image/png",images["old.png"]
        else:status,kind,data = 403,"text/plain",b""
        self.send_response(status)
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        if data:self.wfile.write(data)
server = ThreadingHTTPServer(("127.0.0.1",0),Handler)
server.daemon_threads = False
thread = threading.Thread(target=server.serve_forever)
thread.start()
port = server.server_port
setup_logging(log_dir=root/"logs",stream=sys.stderr)
relative_thumbnail = relative_description = None
results = []
try:
    for label,extension,seed_kind in [
        ("clean-jpeg","jpeg",None),("old-jpeg","jpeg","jpeg"),
        ("old-png","png","png"),("old-description","jpeg","description")
    ]:
        base = root/label
        profile,output = base/"profile",base/"out"
        unlisted = output/"download-1/unlisted.bin"
        unlisted.parent.mkdir(parents=True)
        unlisted.write_bytes(b"Owned test's unrelated foreign file")
        seed = None
        if seed_kind:
            assert relative_thumbnail is not None and relative_description is not None
            relative = relative_description if seed_kind == "description" else (
                relative_thumbnail.with_suffix("."+extension))
            seed = output/"download-1"/relative
            seed.parent.mkdir(parents=True,exist_ok=True)
            body = (b"Preexisting foreign description" if seed_kind == "description"
                    else images["old."+extension])
            with seed.open("xb") as stream:stream.write(body)
            before = seed.stat()
        state.update(case=label,extension=extension)
        counts[label] = {}
        runtime = None
        try:
            runtime = create_runtime(profile,settings_overrides={"output_dir":output})
            ident = runtime.api.queue_add_download(
                url=f"http://127.0.0.1:{port}/owned.html",quality="1080p",download_type="video",
                subtitle_lang="ru",save_subtitles=seed_kind=="description",
                save_description=True,save_thumbnail=True).task_id
            terminal = runtime.api.wait_for_download(ident,timeout=15)
            assert (terminal and terminal.status == "failed"
                    and terminal.error_code == "DOWNLOAD_FAILED")
            assert terminal.result_persisted
        finally:
            closed = runtime.close(cancel=True,wait=True) if runtime else None
        assert closed and closed.closed and not closed.error_codes
        with create_runtime(profile,read_only=True) as reopened:
            row = reopened.api.get_file_paths(ident)
            recorded = {Path(p).resolve() for p in row.artifact_paths}
            assert row.status == "failed" and row.error_code == "DOWNLOAD_FAILED"
            assert all(p.is_relative_to(output.resolve()/"download-1") and p.is_file()
                       for p in recorded)
            assert unlisted.read_bytes() == b"Owned test's unrelated foreign file"
            assert unlisted.resolve() not in recorded
            if seed_kind is None:
                thumbnail = Path(row.thumbnail_path)
                desc = Path(row.description_path)
                assert (thumbnail.read_bytes() == images["remote.jpeg"]
                        and thumbnail.suffix == ".jpeg")
                assert desc.read_text(encoding="utf-8").strip() == description
                relative_thumbnail = thumbnail.relative_to(output/"download-1")
                relative_description = desc.relative_to(output/"download-1")
                assert counts[label].get("/thumb.jpeg",0)>0
            else:
                assert seed.read_bytes() == body
                after = seed.stat()
                assert (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) == (
                    before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
                assert counts[label].get("/thumb."+extension,0) == 0
            if seed_kind == "description":
                assert counts[label].get("/media.mp4",0) == 0 and counts[label].get("/ru.vtt",0)>0
                field_absent = row.description_path is None
            else:
                assert counts[label].get("/media.mp4",0)>0
                field_absent = row.thumbnail_path is None
            results.append({"case":label,"seeded":bool(seed_kind),
                "seed_recorded":bool(seed_kind) and seed.resolve() in recorded,
                "seed_dto_field_absent":field_absent if seed_kind else None,
                "recorded_count":len(recorded),"thumbnail_GET":counts[label].get("/thumb."+extension,0)})
        saved = (profile/"data/history.json").read_bytes()
        with create_runtime(profile) as next_writer:
            assert next_writer.api.get_download(ident).status == "failed"
            assert not next_writer.api.list_tasks()
        assert (profile/"data/history.json").read_bytes() == saved
finally:
    server.shutdown()
    server.server_close()
    thread.join(5)
    logging.shutdown()
assert not thread.is_alive() and server.fileno() == -1
with socket.socket() as probe:probe.bind(("127.0.0.1",port))
print(json.dumps({"cases":results,"owned_server_joined_port_rebind":True}),flush=True)
assert all(not r["seed_recorded"] and r["seed_dto_field_absent"] for r in results if r["seeded"])
'''
    child = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=Path(__file__).resolve().parent.parent,
        env=os.environ.copy(), capture_output=True, text=True, timeout=45,
    )
    (tmp_path / "ownership.stdout.txt").write_text(child.stdout, encoding="utf-8")
    (tmp_path / "ownership.stderr.txt").write_text(child.stderr, encoding="utf-8")
    (tmp_path / "ownership.native-exit.txt").write_text(str(child.returncode), encoding="utf-8")
    assert child.returncode == 0, child.stderr
