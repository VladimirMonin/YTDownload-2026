"""Тесты проверки FFmpeg в vendor/ директории.

Убеждаемся что:
- ffmpeg.exe существует и запускается
- ffprobe.exe существует и возвращает корректный JSON
- Бинарники совместимы с текущей ОС
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src.infrastructure.ffmpeg import find_ffplay


class TestFFmpegVendor:
    """Тесты наличия и работоспособности FFmpeg."""

    def test_ffmpeg_exists(self, ffmpeg_path: Path) -> None:
        """ffmpeg.exe должен существовать в vendor/."""
        assert ffmpeg_path.exists(), f"FFmpeg not found: {ffmpeg_path}"
        assert ffmpeg_path.is_file()

    def test_ffprobe_exists(self, ffprobe_path: Path) -> None:
        """ffprobe.exe должен существовать в vendor/."""
        assert ffprobe_path.exists(), f"FFprobe not found: {ffprobe_path}"
        assert ffprobe_path.is_file()

    def test_ffplay_exists(self) -> None:
        """ffplay должен существовать в env, vendor/ или системном PATH."""
        ffplay = find_ffplay()
        assert ffplay is not None, "FFplay not found in env, vendor/ffmpeg/bin or PATH"
        assert ffplay.exists(), f"FFplay not found: {ffplay}"

    def test_ffmpeg_version(self, ffmpeg_path: Path) -> None:
        """ffmpeg -version должен выполняться и возвращать версию."""
        result = subprocess.run(
            [str(ffmpeg_path), "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"ffmpeg -version failed: {result.stderr}"
        assert "ffmpeg version" in result.stdout.lower()

    def test_ffprobe_version(self, ffprobe_path: Path) -> None:
        """ffprobe -version должен выполняться и возвращать версию."""
        result = subprocess.run(
            [str(ffprobe_path), "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"ffprobe -version failed: {result.stderr}"
        assert "ffprobe version" in result.stdout.lower()

    def test_ffprobe_json_output(
        self, ffmpeg_path: Path, ffprobe_path: Path, tmp_path: Path
    ) -> None:
        """ffprobe должен корректно анализировать медиафайл и возвращать JSON."""
        test_video = tmp_path / "test.mp4"

        # Генерируем 1-секундное тестовое видео (без кодирования сети)
        result = subprocess.run(
            [
                str(ffmpeg_path),
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=320x240:d=1",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=mono",
                "-t",
                "1",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-y",
                str(test_video),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            pytest.skip(f"Cannot generate test video: {result.stderr[:200]}")

        # Проверяем через ffprobe
        probe = subprocess.run(
            [
                str(ffprobe_path),
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                str(test_video),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert probe.returncode == 0
        data = json.loads(probe.stdout)
        streams = data.get("streams", [])
        assert len(streams) > 0

        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        assert len(video_streams) == 1
        assert video_streams[0]["width"] == 320
        assert video_streams[0]["height"] == 240


class TestFFmpegFfcheckerUtility:
    """Тесты утилиты проверки FFmpeg (если есть)."""

    def test_ffmpeg_location_env(self, ffmpeg_path: Path) -> None:
        """YTDL_FFMPEG_PATH должен переопределять путь к ffmpeg."""
        import os

        old = os.environ.get("YTDL_FFMPEG_PATH")
        os.environ["YTDL_FFMPEG_PATH"] = str(ffmpeg_path)

        from main import initialize_app

        try:
            services = initialize_app()
            assert services["coordinator"]._ffmpeg_path == ffmpeg_path
        finally:
            if old is None:
                del os.environ["YTDL_FFMPEG_PATH"]
            else:
                os.environ["YTDL_FFMPEG_PATH"] = old
