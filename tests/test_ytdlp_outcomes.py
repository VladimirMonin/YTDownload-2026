"""Real YtDlpService; only YoutubeDL's network/media-processing boundary is replaced."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yt_dlp

from src.bootstrap import create_runtime
from src.domain.models import AppSettings, DownloadTask
from src.domain.models.app_settings import DownloadType
from src.domain.models.download_task import DownloadStatus
from src.infrastructure.repositories import JsonHistoryRepository
from src.infrastructure.ytdlp_service import YtDlpService


class YoutubeBoundary:
    def __init__(self, opts, scenario):
        self.params, self.scenario, self.processors = opts, scenario, {}
        self.closed = False
        self._postprocessor_hooks = opts.get("postprocessor_hooks", [])

    def evaluate_outtmpl(self, template, data):
        return template

    def to_console_title(self, *args):
        pass  # Real opts disable console title; no network/media behavior is replaced here.

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def add_post_processor(self, processor, when):
        self.processors.setdefault(when, []).append(processor)

    def report_error(self, message, **kwargs):
        self.params["logger"].error(str(message) + str(kwargs.get("tb", "")))

    def prepare_filename(self, info):
        return info["source_path"]

    def before(self, info, stage="pre_process"):
        for processor in self.processors[stage]:
            processor.run(info)

    def extract_info(self, url, download):
        return self.scenario(self, url, download)

    def progress(self, data):
        for callback in self.params["progress_hooks"]:
            callback(data)

    def post(self, info):
        for callback in self.params["postprocessor_hooks"]:
            callback(
                {"status": "started", "postprocessor": "FFmpegExtractAudio", "info_dict": info}
            )

    def finished(self, filename):
        for callback in self.params["post_hooks"]:
            callback(str(filename))


def install_boundary(monkeypatch, scenario):
    instances = []

    def factory(opts):
        instance = YoutubeBoundary(opts, scenario)
        instances.append(instance)
        return instance

    monkeypatch.setattr(yt_dlp, "YoutubeDL", factory)
    return instances


def settings(tmp_path):
    return AppSettings(output_dir=tmp_path / "output")


def task(kind=DownloadType.VIDEO, playlist=""):
    return DownloadTask(
        1,
        "https://example.invalid/owned",
        download_type=kind,
        playlist_title=playlist,
        save_description=True,
    )


def test_sticky_cancel_never_constructs_downloader(monkeypatch, tmp_path: Path) -> None:
    instances = install_boundary(
        monkeypatch, lambda *args: pytest.fail("cancel must precede network")
    )
    service = YtDlpService(ffmpeg_path=tmp_path / "ffmpeg")
    service.cancel()
    assert service.download(task(), settings(tmp_path)).status == "cancelled"
    assert service.download(task(), settings(tmp_path)).status == "cancelled"
    assert instances == []


def test_no_newest_folder_adoption_on_empty_result(monkeypatch, tmp_path: Path) -> None:
    old = tmp_path / "output/download-1/newer/unrelated.mp4"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"do not attribute these bytes")
    instances = install_boundary(monkeypatch, lambda *args: {"id": "empty", "title": "empty"})
    result = YtDlpService(ffmpeg_path=tmp_path / "ffmpeg").download(task(), settings(tmp_path))
    assert result.status == "failed" and result.error_code == "DOWNLOAD_FAILED"
    assert result.video is None and result.artifact_paths == ()
    assert old.read_bytes() == b"do not attribute these bytes"
    assert all(instance.closed for instance in instances)


def test_returned_unrelated_filepath_is_not_a_successful_attempt(
    monkeypatch, tmp_path: Path
) -> None:
    foreign = tmp_path / "output/download-1/foreign.mp4"
    foreign.parent.mkdir(parents=True)
    foreign.write_bytes(b"unchanged foreign metadata target")
    install_boundary(monkeypatch, lambda *args: {"id": "unrelated", "filepath": str(foreign)})
    result = YtDlpService(ffmpeg_path=tmp_path / "ffmpeg").download(task(), settings(tmp_path))
    assert result.status == "failed" and result.video is None
    assert result.artifact_paths == ()
    assert foreign.read_bytes() == b"unchanged foreign metadata target"


def test_real_postprocessing_hooks_attribute_final_audio_and_sidecars(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "output/download-1/item/item.webm"
    final = source.with_suffix(".m4a")
    subtitle = source.with_suffix(".ru.vtt")
    foreign = source.parent / "unrelated.m4a"
    foreign.parent.mkdir(parents=True)
    foreign.write_bytes(b"older unrelated audio")

    def scenario(ydl, url, download):
        info = {"id": "item", "title": "item", "source_path": str(source), "ext": "webm"}
        ydl.before(info)
        description = final.with_suffix(".description")
        metadata = final.with_suffix(".info.json")
        description.write_bytes(b"description from this attempt")
        metadata.write_text('{"id":"item"}', encoding="utf-8")
        ydl.before(info, "before_dl")
        source.write_bytes(b"new intermediate audio")
        ydl.progress({"status": "finished", "filename": str(source), "info_dict": info})
        ydl.post(info)
        final.write_bytes(b"postprocessed owned audio")
        subtitle.write_bytes(b"WEBVTT\n\nowned subtitle")
        info.update(
            filepath=str(final), ext="m4a", requested_subtitles={"ru": {"filepath": str(subtitle)}}
        )
        ydl.finished(final)
        return info

    instances = install_boundary(monkeypatch, scenario)

    class Observer:
        def __init__(self):
            self.stages = []

        def __call__(self, *args):
            pass

        def stage(self, value):
            self.stages.append(value)

    observer = Observer()
    result = YtDlpService(ffmpeg_path=tmp_path / "ffmpeg").download(
        task(DownloadType.AUDIO),
        settings(tmp_path),
        observer,
    )
    assert result.status == "completed" and result.audio == final
    assert result.video is None and result.subtitles == (subtitle,)
    assert observer.stages == [DownloadStatus.MERGING]
    assert result.description.read_bytes() == b"description from this attempt"
    assert result.info_json.read_text(encoding="utf-8") == '{"id":"item"}'
    assert final.read_bytes() == b"postprocessed owned audio"
    assert foreign not in result.artifact_paths and foreign.read_bytes() == b"older unrelated audio"
    assert instances[0].params["overwrites"] is False
    assert all(instance.closed for instance in instances)


def test_playlist_partial_keeps_only_known_results_and_foreign_bytes(
    monkeypatch, tmp_path: Path
) -> None:
    media = tmp_path / "output/download-1/list/001 - one/one.mp4"
    foreign = tmp_path / "output/download-1/newer/foreign.mp4"
    media.parent.mkdir(parents=True)
    foreign.parent.mkdir(parents=True)
    foreign.write_bytes(b"unrelated newer file")

    def scenario(ydl, url, download):
        info = {"id": "one", "source_path": str(media), "title": "one", "ext": "mp4"}
        ydl.before(info)
        ydl.before(info, "before_dl")
        media.write_bytes(b"first playlist item actually completed")
        info["filepath"] = str(media)
        ydl.progress({"status": "finished", "filename": str(media), "info_dict": info})
        ydl.finished(media)
        ydl.params["logger"].error("PRIVATE_PLAYLIST_FAILURE_URL_PROXY_PATH")
        return {"_type": "playlist", "entries": [info, None]}

    instances = install_boundary(monkeypatch, scenario)
    result = YtDlpService(ffmpeg_path=tmp_path / "ffmpeg").download(
        task(playlist="list"), settings(tmp_path)
    )
    assert result.status == "failed" and result.error_code == "PARTIAL_DOWNLOAD"
    assert result.video == media and media in result.artifact_paths
    assert foreign not in result.artifact_paths and foreign.read_bytes() == b"unrelated newer file"
    assert media.read_bytes() == b"first playlist item actually completed"
    assert all(instance.closed for instance in instances)


@pytest.mark.parametrize("independent_failure", [False, True])
def test_cancel_or_failure_retains_explicit_partial_files(
    monkeypatch, tmp_path: Path, independent_failure: bool
) -> None:
    partial = tmp_path / "output/download-1/owned.mp4.part"
    partial.parent.mkdir(parents=True)
    service = YtDlpService(ffmpeg_path=tmp_path / "ffmpeg")

    def scenario(ydl, url, download):
        partial.write_bytes(b"known incomplete owned bytes")
        ydl.progress({"status": "downloading", "tmpfilename": str(partial)})
        service.cancel()
        if independent_failure:
            raise RuntimeError("PRIVATE_INDEPENDENT_BACKEND_FAILURE")
        ydl.progress({"status": "downloading", "tmpfilename": str(partial)})
        pytest.fail("sticky token must stop at the real hook")

    instances = install_boundary(monkeypatch, scenario)
    result = service.download(task(), settings(tmp_path))
    assert result.status == ("failed" if independent_failure else "cancelled")
    assert result.artifact_paths == (partial,)
    assert partial.read_bytes() == b"known incomplete owned bytes"
    assert all(instance.closed for instance in instances)


def test_playlist_cancel_survives_actual_sdk_exception_guard(monkeypatch, tmp_path: Path) -> None:
    # Preserve the installed SDK's real control flow, replacing only network/media extraction.
    guard = yt_dlp.YoutubeDL._handle_extraction_exceptions
    monkeypatch.setattr(YoutubeBoundary, "extract_info", guard(YoutubeBoundary.extract_info))
    partial = tmp_path / "output/download-1/guarded.mp4.part"
    partial.parent.mkdir(parents=True)
    service = YtDlpService(ffmpeg_path=tmp_path / "ffmpeg")

    def scenario(ydl, url, download):
        partial.write_bytes(b"cancelled within guarded playlist extraction")
        service.cancel()
        ydl.progress({"status": "downloading", "tmpfilename": str(partial)})
        pytest.fail("cancellation must escape the actual SDK guard")

    instances = install_boundary(monkeypatch, scenario)
    request = task(playlist="owned")
    request.url = "https://www.youtube.com/playlist?list=OWNED_SYNTHETIC_GUARD"
    result = service.download(request, settings(tmp_path))
    assert instances[0].params["ignoreerrors"] is True
    assert result.status == "cancelled" and result.error_code is None
    assert result.artifact_paths == (partial,)
    assert partial.read_bytes() == b"cancelled within guarded playlist extraction"
    assert all(instance.closed for instance in instances)


def test_cancel_after_final_hook_stops_next_playlist_entry_without_false_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    media = tmp_path / "output/download-1/one.mp4"
    media.parent.mkdir(parents=True)
    service = YtDlpService(ffmpeg_path=tmp_path / "ffmpeg")

    def scenario(ydl, url, download):
        info = {"id": "one", "source_path": str(media), "ext": "mp4"}
        ydl.before(info)
        ydl.before(info, "before_dl")
        media.write_bytes(b"completed before playlist cancellation")
        ydl.progress({"status": "finished", "filename": str(media)})
        service.cancel()
        try:
            ydl.finished(media)
        except Exception as exc:
            # Same broad SDK post_hooks guard: cancellation must not be reported as failure here.
            ydl.params["logger"].error(str(exc))
        ydl.params["match_filter"]({"id": "two"}, incomplete=True)
        pytest.fail("next playlist entry must not pass the actual cancellation filter")

    instances = install_boundary(monkeypatch, scenario)
    request = task(playlist="owned")
    request.url = "https://www.youtube.com/playlist?list=OWNED_SYNTHETIC_HOOK"
    result = service.download(request, settings(tmp_path))
    assert result.status == "cancelled" and result.error_code is None
    assert result.video == media and result.artifact_paths == (media,)
    assert media.read_bytes() == b"completed before playlist cancellation"
    assert all(instance.closed for instance in instances)


def test_existing_final_file_refused_without_overwrite_or_adoption(
    monkeypatch, tmp_path: Path
) -> None:
    existing = tmp_path / "output/download-1/item.mp4"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"pre-existing unrelated same title")

    def scenario(ydl, url, download):
        info = {"id": "new-id", "source_path": str(existing), "title": "item", "ext": "mp4"}
        ydl.before(info)
        pytest.fail("collision must be refused before the network/media effect")

    instances = install_boundary(monkeypatch, scenario)
    result = YtDlpService(ffmpeg_path=tmp_path / "ffmpeg").download(task(), settings(tmp_path))
    assert result.status == "failed" and result.artifact_paths == ()
    assert existing.read_bytes() == b"pre-existing unrelated same title"
    assert all(instance.closed for instance in instances)


@pytest.mark.parametrize("partial_failure", [False, True])
def test_real_adapter_playlist_through_api_json_readback_and_measured_zero(
    monkeypatch,
    tmp_path: Path,
    partial_failure: bool,
) -> None:
    import threading

    progressed, release = threading.Event(), threading.Event()
    output = tmp_path / "output"
    foreign = output / "newer/foreign.mp4"
    foreign.parent.mkdir(parents=True)
    foreign.write_bytes(b"old unrelated bytes stay untouched")
    os.utime(foreign.parent, (2000000000, 2000000000))
    owned = []

    def scenario(ydl, url, download):
        if not download:
            return {
                "_type": "playlist",
                "title": "Owned playlist",
                "entries": [{"id": "one"}, {"id": "two"}],
            }
        entries = []
        for index in (1, 2):
            if index == 2 and partial_failure:
                ydl.params["logger"].error("PRIVATE_PARTIAL_PLAYLIST_MARKER")
                entries.append(None)
                continue
            media = output / "download-1" / "Owned playlist" / str(index) / f"item-{index}.mp4"
            media.parent.mkdir(parents=True)
            info = {"id": str(index), "source_path": str(media), "title": str(index), "ext": "mp4"}
            ydl.before(info)
            ydl.before(info, "before_dl")
            if index == 1:
                ydl.progress(
                    {"status": "downloading", "total_bytes": 100, "downloaded_bytes": 0, "eta": 0}
                )
                progressed.set()
                assert release.wait(5)
            media.write_bytes(f"actually-produced-item-{index}".encode())
            owned.append(media)
            info["filepath"] = str(media)
            ydl.progress({"status": "finished", "filename": str(media), "info_dict": info})
            ydl.finished(media)
            entries.append(info)
        assert ydl.params["noplaylist"] is False
        return {"_type": "playlist", "entries": entries}

    instances = install_boundary(monkeypatch, scenario)
    runtime = create_runtime(
        tmp_path / "runtime",
        settings_overrides={"output_dir": output},
        backend_factory=lambda: YtDlpService(tmp_path / "ffmpeg"),
    )
    events = []
    runtime.event_bus.subscribe("download.done", lambda **kw: events.append(kw["task_id"]))
    try:
        ident = runtime.api.queue_add_download(
            url="https://www.youtube.com/playlist?list=OWNED_SYNTHETIC_LIST",
        ).task_id
        assert progressed.wait(5)
        measured = runtime.api.get_task(ident)
        assert measured.status == "downloading"
        assert measured.progress == 0 and measured.speed is None and measured.eta_seconds == 0
        release.set()
        result = runtime.api.wait_for_download(ident, timeout=5)
        assert result.status == ("failed" if partial_failure else "done")
        assert result.error_code == ("PARTIAL_DOWNLOAD" if partial_failure else None)
        assert result.result_persisted
        assert result.artifact_paths == [str(p) for p in owned]
        assert events == ([] if partial_failure else [ident])
        assert runtime.api.get_file_paths(ident).video_path == str(owned[-1])
    finally:
        release.set()
        closed = runtime.close(cancel=False, wait=True)
    assert closed.closed and not closed.error_codes
    stored = JsonHistoryRepository(tmp_path / "runtime/data").get_by_id(ident)
    assert stored.status.value == result.status and stored.artifact_paths == owned
    assert stored.error_code == result.error_code
    assert foreign.read_bytes() == b"old unrelated bytes stay untouched"
    assert foreign not in stored.artifact_paths
    assert all(
        p.read_bytes() == f"actually-produced-item-{index}".encode()
        for index, p in enumerate(owned, 1)
    )
    assert all(instance.closed for instance in instances)


@pytest.mark.parametrize("b_outcome", ["done", "cancelled", "failed"])
def test_native_same_title_tasks_own_distinct_effects_and_partial_paths(
    monkeypatch,
    tmp_path: Path,
    b_outcome: str,
) -> None:
    import threading

    from yt_dlp.downloader.common import FileDownloader

    passed = {key: threading.Event() for key in ("a", "b")}
    a_written, b_ready, release_b = threading.Event(), threading.Event(), threading.Event()
    targets, physical, native_results, native_calls = {}, [], [], []
    native_download = FileDownloader.download
    real_class = yt_dlp.YoutubeDL

    class OwnedFD(FileDownloader):
        FD_NAME = "owned-same-title-media-edge"

        def real_download(self, filename, info):
            key = info["id"]
            target = Path(filename)
            assert target.resolve().is_relative_to(tmp_path / "output")
            target.parent.mkdir(parents=True, exist_ok=True)
            physical.append(key)
            if key == "b":
                partial = Path(str(target) + ".part")
                partial.write_bytes(b"owned incomplete B bytes")
                self._hook_progress({"status": "downloading", "tmpfilename": str(partial)}, info)
                b_ready.set()
                assert release_b.wait(8), "B effect must be released in finally"
                if b_outcome == "failed":
                    raise RuntimeError("OWNED_INDEPENDENT_B_FAILURE")
                if b_outcome == "cancelled":
                    self._hook_progress(
                        {"status": "downloading", "tmpfilename": str(partial)}, info
                    )
                    pytest.fail("real cancellation hook must stop B")
            target.write_bytes(("actually-produced-by-" + key).encode())
            self._hook_progress(
                {
                    "filename": str(target),
                    "status": "finished",
                    "total_bytes": target.stat().st_size,
                },
                info,
            )
            if key == "a":
                a_written.set()
            return True

    class NativeEdge(real_class):
        def __init__(self, params):
            super().__init__(
                {**params, "check_formats": False, "fixup": "never", "cachedir": False}
            )

        def extract_info(self, url, download=True, **kwargs):
            key = url.rsplit("/", 1)[-1]
            info = {
                "id": key,
                "title": "shared-title",
                "ext": "mp4",
                "url": "https://example.invalid/owned-media/" + key,
                "webpage_url": url,
                "extractor": "OwnedEdge",
                "extractor_key": "OwnedEdge",
                "vcodec": "avc1",
                "acodec": "mp4a",
                "height": 720,
                "width": 1280,
                "format_id": "owned",
                "protocol": "https",
            }
            return self.process_ie_result(info, download=True) if download else info

        def pre_process(self, info, key="pre_process", files_to_move=None):
            result = super().pre_process(info, key, files_to_move)
            if key == "before_dl":
                ident = info["id"]
                target = Path(self.prepare_filename(result[0]))
                assert not target.exists(), "both real fences must precede each own media effect"
                targets[ident] = target
                passed[ident].set()
                if ident == "a":
                    assert passed["b"].wait(8)
                else:
                    assert a_written.wait(8)
            return result

        def dl(self, name, info, subtitle=False, test=False):
            downloader = OwnedFD(self, self.params)
            for hook in self._progress_hooks:
                downloader.add_progress_hook(hook)
            native_calls.append(info["id"])
            result = downloader.download(name, info, subtitle=subtitle)
            native_results.append((info["id"], result))
            return result

    monkeypatch.setattr(yt_dlp, "YoutubeDL", NativeEdge)
    runtime = create_runtime(
        tmp_path / "runtime",
        settings_overrides={
            "output_dir": tmp_path / "output",
            "proxy": "",
            "max_concurrent": 2,
        },
        backend_factory=lambda: YtDlpService(tmp_path / "ffmpeg"),
    )
    try:
        api = runtime.api
        a = api.queue_add_download(url="https://example.invalid/a").task_id
        assert passed["a"].wait(5), "A native metadata write must precede B admission"
        b = api.queue_add_download(url="https://example.invalid/b").task_id
        assert b_ready.wait(8), "independent B must reach real_download, not native skip A"
        first = api.wait_for_download(a, timeout=8)
        assert first.status == "done" and first.result_persisted
        assert targets["a"] != targets["b"]
        assert targets["a"].read_bytes() == b"actually-produced-by-a"
        if b_outcome == "cancelled":
            assert api.cancel_download(b).status == "cancel_requested"
            assert api.get_task(b).status == "downloading"
        release_b.set()
        second = api.wait_for_download(b, timeout=8)
        assert second.status == b_outcome and second.result_persisted
        assert native_calls == physical == ["a", "b"]
        assert ("a", (True, True)) in native_results
        if b_outcome == "done":
            assert ("b", (True, True)) in native_results
            assert targets["b"].read_bytes() == b"actually-produced-by-b"
            assert str(targets["b"]) in second.artifact_paths
        else:
            partial = Path(str(targets["b"]) + ".part")
            assert partial.read_bytes() == b"owned incomplete B bytes"
            assert str(partial) in second.artifact_paths and not targets["b"].exists()
        assert not set(first.artifact_paths) & set(second.artifact_paths)
        assert all(
            Path(p).is_relative_to(tmp_path / "output" / f"download-{b}")
            for p in second.artifact_paths
        )
        assert targets["a"].read_bytes() == b"actually-produced-by-a"
        assert FileDownloader.download is native_download
    finally:
        release_b.set()
        a_written.set()
        for signal in passed.values():
            signal.set()
        closed = runtime.close(cancel=False, wait=True)
    assert closed.closed and not closed.pending_task_ids and not closed.error_codes
    stored = JsonHistoryRepository(tmp_path / "runtime/data")
    assert stored.get_by_id(a).status.value == first.status
    assert stored.get_by_id(b).status.value == second.status
    assert stored.get_by_id(a).artifact_paths == [Path(p) for p in first.artifact_paths]
    assert stored.get_by_id(b).artifact_paths == [Path(p) for p in second.artifact_paths]
    assert targets["a"].read_bytes() == b"actually-produced-by-a"


def test_connected_backend_coordinator_subscriber_diagnostics_real_sinks(tmp_path: Path) -> None:
    script = r"""
