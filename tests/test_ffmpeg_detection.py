"""Unit tests for cross-platform FFmpeg executable discovery."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.infrastructure import ffmpeg as ffmpeg_module
from src.infrastructure.ffmpeg import find_executable

TOOL_CASES = [
    ("find_ffmpeg", "YTDL_FFMPEG_PATH", "ffmpeg"),
    ("find_ffprobe", "YTDL_FFPROBE_PATH", "ffprobe"),
    ("find_ffplay", "YTDL_FFPLAY_PATH", "ffplay"),
]

WRAPPER_CASES = [
    ("find_ffmpeg", "ffmpeg"),
    ("find_ffprobe", "ffprobe"),
    ("find_ffplay", "ffplay"),
]


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub", encoding="utf-8")
    return path


@pytest.mark.parametrize(("finder_name", "env_var", "tool_name"), TOOL_CASES)
def test_explicit_env_path_wins(
    monkeypatch,
    tmp_path: Path,
    finder_name: str,
    env_var: str,
    tool_name: str,
) -> None:
    explicit = _touch(tmp_path / "custom" / f"{tool_name}-custom")
    vendor = tmp_path / "vendor" / "bin"
    _touch(vendor / f"{tool_name}.exe")
    _touch(vendor / tool_name)

    monkeypatch.setattr(ffmpeg_module, "VENDOR_BIN", vendor)
    monkeypatch.setenv(env_var, str(explicit))

    finder = getattr(ffmpeg_module, finder_name)
    assert finder() == explicit


@pytest.mark.parametrize("tool_name", ["ffmpeg", "ffprobe", "ffplay"])
def test_windows_vendor_exe_is_preferred_before_unix_vendor_binary(
    monkeypatch,
    tmp_path: Path,
    tool_name: str,
) -> None:
    vendor = tmp_path / "vendor" / "bin"
    windows_binary = _touch(vendor / f"{tool_name}.exe")
    _touch(vendor / tool_name)

    monkeypatch.setattr(ffmpeg_module.os, "name", "nt", raising=False)
    assert find_executable(tool_name, vendor_bin=vendor) == windows_binary


@pytest.mark.parametrize("tool_name", ["ffmpeg", "ffprobe", "ffplay"])
def test_unix_vendor_binary_is_used_when_no_exe_exists(
    monkeypatch,
    tmp_path: Path,
    tool_name: str,
) -> None:
    vendor = tmp_path / "vendor" / "bin"
    unix_binary = _touch(vendor / tool_name)

    monkeypatch.setattr(ffmpeg_module.os, "name", "posix", raising=False)
    assert find_executable(tool_name, vendor_bin=vendor) == unix_binary


@pytest.mark.parametrize(("finder_name", "tool_name"), WRAPPER_CASES)
def test_linux_ignores_vendor_exe_and_falls_back_to_path(
    monkeypatch,
    tmp_path: Path,
    finder_name: str,
    tool_name: str,
) -> None:
    vendor = tmp_path / "vendor" / "bin"
    _touch(vendor / f"{tool_name}.exe")

    path_bin = tmp_path / "path-bin"
    system_binary = _touch(path_bin / tool_name)
    system_binary.chmod(0o755)

    monkeypatch.setattr(ffmpeg_module, "VENDOR_BIN", vendor)
    monkeypatch.setattr(ffmpeg_module.os, "name", "posix", raising=False)
    monkeypatch.setenv("PATH", str(path_bin))

    finder = getattr(ffmpeg_module, finder_name)
    assert finder() == system_binary


@pytest.mark.parametrize(("finder_name", "tool_name"), WRAPPER_CASES)
def test_windows_vendor_exe_beats_system_path(
    monkeypatch,
    tmp_path: Path,
    finder_name: str,
    tool_name: str,
) -> None:
    vendor = tmp_path / "vendor" / "bin"
    vendor_binary = _touch(vendor / f"{tool_name}.exe")

    path_bin = tmp_path / "path-bin"
    path_binary = _touch(path_bin / f"{tool_name}.exe")
    path_binary.chmod(0o755)

    monkeypatch.setattr(ffmpeg_module, "VENDOR_BIN", vendor)
    monkeypatch.setattr(ffmpeg_module.os, "name", "nt", raising=False)
    monkeypatch.setenv("PATH", str(path_bin))

    finder = getattr(ffmpeg_module, finder_name)
    assert finder() == vendor_binary


@pytest.mark.parametrize("tool_name", ["ffmpeg", "ffprobe", "ffplay"])
def test_system_path_is_fallback(monkeypatch, tmp_path: Path, tool_name: str) -> None:
    vendor = tmp_path / "empty-vendor"
    bin_dir = tmp_path / "path-bin"
    executable_name = f"{tool_name}.exe" if os.name == "nt" else tool_name
    executable = _touch(bin_dir / executable_name)
    executable.chmod(0o755)

    monkeypatch.setenv("PATH", str(bin_dir))

    assert find_executable(tool_name, vendor_bin=vendor) == executable
