"""Пакет доменных моделей."""

from .app_settings import AppSettings, DownloadType, QualityOption
from .download_task import DownloadStatus, DownloadTask
from .history_entry import HistoryEntry
from .video_info import VideoInfo

__all__ = [
    "AppSettings",
    "DownloadType",
    "DownloadStatus",
    "DownloadTask",
    "HistoryEntry",
    "QualityOption",
    "VideoInfo",
]
