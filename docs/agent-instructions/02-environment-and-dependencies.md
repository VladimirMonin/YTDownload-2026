# 02 — Environment and dependencies

## Python environment

The project requires Python 3.12 or newer. Reuse the existing `.venv`; do not create,
install, update or synchronize environments as a diagnostic shortcut:

```bash
uv run --locked --no-sync python --version
```

For tests/imports/smokes, establish owned storage/home/temp/cache/log roots **before**
the process per [testing](../../.github/instructions/testing.instructions.md), and
set offline/no-download flags. Keep required OS paths; do not dump credentials or
user settings. A missing interpreter/dependency is a blocker, not install permission.
Initial user installation is a separate action: README setup recipes are not an
agent authorization to run `uv sync`, installers or package managers.

## FFmpeg policy

FFmpeg is required for merging video and audio and for audio-only extraction.

Detection order:

1. Explicit environment variable:
   - `YTDL_FFMPEG_PATH`
   - `YTDL_FFPROBE_PATH`
   - `YTDL_FFPLAY_PATH`
2. Bundled binaries in `vendor/ffmpeg/bin/`:
   - Windows: `ffmpeg.exe`, `ffprobe.exe`, `ffplay.exe`
   - Unix-like: `ffmpeg`, `ffprobe`, `ffplay`
3. System `PATH`.

Linux development should normally use the distro package, for example `/usr/bin/ffmpeg`.

## Do not

- Do not download large vendor binaries without user approval.
- Do not install global/system packages without user approval.
- Do not assume Windows `.exe` paths work on Linux.
