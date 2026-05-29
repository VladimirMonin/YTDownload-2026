"""pytest конфигурация и общие fixtures.

Предоставляет:
    - Пути к FFmpeg/FFprobe в vendor/
    - Временные директории для тестов
    - Базовые AppSettings для тестов
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.infrastructure.ffmpeg import find_ffmpeg, find_ffprobe

# Корень проекта
PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def ffmpeg_path() -> Path:
    """Абсолютный путь к ffmpeg из env, vendor/ или системного PATH."""
    path = find_ffmpeg()
    assert path is not None, "FFmpeg not found in env, vendor/ffmpeg/bin or PATH"
    return path


@pytest.fixture(scope="session")
def ffprobe_path() -> Path:
    """Абсолютный путь к ffprobe из env, vendor/ или системного PATH."""
    path = find_ffprobe()
    assert path is not None, "FFprobe not found in env, vendor/ffmpeg/bin or PATH"
    return path


@pytest.fixture(scope="session")
def base_settings(tmp_path_factory):
    """Базовые AppSettings для тестов с tmp_path в качестве output_dir."""
    from src.domain.models.app_settings import AppSettings, DownloadType, QualityOption

    output_dir = tmp_path_factory.mktemp("downloads")
    return AppSettings(
        output_dir=output_dir,
        quality=QualityOption.P720,
        download_type=DownloadType.VIDEO,
        save_subtitles=False,
        save_description=False,
        save_thumbnail=False,
    )


def probe_video(ffprobe_path: Path, video_path: Path) -> dict:
    """Запускает ffprobe и возвращает первый video stream info.

    Args:
        ffprobe_path: Путь к ffprobe.exe.
        video_path: Путь к видеофайлу.

    Returns:
        Словарь со stream информацией (codec_name, width, height, ...).
    """
    import json

    result = subprocess.run(
        [
            str(ffprobe_path),
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    return video_streams[0] if video_streams else {}
