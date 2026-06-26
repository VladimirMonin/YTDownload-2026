"""FFmpeg executable discovery helpers.

Supports both bundled Windows binaries in vendor/ffmpeg/bin and system
executables on Linux/macOS.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
VENDOR_BIN = PROJECT_ROOT / "vendor" / "ffmpeg" / "bin"


def find_executable(
    name: str,
    env_var: str | None = None,
    vendor_bin: Path | None = None,
) -> Path | None:
    """Return an executable path from env, vendor directory, or system PATH.

    Args:
        name: Executable base name, for example ``ffmpeg`` or ``ffprobe``.
        env_var: Optional environment variable with an explicit executable path.
        vendor_bin: Optional vendor bin directory. Defaults to the project vendor path.
    """
    if env_var:
        env_value = os.getenv(env_var, "").strip()
        if env_value:
            path = Path(env_value).expanduser()
            if path.exists():
                return path

    bin_dir = vendor_bin or VENDOR_BIN
    if os.name == "nt":
        candidates = [
            bin_dir / f"{name}.exe",
        ]
    else:
        candidates = [
            bin_dir / name,
        ]
    for path in candidates:
        if path.exists():
            return path

    system_path = shutil.which(name)
    return Path(system_path) if system_path else None


def find_ffmpeg() -> Path | None:
    """Find ffmpeg, honoring YTDL_FFMPEG_PATH."""
    return find_executable("ffmpeg", "YTDL_FFMPEG_PATH")


def find_ffprobe() -> Path | None:
    """Find ffprobe, honoring YTDL_FFPROBE_PATH."""
    return find_executable("ffprobe", "YTDL_FFPROBE_PATH")


def find_ffplay() -> Path | None:
    """Find ffplay, honoring YTDL_FFPLAY_PATH."""
    return find_executable("ffplay", "YTDL_FFPLAY_PATH")
