"""Модель записи истории загрузки.

Классы:
    HistoryEntry: Полная запись о загрузке с путями к файлам.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .app_settings import DownloadType, QualityOption
from .download_task import DownloadStatus


@dataclass
class HistoryEntry:
    """Запись в истории загрузок.

    Хранится в JSON. Содержит все пути к финальным файлам.

    Attributes:
        id: Уникальный числовой ID (auto-increment, возрастающий).
        url: Исходный URL.
        title: Название видео.
        playlist_title: Название плейлиста (пустая строка если одиночное видео).
        quality: Качество загрузки.
        download_type: Тип (видео или аудио).
        status: Финальный статус.
        video_path: Путь к видеофайлу (mp4/mkv) или None.
        audio_path: Путь к аудиофайлу (m4a/opus) если audio-only или None.
        subtitle_paths: Список путей к файлам субтитров (vtt/srt).
        description_path: Путь к файлу описания (.txt) или None.
        thumbnail_path: Путь к обложке (.webp/.jpg) или None.
        info_json_path: Путь к info.json или None.
        error_message: Сообщение об ошибке (если failed).
        created_at: Когда добавлено в очередь.
        finished_at: Когда завершено (None если не завершено).
    """

    id: int
    url: str
    title: str = ""
    playlist_title: str = ""
    quality: QualityOption = QualityOption.BEST
    download_type: DownloadType = DownloadType.VIDEO
    status: DownloadStatus = DownloadStatus.QUEUED
    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    subtitle_paths: list[Path] = field(default_factory=list)
    description_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    info_json_path: Optional[Path] = None
    output_dir: Optional[Path] = None
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Сериализует запись в словарь для JSON."""

        def _path(p: Optional[Path]) -> Optional[str]:
            return str(p) if p else None

        def _ev(v: object) -> str:
            """Возвращает .value если Enum, иначе str."""
            return v.value if hasattr(v, "value") else str(v)  # type: ignore[union-attr]

        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "playlist_title": self.playlist_title,
            "quality": _ev(self.quality),
            "download_type": _ev(self.download_type),
            "status": _ev(self.status),
            "video_path": _path(self.video_path),
            "audio_path": _path(self.audio_path),
            "subtitle_paths": [str(p) for p in self.subtitle_paths],
            "description_path": _path(self.description_path),
            "thumbnail_path": _path(self.thumbnail_path),
            "info_json_path": _path(self.info_json_path),
            "output_dir": _path(self.output_dir),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> HistoryEntry:
        """Десериализует запись из словаря.

        Args:
            data: Словарь из JSON.

        Returns:
            Экземпляр HistoryEntry.
        """

        def _path(v: Optional[str]) -> Optional[Path]:
            return Path(v) if v else None

        return cls(
            id=data["id"],
            url=data["url"],
            title=data.get("title", ""),
            playlist_title=data.get("playlist_title", ""),
            quality=QualityOption(data.get("quality", "best")),
            download_type=DownloadType(data.get("download_type", "video")),
            status=DownloadStatus(data.get("status", "done")),
            video_path=_path(data.get("video_path")),
            audio_path=_path(data.get("audio_path")),
            subtitle_paths=[Path(p) for p in data.get("subtitle_paths", [])],
            description_path=_path(data.get("description_path")),
            thumbnail_path=_path(data.get("thumbnail_path")),
            info_json_path=_path(data.get("info_json_path")),
            output_dir=_path(data.get("output_dir")),
            error_message=data.get("error_message", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            finished_at=(
                datetime.fromisoformat(data["finished_at"]) if data.get("finished_at") else None
            ),
        )
