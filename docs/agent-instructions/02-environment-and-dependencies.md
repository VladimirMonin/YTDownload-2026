# 02 — Environment and dependencies

## Python environment

Use uv:

```bash
uv sync
uv run python --version
```

The project requires Python 3.12 or newer.

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
