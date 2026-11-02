"""Real API / source CLI / MCP SDK -> yt-dlp -> owned DASH -> FFmpeg/files.

All media/manifests/sidecars are newly generated synthetic loopback data, not
YouTube/availability proof. No download service, API, terminal or repository mocks.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastmcp import Client

from src.bootstrap import create_runtime
from src.infrastructure.mcp.server import create_mcp_server


@pytest.fixture(scope="module")
def quality_source(tmp_path_factory, ffmpeg_path):
    root = tmp_path_factory.mktemp("owned-quality-source")
    for height, width in ((1080, 1920), (1440, 2560), (2160, 3840)):
        subprocess.run(
            [
                str(ffmpeg_path),
                "-v",
                "error",
                "-n",
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={width}x{height}:r=4",
                "-t",
                "0.5",
                "-an",
                "-c:v",
                "mpeg4",
                "-q:v",
                "8",
                "-threads",
                "1",
                str(root / f"v{height}.mp4"),
            ],
            capture_output=True,
            check=True,
            timeout=20,
        )
    subprocess.run(
        [
            str(ffmpeg_path),
            "-v",
            "error",
            "-n",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100",
            "-t",
            "0.5",
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            str(root / "audio.m4a"),
        ],
        capture_output=True,
        check=True,
        timeout=20,
    )
    subprocess.run(
        [
            str(ffmpeg_path),
            "-v",
            "error",
            "-n",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=32x18",
            "-frames:v",
            "1",
            "-update",
            "1",
            str(root / "thumb.png"),
        ],
        capture_output=True,
        check=True,
        timeout=20,
    )
    (root / "ru.vtt").write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:00.500\nСинтетические RU субтитры\n", encoding="utf-8"
    )
    representations = "".join(
        f'<Representation id="v{height}" bandwidth="{height * 1000}" '
        f'width="{width}" height="{height}" frameRate="4" codecs="mp4v.20.9">'
        f"<BaseURL>v{height}.mp4</BaseURL></Representation>"
        for height, width in ((1080, 1920), (1440, 2560), (2160, 3840))
    )
    (root / "source.mpd").write_text(
        '<?xml version="1.0"?><MPD xmlns="urn:mpeg:dash:schema:mpd:2011" '
        'type="static" mediaPresentationDuration="PT0.5S" minBufferTime="PT0.1S">'
        '<Period duration="PT0.5S"><AdaptationSet mimeType="video/mp4">'
        + representations
        + '</AdaptationSet><AdaptationSet mimeType="audio/mp4" lang="ru">'
        '<Representation id="audio" bandwidth="96000" codecs="mp4a.40.2">'
        "<BaseURL>audio.m4a</BaseURL></Representation></AdaptationSet></Period></MPD>",
        encoding="utf-8",
    )

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(root)))
    origin = f"http://127.0.0.1:{server.server_port}"
    (root / "owned.html").write_text(
        "<html><head><title>OwnedQ3</title>"
        '<meta property="og:description" content="Distinct Q3 owned description">'
        f'<meta property="og:image" content="{origin}/thumb.png"></head><body>'
        f'<video controls><source src="{origin}/source.mpd" type="application/dash+xml">'
        f'<track kind="subtitles" src="{origin}/ru.vtt" srclang="ru" label="Russian">'
        "</video></body></html>",
        encoding="utf-8",
    )
    (root / "no-extras.html").write_text(
        "<html><head><title>OwnedNoExtras</title></head><body>"
        f'<video><source src="{origin}/source.mpd" type="application/dash+xml">'
        "</video></body></html>",
        encoding="utf-8",
    )
    (root / "missing-thumb.html").write_text(
        (root / "owned.html").read_text(encoding="utf-8").replace("/thumb.png", "/missing.png"),
        encoding="utf-8",
    )
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield {"url": origin + "/owned.html", "root": root}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        assert not thread.is_alive()


def _arguments(url: str, height: int) -> dict:
    return {
        "url": url,
        "quality": f"{height}p",
        "download_type": "video",
        "subtitle_lang": "ru",
        "save_subtitles": True,
        "save_description": True,
        "save_thumbnail": True,
    }


def _verify(profile: Path, output: Path, ident: int, height: int, ffprobe_path: Path) -> dict:
    with create_runtime(profile, read_only=True) as reopened:
        row = reopened.api.get_file_paths(ident)
        assert row.id == ident and row.status == "done" and row.quality == f"{height}p"
        paths = {Path(p) for p in row.artifact_paths}
        assert paths and all(p.is_relative_to(output) and p.is_file() for p in paths)
        video = Path(row.video_path)
        assert video in paths
        result = subprocess.run(
            [
                str(ffprobe_path),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                str(video),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        streams = json.loads(result.stdout)["streams"]
        videos = [s for s in streams if s["codec_type"] == "video"]
        audios = [s for s in streams if s["codec_type"] == "audio"]
        assert len(videos) == 1 and videos[0]["height"] == height and audios
        info = json.loads(Path(row.info_json_path).read_text(encoding="utf-8"))
        assert info["height"] == height
        # yt-dlp intentionally omits requested_formats from exported info JSON.
        # Its persisted composite ID/codecs plus ffprobe streams prove the merge.
        assert info["format_id"] == f"v{height}+audio"
        assert info["vcodec"] != "none" and info["acodec"] != "none"
        description = Path(row.description_path).read_text(encoding="utf-8").strip()
        assert description == "Distinct Q3 owned description"
        assert row.subtitle_paths
        subtitle = Path(row.subtitle_paths[0]).read_text(encoding="utf-8")
        assert subtitle.startswith("WEBVTT") and "Синтетические RU субтитры" in subtitle
        thumb = Path(row.thumbnail_path)
        assert thumb.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        return {
            "id": ident,
            "requested_quality": row.quality,
            "actual_height": videos[0]["height"],
            "audio_streams": len(audios),
            "artifact_count": len(paths),
            "subtitle": "owned synthetic ru",
            "description": True,
            "thumbnail_type": "PNG",
            "info_json": True,
            "persisted_readonly_reopen": True,
        }


def _cli_environment(root: Path, profile: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key, relative in {
        "APPDATA": "appdata",
        "LOCALAPPDATA": "local",
        "HOME": "home",
        "USERPROFILE": "home",
        "TMP": "temp",
        "TEMP": "temp",
        "TMPDIR": "temp",
        "XDG_CONFIG_HOME": "config",
        "XDG_DATA_HOME": "data",
        "XDG_CACHE_HOME": "cache",
        "YTDL_LOG_DIR": "logs",
    }.items():
        path = root / relative
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    env["YTDL_DATA_DIR"] = str(profile)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


@pytest.mark.parametrize("height", [1080, 1440, 2160])
@pytest.mark.parametrize("adapter", ["api", "cli", "mcp"])
def test_real_shared_quality_adapter_merge_sidecars_and_reopen(
    tmp_path: Path, quality_source, ffprobe_path, height: int, adapter: str
):
    profile, output = tmp_path / "profile", tmp_path / "out"
    args = _arguments(quality_source["url"], height)
    if adapter == "cli":
        # Source API prepares only settings, then closes before the real CLI owns data.
        with create_runtime(profile, settings_overrides={"output_dir": output}) as preparation:
            preparation.api.update_settings(preparation.api.get_settings())
        command = [
            sys.executable,
            "-m",
            "src.interfaces.cli",
            "--json",
            "--data-dir",
            str(profile),
            "queue",
            "add",
            args["url"],
            "--quality",
            args["quality"],
            "--type",
            "video",
            "--subtitle-lang",
            "ru",
            "--save-subtitles",
            "--save-description",
            "--save-thumbnail",
        ]
        child = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parent.parent,
            env=_cli_environment(tmp_path / "cli-selectors", profile),
            capture_output=True,
            text=True,
            timeout=35,
        )
        (tmp_path / "cli-native.json").write_text(
            json.dumps(
                {
                    "argv": command,
                    "native_exit": child.returncode,
                    "stdout": child.stdout,
                    "stderr": child.stderr,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        assert child.returncode == 0, child.stderr
        assert child.stderr == ""
        ident = json.loads(child.stdout)["task_id"]
    else:
        runtime = create_runtime(profile, settings_overrides={"output_dir": output})
        try:
            if adapter == "api":
                accepted = runtime.api.queue_add_download(**args)
                ident = accepted.task_id
                terminal = runtime.api.wait_for_download(ident, timeout=15)
            else:

                async def exercise():
                    async with Client(
                        create_mcp_server({"application_api": runtime.api})
                    ) as client:
                        result = await client.call_tool("add_download", args)
                        accepted = result.structured_content
                        assert "error" not in accepted, accepted
                        ident = accepted["task_id"]
                        terminal = await asyncio.to_thread(
                            runtime.api.wait_for_download, ident, timeout=15
                        )
                        wire = (
                            await client.call_tool("get_file_paths", {"id": ident})
                        ).structured_content
                        assert wire["quality"] == f"{height}p" and wire["status"] == "done", wire
                        return ident, terminal

                ident, terminal = asyncio.run(exercise())
            assert terminal and terminal.status == "done" and terminal.result_persisted
        finally:
            closed = runtime.close(cancel=True, wait=True)
        assert closed.closed and not closed.error_codes
    facts = _verify(profile, output, ident, height, ffprobe_path)
    (tmp_path / "physical-proof.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")


def test_requested_thumbnail_transfer_failure_is_not_full_success(
    tmp_path: Path, quality_source, ffprobe_path: Path
):
    profile, output = tmp_path / "profile", tmp_path / "out"
    runtime = create_runtime(profile, settings_overrides={"output_dir": output})
    try:
        args = _arguments(quality_source["url"].replace("owned.html", "missing-thumb.html"), 1080)
        ident = runtime.api.queue_add_download(**args).task_id
        terminal = runtime.api.wait_for_download(ident, timeout=15)
        assert (
            terminal and terminal.status == "failed" and terminal.error_code == "PARTIAL_DOWNLOAD"
        )
        assert terminal.result_persisted
    finally:
        closed = runtime.close(cancel=True, wait=True)
    assert closed.closed and not closed.error_codes
    with create_runtime(profile, read_only=True) as reopened:
        row = reopened.api.get_file_paths(ident)
        assert row.status == "failed" and row.error_code == "PARTIAL_DOWNLOAD"
        assert row.thumbnail_path is None
        media = Path(row.video_path)
        assert media.is_file() and media.is_relative_to(output)
        assert row.subtitle_paths and row.description_path and row.info_json_path
        physical = {p for p in output.rglob("*") if p.is_file()}
        assert {Path(p) for p in row.artifact_paths} == physical
        probe = subprocess.run(
            [str(ffprobe_path), "-v", "error", "-show_streams", "-of", "json", str(media)],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        streams = json.loads(probe.stdout)["streams"]
        assert {s["codec_type"] for s in streams} == {"video", "audio"}
        assert next(s for s in streams if s["codec_type"] == "video")["height"] == 1080


def test_source_unavailable_extras_are_distinct_from_transfer_failure(
    tmp_path: Path, quality_source
):
    profile, output = tmp_path / "profile", tmp_path / "out"
    runtime = create_runtime(profile, settings_overrides={"output_dir": output})
    try:
        args = _arguments(quality_source["url"].replace("owned.html", "no-extras.html"), 1080)
        ident = runtime.api.queue_add_download(**args).task_id
        terminal = runtime.api.wait_for_download(ident, timeout=15)
        assert terminal and terminal.status == "done" and terminal.result_persisted
    finally:
        closed = runtime.close(cancel=True, wait=True)
    assert closed.closed and not closed.error_codes
    with create_runtime(profile, read_only=True) as reopened:
        row = reopened.api.get_file_paths(ident)
        assert row.status == "done" and row.error_code is None
        assert (
            row.thumbnail_path is None and row.description_path is None and row.subtitle_paths == []
        )
        assert Path(row.video_path).is_file() and Path(row.info_json_path).is_file()
        info = json.loads(Path(row.info_json_path).read_text(encoding="utf-8"))
        assert (
            not info.get("description") and not info.get("thumbnail") and not info.get("subtitles")
        )
