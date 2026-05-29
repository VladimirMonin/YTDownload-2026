"""Unit tests for cross-platform FFmpeg executable discovery."""

from __future__ import annotations

import os
from pathlib import Path

from src.infrastructure.ffmpeg import find_executable


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub", encoding="utf-8")
    return path


def test_explicit_env_path_wins(monkeypatch, tmp_path: Path) -> None:
    explicit = _touch(tmp_path / "custom" / "ffmpeg-custom")
    vendor = tmp_path / "vendor" / "bin"
    _touch(vendor / "ffmpeg.exe")

    monkeypatch.setenv("YTDL_FFMPEG_PATH", str(explicit))

    assert find_executable("ffmpeg", "YTDL_FFMPEG_PATH", vendor_bin=vendor) == explicit


def test_windows_vendor_exe_is_preferred_before_unix_vendor_binary(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor" / "bin"
    windows_binary = _touch(vendor / "ffmpeg.exe")
    _touch(vendor / "ffmpeg")

    assert find_executable("ffmpeg", vendor_bin=vendor) == windows_binary


def test_unix_vendor_binary_is_used_when_no_exe_exists(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor" / "bin"
    unix_binary = _touch(vendor / "ffmpeg")

    assert find_executable("ffmpeg", vendor_bin=vendor) == unix_binary


def test_system_path_is_fallback(monkeypatch, tmp_path: Path) -> None:
    vendor = tmp_path / "empty-vendor"
    bin_dir = tmp_path / "path-bin"
    executable_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    executable = _touch(bin_dir / executable_name)
    executable.chmod(0o755)

    monkeypatch.setenv("PATH", str(bin_dir))

    assert find_executable("ffmpeg", vendor_bin=vendor) == executable
