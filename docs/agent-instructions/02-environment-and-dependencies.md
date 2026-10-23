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

## Application data and ownership

`src.bootstrap.create_runtime(data_root=None, *, read_only=False, ...)` selects an
explicit root → nonempty `YTDL_DATA_DIR` → nonempty APPDATA/YTDownloader →
home/YTDownloader, then canonicalizes it. The root contains `config/settings.json`,
`data/history.json` and `logs/`; output still defaults to home/Downloads/YTDownloader.
`settings_overrides` are effective snapshots, not silently persisted settings.

Writable construction acquires the stdlib OS lease **before** mutable cache load,
recovers orphan queued/downloading/merging records to failed/INTERRUPTED without
replay/media cleanup, and refuses a second writer with OWNER_BUSY. The lock file
remains on unlock. Read-only construction creates no root/lease/executor/recovery
and reads detached last-saved snapshots, not another process's live queue.

Use `with create_runtime(...):` (drain on exit) or explicit
`close(cancel=False, wait=True)` for the S2-proved join path. `wait=False` retains
the lease until a real join; stale repository references cannot write after close.
Borrowed wrappers never close caller-owned coordinator/resources. Full cooperative
cancel/terminal consistency and new pool-cap-after-drain semantics remain S3.
Direct legacy JSON repository construction does **not** automatically acquire a
runtime lease; its caller must own that policy. Atomic JSON is not a media+JSON
transaction or a power-loss guarantee.

For tests/smokes assign an owned YTDL_DATA_DIR before collection/import; the smoke
helper additionally overrides it into its own subtree and restores it in finally.
Existing CLI/MCP/GUI entrypoints are not an external Attached client; complete
read-only/standalone adapter lifetime migration and CLI `--data-dir` remain S5.

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
