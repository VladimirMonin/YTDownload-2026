"""Модель информации о видео.

Классы:
    VideoInfo: Метаданные видео, полученные от yt-dlp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VideoInfo:
    """Метаданные видео от yt-dlp (без скачивания).

    Attributes:
        id: YouTube ID видео.
        title: Название.
        uploader: Автор/канал.
        duration: Длительность в секундах.
        description: Описание видео.
        thumbnail_url: URL обложки.
        available_subtitles: Доступные языки субтитров.
        available_auto_subs: Доступные автосубтитры.
        is_playlist: Является ли URL плейлистом.
        playlist_title: Название плейлиста.
        playlist_count: Количество видео в плейлисте.
    """

    id: str = ""
    title: str = ""
    uploader: str = ""
    duration: int = 0
    description: str = ""
    thumbnail_url: str = ""
    available_subtitles: list[str] = field(default_factory=list)
    available_auto_subs: list[str] = field(default_factory=list)
    is_playlist: bool = False
    playlist_title: str = ""
    playlist_count: int = 0

    @property
    def duration_str(self) -> str:
        """Длительность в формате HH:MM:SS или MM:SS."""
        h = self.duration // 3600
        m = (self.duration % 3600) // 60
        s = self.duration % 60
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
