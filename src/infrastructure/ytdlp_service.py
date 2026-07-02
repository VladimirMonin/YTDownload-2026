"""Сервис загрузки через yt-dlp.

Классы:
    YtDlpService: Реализация IDownloadService через yt-dlp + FFmpeg.
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from ..domain.models import AppSettings, DownloadTask, VideoInfo
from ..domain.models.app_settings import DownloadType, QualityOption
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
    """Внутреннее исключение для отмены загрузки."""


class YtDlpService(IDownloadService):
    """Реализация сервиса загрузки через yt-dlp.

    Attributes:
        _ffmpeg_path: Путь к исполняемому файлу ffmpeg.
        _cancel_event: Событие отмены текущей загрузки.
    """

    def __init__(self, ffmpeg_path: Optional[Path] = None) -> None:
        self._ffmpeg_path = ffmpeg_path or self._detect_ffmpeg()
        self._cancel_event = threading.Event()

    @staticmethod
    def _detect_ffmpeg() -> Optional[Path]:
        """Ищет ffmpeg в env, vendor/ffmpeg/bin или системном PATH."""
        return find_ffmpeg()

    def _base_opts(self, settings: AppSettings) -> dict[str, Any]:
        """Строит базовый словарь опций yt-dlp."""
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
        if self._ffmpeg_path:
            opts["ffmpeg_location"] = str(self._ffmpeg_path.parent)
        if settings.proxy:
            opts["proxy"] = settings.proxy
        return opts

    def fetch_info(self, url: str, settings: AppSettings) -> VideoInfo:
        """Получает метаданные без скачивания.

        Args:
            url: URL видео или плейлиста.
            settings: Настройки приложения.

        Returns:
            VideoInfo с метаданными.

        Raises:
            ValueError: Если URL недоступен.
        """
        import yt_dlp  # Локальный импорт — не загрязняем domain

        clean_url, is_playlist = parse_youtube_url(url)

        opts = self._base_opts(settings)
        opts["extract_flat"] = "in_playlist"  # Быстрое извлечение для плейлистов
        opts["noplaylist"] = not is_playlist

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(clean_url, download=False)
                if data is None:
                    raise ValueError("Failed to extract info")
                return self._parse_info(data)
        except Exception as exc:
            logger.error("ytdlp.fetch_info.failed url_len=%d", len(url), exc_info=True)
            raise ValueError(f"Не удалось получить информацию: {exc}") from exc

    @staticmethod
    def _parse_info(data: dict) -> VideoInfo:
        """Разбирает сырые данные yt-dlp в VideoInfo."""
        is_playlist = data.get("_type") == "playlist" or "entries" in data

        entries = data.get("entries", [])
        count = len(entries) if entries else 0

        # Для одиночного видео берём его данные напрямую
        return VideoInfo(
            id=data.get("id", ""),
            title=data.get("title", ""),
            uploader=data.get("uploader", data.get("channel", "")),
            duration=data.get("duration", 0) or 0,
            description=data.get("description", "") or "",
            thumbnail_url=data.get("thumbnail", "") or "",
            available_subtitles=list((data.get("subtitles") or {}).keys()),
            available_auto_subs=list((data.get("automatic_captions") or {}).keys()),
            is_playlist=is_playlist,
            playlist_title=data.get("title", "") if is_playlist else "",
            playlist_count=count,
        )

    def download(
        self,
        task: DownloadTask,
        settings: AppSettings,
        progress_callback: Optional[Callable[[float, float, int], None]] = None,
    ) -> dict[str, Any]:
        """Скачивает видео согласно заданию.

        Args:
            task: Задание на загрузку.
            settings: Настройки приложения (proxy, output_dir и др.).
            progress_callback: Вызывается с (percent, speed_bps, eta_sec).

        Returns:
            Словарь путей к созданным файлам.

        Raises:
            RuntimeError: При ошибке загрузки.
        """
        import yt_dlp  # Локальный импорт

        self._cancel_event.clear()
        output_dir = settings.output_dir
        clean_url, is_playlist = parse_youtube_url(task.url)

        # Строим путь вывода
        if task.playlist_title:
            safe_playlist = _safe_dirname(task.playlist_title)
            outtmpl = str(
                output_dir
                / safe_playlist
                / "%(playlist_index)03d - %(title)s"
                / "%(title)s.%(ext)s"
            )
            scan_root = output_dir / safe_playlist
        else:
            outtmpl = str(output_dir / "%(title)s" / "%(title)s.%(ext)s")
            scan_root = output_dir

        # Отслеживаем созданные файлы: папка видео
        video_folder: dict[str, Optional[Path]] = {"path": None}

        def progress_hook(d: dict) -> None:
            if self._cancel_event.is_set():
                raise _CancelledError("Download cancelled")

            if d["status"] == "downloading" and progress_callback:
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0) or 0
                percent = (downloaded / total * 100.0) if total > 0 else 0.0
                speed = d.get("speed") or 0.0
                eta = d.get("eta") or 0
                progress_callback(percent, float(speed), int(eta))

            if d["status"] == "finished":
                # Запоминаем папку, где лежит файл
                fname = d.get("filename") or d.get("info_dict", {}).get("filename")
                if fname:
                    video_folder["path"] = Path(fname).parent
                    logger.info("ytdlp.download.finished ext=%s", Path(fname).suffix)

        # Настройки yt-dlp — базовые (proxy, ffmpeg) + специфичные для загрузки
        opts = self._base_opts(settings)
        opts.update({
            "format": _build_format_string(task),
            "outtmpl": outtmpl,
            "merge_output_format": "mp4" if task.download_type == DownloadType.VIDEO else None,
            "retries": 5,
            "fragment_retries": 5,
            "continuedl": True,
            "progress_hooks": [progress_hook],
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
            "ignoreerrors": is_playlist,  # Продолжать при ошибках только в плейлисте
            "postprocessors": [],
        })

        # Audio-only постобработчик
        if task.download_type == DownloadType.AUDIO:
            opts["postprocessors"].append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "192",
                }
            )

        logger.info(
            "ytdlp.download.start fmt=%s subs=%s is_playlist=%s",
            task.download_type.value
            if hasattr(task.download_type, "value")
            else task.download_type,
            task.save_subtitles,
            is_playlist,
        )

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([clean_url])
        except _CancelledError:
            logger.info("ytdlp.download.cancelled")
            return self._empty_result()
        except Exception as exc:
            logger.error("ytdlp.download.failed", exc_info=True)
            raise RuntimeError(f"Ошибка загрузки: {exc}") from exc

        # Сканируем созданные файлы
        folder = video_folder["path"]
        if folder is None:
            # Пытаемся найти папку сами
            folder = _find_newest_folder(scan_root)

        if folder and folder.exists():
            result = _scan_folder(folder, task.download_type)
            # Для плейлиста — папка плейлиста; для одиночного видео — папка видео
            result["scan_root"] = scan_root if task.playlist_title else folder
            return result

        return self._empty_result()

    def cancel(self) -> None:
        """Отменяет текущую загрузку."""
        self._cancel_event.set()

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "video": None,
            "audio": None,
            "subtitles": [],
            "description": None,
            "thumbnail": None,
            "info_json": None,
            "scan_root": None,
        }


def _safe_dirname(name: str) -> str:
    """Очищает строку для использования как имя папки Windows."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.strip(". ")
    return name[:128] if name else "Unknown"


