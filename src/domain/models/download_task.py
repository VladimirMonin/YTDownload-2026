"""Модель задания на загрузку.

Классы:
    DownloadStatus: Статусы загрузки.
    DownloadTask: Задание на загрузку с уникальным ID.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .app_settings import DownloadType, QualityOption


class DownloadStatus(str, Enum):
    """Статусы загрузки."""

    QUEUED = "queued"  # В очереди, ожидает
    DOWNLOADING = "downloading"  # Загружается прямо сейчас
    MERGING = "merging"  # FFmpeg собирает дорожки
    DONE = "done"  # Успешно завершено
    FAILED = "failed"  # Ошибка
    CANCELLED = "cancelled"  # Отменено пользователем

    def display_name(self) -> str:
        """Возвращает отображаемое имя."""
        names = {
            self.QUEUED: "В очереди",
            self.DOWNLOADING: "Загрузка...",
            self.MERGING: "Сборка...",
            self.DONE: "Готово",
            self.FAILED: "Ошибка",
            self.CANCELLED: "Отменено",
        }
        return names[self]

    def is_terminal(self) -> bool:
        """Завершён ли процесс (финальный статус)."""
        return self in (self.DONE, self.FAILED, self.CANCELLED)

    def is_active(self) -> bool:
        """Выполняется ли загрузка прямо сейчас."""
        return self in (self.DOWNLOADING, self.MERGING)


@dataclass
class DownloadTask:
    """Задание на загрузку с уникальным числовым ID.

    Attributes:
        id: Уникальный числовой ID (auto-increment из репозитория).
        url: URL YouTube видео или плейлиста.
        title: Название (заполняется после fetch_info).
        playlist_title: Название плейлиста (если применимо).
        quality: Желаемое качество.
        download_type: Тип (видео+аудио или только аудио).
        subtitle_lang: Язык субтитров.
        save_subtitles: Сохранять субтитры.
        save_description: Сохранять описание.
        save_thumbnail: Сохранять обложку.
        status: Текущий статус загрузки.
        progress: Прогресс 0..100.
        speed: Скорость в байтах/сек (0 если неизвестна).
        eta_seconds: Оставшееся время в секундах.
        error_message: Сообщение об ошибке.
        created_at: Дата добавления в очередь.
    """

    id: int
    url: str
    title: str = ""
    playlist_title: str = ""
    quality: QualityOption = QualityOption.BEST
    download_type: DownloadType = DownloadType.VIDEO
    subtitle_lang: str = "ru"
    save_subtitles: bool = True
    save_description: bool = True
    save_thumbnail: bool = True
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0
    speed: float = 0.0
    eta_seconds: int = 0
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
