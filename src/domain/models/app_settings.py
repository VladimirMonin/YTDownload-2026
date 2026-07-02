"""Модель настроек приложения.

Классы:
    QualityOption: Перечисление вариантов качества.
    DownloadType: Тип загрузки (видео или аудио).
    AppSettings: Полные настройки приложения.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class QualityOption(str, Enum):
    """Варианты качества загружаемого видео."""

    BEST = "best"
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"
    P360 = "360p"
    AUDIO = "audio"

    def display_name(self) -> str:
        """Возвращает отображаемое имя для UI."""
        names = {
            self.BEST: "Лучшее",
            self.P1080: "1080p",
            self.P720: "720p",
            self.P480: "480p",
            self.P360: "360p",
            self.AUDIO: "Только аудио",
        }
        return names[self]


class DownloadType(str, Enum):
    """Тип загружаемого контента."""

    VIDEO = "video"  # видео + аудио (мерж через FFmpeg)
    AUDIO = "audio"  # только аудио


@dataclass
class AppSettings:
    """Полные настройки приложения.

    Attributes:
        output_dir: Папка для сохранения загрузок.
        proxy: Прокси (socks5://... или http://...), пустая строка = нет.
        quality: Желаемое качество видео.
        download_type: Тип контента (видео или аудио).
        subtitle_lang: Язык субтитров (ru, en, kk, ...).
        save_subtitles: Сохранять субтитры.
        save_description: Сохранять описание.
        save_thumbnail: Сохранять обложку.
        max_concurrent: Максимальное число параллельных загрузок.
        theme: Тема оформления (dark / light).
    """

    output_dir: Path = field(default_factory=lambda: Path.home() / "Downloads" / "YTDownloader")
    proxy: str = ""
    quality: QualityOption = QualityOption.BEST
    download_type: DownloadType = DownloadType.VIDEO
    subtitle_lang: str = "ru"
    save_subtitles: bool = True
    save_description: bool = True
    save_thumbnail: bool = True
    max_concurrent: int = 2
    mcp_port: int = 8765
    theme: str = "dark"

    def to_dict(self) -> dict:
        """Сериализует настройки в словарь для JSON."""
        return {
            "output_dir": str(self.output_dir),
            "proxy": self.proxy,
            "quality": self.quality.value,
            "download_type": self.download_type.value,
            "subtitle_lang": self.subtitle_lang,
            "save_subtitles": self.save_subtitles,
            "save_description": self.save_description,
            "save_thumbnail": self.save_thumbnail,
            "max_concurrent": self.max_concurrent,
            "mcp_port": self.mcp_port,
            "theme": self.theme,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AppSettings:
        """Десериализует настройки из словаря.

        Args:
            data: Словарь с данными.

        Returns:
            Экземпляр AppSettings.
        """
        return cls(
            output_dir=Path(
                data.get("output_dir", str(Path.home() / "Downloads" / "YTDownloader"))
            ),
            proxy=data.get("proxy", ""),
            quality=QualityOption(data.get("quality", "best")),
            download_type=DownloadType(data.get("download_type", "video")),
            subtitle_lang=data.get("subtitle_lang", "ru"),
            save_subtitles=data.get("save_subtitles", True),
            save_description=data.get("save_description", True),
            save_thumbnail=data.get("save_thumbnail", True),
            max_concurrent=data.get("max_concurrent", 2),
            mcp_port=data.get("mcp_port", 8765),
            theme=data.get("theme", "dark"),
        )