import logging, sys
from pathlib import Path
import yt_dlp
from src.bootstrap import create_runtime
from src.core.logging_setup import setup_logging
from src.infrastructure.ytdlp_service import YtDlpService
root = Path(sys.argv[1])
marker = "PRIVATE_CONTENT_URL_PROXY_TITLE_EXCEPTION_PATH"
class BrokenYoutubeDL:
    def __init__(self, opts): self.opts = opts
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def add_post_processor(self, *args, **kwargs): pass
    def extract_info(self, *args, **kwargs):
        self.opts['logger'].warning(marker)
        self.opts['logger'].error(marker)
        raise RuntimeError(marker)
yt_dlp.YoutubeDL = BrokenYoutubeDL
setup_logging(log_dir=root/'logs', stream=sys.stderr)
runtime = create_runtime(root/'data-root', backend_factory=lambda: YtDlpService(root/'ffmpeg'),
                         settings_overrides={'output_dir':root/'output'})
def broken(**kwargs): raise RuntimeError(marker)
runtime.event_bus.subscribe('download.queued', broken)
try:
    ident = runtime.api.queue_add_download(url='https://example.invalid/'+marker).task_id
    result = runtime.api.wait_for_download(ident, timeout=5)
    assert result.status == 'failed' and result.error_code == 'DOWNLOAD_FAILED'
finally:
    closed = runtime.close(cancel=False, wait=True)
    logging.shutdown()
assert closed.closed and not closed.pending_task_ids
"""
    child = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=Path(__file__).resolve().parent.parent,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=25,
    )
    (tmp_path / "diagnostics.stdout.txt").write_text(child.stdout, encoding="utf-8")
    (tmp_path / "diagnostics.stderr.txt").write_text(child.stderr, encoding="utf-8")
    (tmp_path / "diagnostics.native-exit.txt").write_text(str(child.returncode), encoding="utf-8")
    assert child.returncode == 0, child.stderr
    for output in (
        child.stderr,
        (tmp_path / "logs/app.log").read_text(encoding="utf-8"),
        (tmp_path / "logs/app.error.log").read_text(encoding="utf-8"),
    ):
        assert output
        assert "coordinator.failed id=1 reason_code=DOWNLOAD_FAILED" in output
        assert "ytdlp.download.terminal id=1 status=failed" in output
        assert "event.handler.failed id=1 reason_code=SUBSCRIBER_FAILED" in output
        assert "PRIVATE_CONTENT" not in output
        assert "example.invalid" not in output
        assert str(tmp_path) not in output
    assert child.stdout == ""
