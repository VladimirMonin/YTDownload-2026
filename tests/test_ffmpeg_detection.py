"""Unit tests for cross-platform FFmpeg executable discovery."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

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
    # Simulate selection, not the host's Windows executable/PATHEXT resolver.
    resolver = Mock(return_value=str(system_binary))
    monkeypatch.setattr(ffmpeg_module.shutil, "which", resolver)
    monkeypatch.setattr(ffmpeg_module, "VENDOR_BIN", vendor)
    # Do not mutate global os.name: pathlib must keep using the actual host flavour.
    monkeypatch.setattr(ffmpeg_module, "os", SimpleNamespace(name="posix", getenv=os.getenv))
    monkeypatch.setenv("PATH", str(path_bin))

    finder = getattr(ffmpeg_module, finder_name)
    assert finder() == system_binary
    resolver.assert_called_once_with(tool_name)


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


@pytest.mark.parametrize("frozen", [False, True])
def test_application_root_source_or_frozen_executable_not_internal(monkeypatch, tmp_path, frozen):
    executable = _touch(tmp_path / "relocated bundle" / "ytdl.exe")
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "wrong internal"), raising=False)
    spec = importlib.util.spec_from_file_location("owned_ffmpeg_root", ffmpeg_module.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = executable.parent if frozen else Path(ffmpeg_module.__file__).parent.parent.parent
    assert module.PROJECT_ROOT == expected
    assert module.VENDOR_BIN == expected / "vendor" / "ffmpeg" / "bin"


@pytest.mark.parametrize("tool_name", ["ffmpeg", "ffprobe", "ffplay"])
def test_frozen_real_resolver_env_explicit_vendor_default_and_path(
    monkeypatch, tmp_path, tool_name
):
    executable = _touch(tmp_path / "relocated bundle" / "ytdl.exe")
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "wrong internal"), raising=False)
    spec = importlib.util.spec_from_file_location("owned_ffmpeg_priority", ffmpeg_module.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suffix = ".exe" if os.name == "nt" else ""
    bundled = _touch(executable.parent / "vendor/ffmpeg/bin" / (tool_name + suffix))
    explicit = _touch(tmp_path / "explicit" / (tool_name + suffix))
    override = _touch(tmp_path / "custom vendor" / (tool_name + suffix))
    path_file = _touch(tmp_path / "path" / (tool_name + suffix))
    env_var = "YTDL_" + tool_name.upper() + "_PATH"
    monkeypatch.setenv(env_var, str(explicit))
    monkeypatch.setattr(module.shutil, "which", lambda _: str(path_file))
    assert module.find_executable(tool_name, env_var) == explicit
    monkeypatch.delenv(env_var)
    assert module.find_executable(tool_name, env_var, override.parent) == override
    assert module.find_executable(tool_name, env_var) == bundled
    # An explicit empty vendor still falls back to PATH, not another root scan.
    assert module.find_executable(tool_name, env_var, tmp_path / "empty") == path_file