def _find_newest_folder(root: Path) -> Optional[Path]:
    """Находит самую новую папку в root (для случая когда путь неизвестен)."""
    if not root.exists():
        return None
    folders = [p for p in root.iterdir() if p.is_dir()]
    if not folders:
        return None
    return max(folders, key=lambda p: p.stat().st_mtime)


def _scan_folder(folder: Path, download_type: DownloadType) -> dict[str, Any]:
    """Сканирует папку и возвращает dict с путями к найденным файлам.

    Args:
        folder: Папка для сканирования.
        download_type: Тип загрузки.

    Returns:
        Словарь с путями к файлам.
    """
    result: dict[str, Any] = {
        "video": None,
        "audio": None,
        "subtitles": [],
        "description": None,
        "thumbnail": None,
        "info_json": None,
    }

    if not folder.exists():
        return result

    for f in folder.iterdir():
        if not f.is_file():
            continue
        ext = f.suffix.lower()

        if download_type == DownloadType.VIDEO and ext in (".mp4", ".mkv", ".webm"):
            if result["video"] is None:
                result["video"] = f
        elif download_type == DownloadType.AUDIO and ext in (
            ".m4a",
            ".opus",
            ".mp3",
            ".ogg",
            ".webm",
        ):
            if result["audio"] is None:
                result["audio"] = f
        elif ext in (".vtt", ".srt", ".ass"):
            result["subtitles"].append(f)
        elif f.name.endswith(".description"):
            result["description"] = f
        elif ext in (".webp", ".jpg", ".jpeg", ".png"):
            result["thumbnail"] = f
        elif f.name.endswith(".info.json"):
            result["info_json"] = f

    logger.info(
        "ytdlp.scan.done video=%s audio=%s subs=%d",
        result["video"] is not None,
        result["audio"] is not None,
        len(result["subtitles"]),
    )
    return result
