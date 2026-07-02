"""Протокол сервиса загрузки."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional

from ..models import AppSettings, DownloadTask, VideoInfo


class IDownloadService(ABC):
    """Интерфейс сервиса загрузки через yt-dlp."""

    @abstractmethod
    def fetch_info(self, url: str, settings: AppSettings) -> VideoInfo:
        """Получает метаданные без скачивания.

        Args:
            url: URL видео или плейлиста.
            settings: Настройки (прокси и др.).

        Returns:
            Метаданные видео.

        Raises:
            ValueError: Если URL невалиден или недоступен.
        """

    @abstractmethod
    def download(
        self,
        task: DownloadTask,
        settings: AppSettings,
        progress_callback: Optional[Callable[[float, float, int], None]] = None,
    ) -> dict[str, Optional[Path]]:
        """Скачивает видео согласно заданию.

        Args:
            task: Задание на загрузку.
            settings: Настройки приложения (proxy, output_dir и др.).
            progress_callback: Вызывается с (percent, speed_bps, eta_sec).

        Returns:
            Словарь путей: {
                "video": Path | None,
                "audio": Path | None,
                "subtitles": list[Path],
                "description": Path | None,
                "thumbnail": Path | None,
                "info_json": Path | None,
            }

        Raises:
            RuntimeError: При ошибке загрузки.
        """

    @abstractmethod
    def cancel(self) -> None:
        """Отменяет текущую загрузку."""
