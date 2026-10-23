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
The real yt-dlp backend writes new results beneath
`output_dir/download-<admitted task_id>/` with the existing title/playlist templates.
The leased repository allocates monotonically distinct IDs; no second registry
or cross-profile sharing is implied. AppSettings.output_dir and HistoryEntry.output_root
retain the selected parent. Read actual returned/stored paths; never reconstruct ownership
from titles or newest folders. Old records/files are not moved or deleted.

Writable construction acquires the stdlib OS lease **before** mutable cache load,
recovers orphan queued/downloading/merging records to failed/INTERRUPTED without
replay/media cleanup, and refuses a second writer with OWNER_BUSY. The lock file
remains on unlock. Read-only construction creates no root/lease/executor/recovery
and reads detached last-saved snapshots, not another process's live queue.

Use `with create_runtime(...):` for drain on exit, or explicit close: `cancel=False`
drains; `cancel=True` removes queued work/signals active work cooperatively.
`wait=False` is not completed cleanup and retains the lease until a real join;
stale repositories cannot write after close. Borrowed wrappers never close the
caller. Check ShutdownResultDTO even when closed=True: persistence_error_ids and
error_codes may still report a physically completed but unsaved result. Blocking
foreign calls have no hard stop deadline/rollback guarantee.

S3 fixes the whole settings snapshot at admission. Updating settings cannot mutate
A/B; a new pool cap applies only after the old futures/callbacks drain and its pool
joins. Task/wait snapshots are detached; list/search selection, limit and mapping
use the same captured entry/task pair. Unknown metrics are None, measured0 is0;
legacy numeric bridge compatibility is not a measurement claim.
Direct legacy JSON repository construction does **not** automatically acquire a
runtime lease; its caller must own that policy. Atomic JSON is not a media+JSON
transaction or a power-loss guarantee.

For tests/smokes assign an owned YTDL_DATA_DIR before collection/import; the smoke
helper additionally overrides it into its own subtree and restores it in finally.
Existing CLI/MCP/GUI entrypoints are not an external Attached client; complete
read-only/standalone adapter lifetime migration and CLI `--data-dir` remain S5.

## S4 file-effect boundary

`create_runtime` supplies a default lazy `QtFileRemover` in infrastructure. Core
construction imports no Qt/transport/backend SDK and needs no QApplication;
actual Trash capability is checked at the effect edge. No new package or
permanent-delete fallback is used. Read-only preview has no remover/executor.

Use the Application API's explicit preview token with the same ID/delete_files
mode. Only recorded artifact/legacy paths within checked roots are candidates;
output_dir/download-<id> is not authority to remove a directory. Old folder-only
records permit checked keep-files, not a directory scan. Active/unquiesced jobs,
links/reparse ancestry and shared attribution block file effects. Partial moves
and failed history save are not rollback or confirmed deletion; read the structured
result and repreview. Synthetic recoverable moves and installed capability were
verified; native Trash move/restore remains NOT_RUN. Complete adapter confirmation
and lifetime wiring remain S5. See [current evidence](../command-first/VERIFICATION.md).

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
