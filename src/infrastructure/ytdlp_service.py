"""Сервис загрузки через yt-dlp.

Классы:
    YtDlpService: Реализация IDownloadService через yt-dlp + FFmpeg.
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from ..domain.models import AppSettings, DownloadTask, VideoInfo
from ..domain.models.app_settings import DownloadType, QualityOption
from ..domain.models.download_outcome import DownloadOutcome
from ..domain.models.download_task import DownloadStatus
from ..domain.protocols import IDownloadService
from .ffmpeg import find_ffmpeg
from .url_utils import parse_youtube_url

logger = logging.getLogger(__name__)

# Высота для каждого варианта качества
_QUALITY_HEIGHT: dict[QualityOption, Optional[int]] = {
    QualityOption.BEST: None,
    QualityOption.P1080: 1080,
    QualityOption.P720: 720,
    QualityOption.P480: 480,
    QualityOption.P360: 360,
    QualityOption.AUDIO: None,
}


def _build_format_string(task: DownloadTask) -> str:
    """Строит строку формата yt-dlp для заданных параметров качества."""
    if task.download_type == DownloadType.AUDIO:
        return "bestaudio[ext=m4a]/bestaudio/best"

    height = _QUALITY_HEIGHT.get(task.quality)
    if height is None:
        # Лучшее доступное видео + аудио
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

    # Видео до заданного разрешения + лучшее аудио
    return (
        f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo[height<={height}]+bestaudio"
        f"/best[height<={height}]"
        f"/best"
    )


class _CancelledError(Exception):
    """Cooperative cancellation, never a successful empty result."""


class _BackendLogger:
    """yt-dlp messages are untrusted content, not diagnostic templates."""

    def __init__(self) -> None:
        self.errors = 0

    def debug(self, message: object) -> None:
        logger.debug("ytdlp.message level=debug")

    def info(self, message: object) -> None:
        logger.info("ytdlp.message level=info")

    def warning(self, message: object) -> None:
        logger.warning("ytdlp.message reason_code=BACKEND_WARNING")

    def error(self, message: object) -> None:
        self.errors += 1
        logger.error("ytdlp.message reason_code=DOWNLOAD_FAILED")


class YtDlpService(IDownloadService):
    """One service per attempt; cancellation is sticky, paths come only from this attempt."""

    def __init__(self, ffmpeg_path: Optional[Path] = None) -> None:
        self._ffmpeg_path = ffmpeg_path or self._detect_ffmpeg()
        self._cancel_event = threading.Event()

    @staticmethod
    def _detect_ffmpeg() -> Optional[Path]:
        return find_ffmpeg()

    def _base_opts(self, settings: AppSettings) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": _BackendLogger(),
            "overwrites": False,
            "consoletitle": False,
        }
        if self._ffmpeg_path:
            opts["ffmpeg_location"] = str(self._ffmpeg_path.parent)
        if settings.proxy:
            opts["proxy"] = settings.proxy
        return opts

    def _check_cancel(self) -> None:
        if self._cancel_event.is_set():
            raise _CancelledError("Download cancelled")

    def fetch_info(self, url: str, settings: AppSettings) -> VideoInfo:
        self._check_cancel()
        import yt_dlp

        clean_url, is_playlist = parse_youtube_url(url)
        opts = self._base_opts(settings)
        opts.update(extract_flat="in_playlist", noplaylist=not is_playlist)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(clean_url, download=False)
                self._check_cancel()
                if data is None:
                    raise ValueError("Metadata unavailable")
                return self._parse_info(data)
        except _CancelledError:
            raise
        except Exception:
            logger.error("ytdlp.fetch_info.failed reason_code=DOWNLOAD_FAILED")
            raise ValueError("Metadata unavailable") from None

    @staticmethod
    def _parse_info(data: dict) -> VideoInfo:
        playlist = data.get("_type") == "playlist" or "entries" in data
        entries = data.get("entries") or []
        return VideoInfo(
            id=data.get("id", ""),
            title=data.get("title", ""),
            uploader=data.get("uploader", data.get("channel", "")),
            duration=data.get("duration", 0) or 0,
            description=data.get("description", "") or "",
            thumbnail_url=data.get("thumbnail", "") or "",
            available_subtitles=list((data.get("subtitles") or {}).keys()),
            available_auto_subs=list((data.get("automatic_captions") or {}).keys()),
            is_playlist=playlist,
            playlist_title=data.get("title", "") if playlist else "",
            playlist_count=len(entries),
        )

    def download(
        self,
        task: DownloadTask,
        settings: AppSettings,
        progress_callback: Optional[Callable[[float, float, int], None]] = None,
    ) -> DownloadOutcome:
        if self._cancel_event.is_set():
            return DownloadOutcome("cancelled")
        import yt_dlp
        from yt_dlp.postprocessor.common import PostProcessor
        from yt_dlp.utils import DownloadCancelled

        clean_url, is_playlist = parse_youtube_url(task.url)
        # A leased runtime allocates unique task IDs. Keep each task's checks, media
        # effects and final hooks in its own namespace, including on failure/cancel.
        # A native skip/final hook from another task cannot prove ownership here.
        root = settings.output_dir.resolve() / f"download-{task.id}"
        if task.playlist_title:
            outtmpl = str(
                root
                / _safe_dirname(task.playlist_title)
                / "%(playlist_index)03d - %(title)s"
                / "%(title)s.%(ext)s"
            )
        else:
            outtmpl = str(root / "%(title)s" / "%(title)s.%(ext)s")
        announced: set[Path] = set()
        preexisting: set[Path] = set()
        media: list[Path] = []
        last: dict[str, object] = {}

        def abort() -> None:
            if self._cancel_event.is_set():
                # The SDK deliberately rethrows this through ignoreerrors/playlist guards.
                raise DownloadCancelled("Download cancelled")

        def cancellation_filter(info: dict, *, incomplete: bool = False) -> None:
            abort()  # Also checked before advancing to another playlist entry.

        def path(value: object) -> Path | None:
            if not isinstance(value, (str, Path)) or not value:
                return None
            candidate = Path(value).resolve()
            return candidate if candidate.is_relative_to(root) else None

        def announce(value: object) -> Path | None:
            candidate = path(value)
            if candidate is not None and candidate not in preexisting:
                announced.add(candidate)
                return candidate
            return None

        def final_media(value: object) -> None:
            candidate = announce(value)
            if candidate is not None:
                media.append(candidate)
                key = "audio" if task.download_type == DownloadType.AUDIO else "video"
                last[key] = candidate
                last["scan_root"] = (
                    root / _safe_dirname(task.playlist_title)
                    if task.playlist_title
                    else candidate.parent
                )
                # Exact sidecar basenames, never a directory scan or newest-folder adoption.
                for key, suffix, enabled in (
                    ("info_json", ".info.json", True),
                    ("description", ".description", task.save_description),
                ):
                    sidecar = candidate.with_suffix(suffix)
                    if enabled and announce(sidecar) is not None:
                        last[key] = sidecar

        def capture(info: dict, *, completed: bool = False) -> None:
            for item in info.get("requested_downloads") or []:
                if isinstance(item, dict):
                    capture(item, completed=completed)
            # A returned metadata filepath alone is not proof of a completed media effect.
            # Successful yt-dlp processing always invokes its final post hook.
            if completed and path(info.get("filepath")) not in media:
                return
            for key in ("filename", "filepath", "_filename", "tmpfilename"):
                announce(info.get(key))
            subtitles = []
            for item in (info.get("requested_subtitles") or {}).values():
                if isinstance(item, dict) and (sub := announce(item.get("filepath"))) is not None:
                    subtitles.append(sub)
            if subtitles:
                last["subtitles"] = subtitles
            for item in info.get("thumbnails") or []:
                if isinstance(item, dict) and (thumb := announce(item.get("filepath"))) is not None:
                    last["thumbnail"] = thumb

        class _AttributionFencePP(PostProcessor):
            def __init__(self, downloader: Any, *, before_media: bool = False) -> None:
                super().__init__(downloader)
                self.before_media = before_media

            def run(self, info: dict[str, Any]) -> tuple[list[object], dict[str, Any]]:
                abort()
                filename = self._downloader.prepare_filename(info)
                target = path(filename)
                if target is not None:
                    candidates = [
                        target,
                        target.with_suffix(".mp4"),
                        target.with_suffix(".m4a"),
                        target.with_suffix(".description"),
                        target.with_suffix(".info.json"),
                    ]
                    candidates.extend(
                        target.with_suffix(suffix) for suffix in (".jpg", ".png", ".webp")
                    )
                    languages = {task.subtitle_lang, *(info.get("requested_subtitles") or {})}
                    candidates.extend(
                        target.with_suffix(f".{lang}.{ext}")
                        for lang in languages
                        for ext in ("vtt", "srt", "ass")
                    )
                    for candidate in candidates[:3] if self.before_media else candidates:
                        if candidate.is_file():
                            preexisting.add(candidate)
                    # Existing main files have no attempt attribution; never overwrite/adopt them.
                    if any(p.is_file() for p in candidates[:3]):
                        raise RuntimeError("Existing output is not attributable")
                return [], info

        def progress_hook(data: dict) -> None:
            capture(data)
            capture(data.get("info_dict") or {})
            abort()
            if data.get("status") == "downloading" and progress_callback is not None:
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                done = data.get("downloaded_bytes") or 0
                measured = getattr(progress_callback, "measured", None)
                if callable(measured):
                    measured(
                        done / total * 100 if total else None, data.get("speed"), data.get("eta")
                    )
                else:
                    progress_callback(
                        done / total * 100 if total else 0.0,
                        float(data.get("speed") or 0),
                        int(data.get("eta") or 0),
                    )

        def postprocessing_hook(data: dict) -> None:
            if data.get("postprocessor") == "_AttributionFence":
                return
            capture(data.get("info_dict") or {})
            abort()
            stage = getattr(progress_callback, "stage", None)
            if (
                callable(stage)
                and data.get("postprocessor") != "_AttributionFence"
                and data.get("status") in {"started", "processing"}
            ):
                stage(DownloadStatus.MERGING)

        def post_hook(filename: str) -> None:
            # SDK post_hooks catch ALL Exception as a failure. Capture the completed file;
            # observe cancellation at the next match/PP/progress boundary or final outcome.
            final_media(filename)

        opts = self._base_opts(settings)
        opts.update(
            {
                "match_filter": cancellation_filter,
                "format": _build_format_string(task),
                "outtmpl": outtmpl,
                "merge_output_format": "mp4" if task.download_type == DownloadType.VIDEO else None,
                "retries": 5,
                "fragment_retries": 5,
                "continuedl": True,
                "progress_hooks": [progress_hook],
                "postprocessor_hooks": [postprocessing_hook],
                "post_hooks": [post_hook],
                "writeinfojson": True,
                "writethumbnail": task.save_thumbnail,
                "writesubtitles": task.save_subtitles,
                "writeautomaticsub": task.save_subtitles,
                "subtitleslangs": [task.subtitle_lang, f"{task.subtitle_lang}-*"]
                if task.save_subtitles
                else [],
                "subtitlesformat": "vtt/srt",
                "writedescription": task.save_description,
                "restrictfilenames": False,
                "windowsfilenames": True,
                "noplaylist": not is_playlist,
                "ignoreerrors": is_playlist,
                "postprocessors": [],
            }
        )
        if task.download_type == DownloadType.AUDIO:
            opts["postprocessors"].append(
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "192"}
            )
        failed = False
        try:
            logger.info("ytdlp.download.start id=%d", task.id)
            with yt_dlp.YoutubeDL(opts) as ydl:
                # pre_process is before metadata writes; before_dl also sees final selected formats.
                ydl.add_post_processor(_AttributionFencePP(ydl), when="pre_process")
                ydl.add_post_processor(
                    _AttributionFencePP(ydl, before_media=True), when="before_dl"
                )
                data = ydl.extract_info(clean_url, download=True)
                if not data:
                    failed = True
                elif "entries" in data:
                    entries = list(data.get("entries") or [])
                    failed = not entries or any(item is None for item in entries)
                    for item in entries:
                        if isinstance(item, dict):
                            capture(item, completed=True)
                else:
                    capture(data, completed=True)
        except (DownloadCancelled, _CancelledError):
            pass
        except Exception:
            failed = True
        known = tuple(
            sorted((p for p in announced if p not in preexisting and p.is_file()), key=str)
        )
        primary = next((p for p in reversed(media) if p in known), None)
        if primary is not None:
            last["audio" if task.download_type == DownloadType.AUDIO else "video"] = primary
        reporter = opts["logger"]
        failed = failed or reporter.errors > 0
        # An independent failure remains failed, even if a cancel request races it.
        status: Literal["completed", "cancelled", "failed"] = (
            "failed" if failed else "cancelled" if self._cancel_event.is_set() else "completed"
        )
        if status == "completed" and primary is None:
            status = "failed"
        code = (
            ("PARTIAL_DOWNLOAD" if primary is not None else "DOWNLOAD_FAILED")
            if status == "failed"
            else None
        )
        for key in ("video", "audio", "description", "thumbnail", "info_json"):
            if last.get(key) not in known:
                last.pop(key, None)
        subs = last.get("subtitles")
        last["subtitles"] = [p for p in subs if p in known] if isinstance(subs, list) else []
        last["artifact_paths"] = list(known)
        logger.log(
            logging.ERROR if code else logging.INFO,
            "ytdlp.download.terminal id=%d status=%s reason_code=%s count=%d",
            task.id,
            status,
            code,
            len(known),
        )
        return DownloadOutcome.from_paths(last, status=status, error_code=code)

    def cancel(self) -> None:
        self._cancel_event.set()


def _safe_dirname(name: str) -> str:
    """Очищает строку для использования как имя папки Windows."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.strip(". ")
    return name[:128] if name else "Unknown"
