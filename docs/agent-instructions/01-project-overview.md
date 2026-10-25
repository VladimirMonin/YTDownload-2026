# 01 — Project overview

YTDownload 2026 is a YouTube downloader with an existing PySide6 GUI, CLI and local MCP server.

Engineering entry: [docs/engineering.md](../engineering.md); normative rationale:
[project philosophy](../foundation/project-philosophy.md). A command-first refactor is
requested, not assumed complete from the existence of an API module.

## Stack

- Python 3.12+
- PySide6 GUI
- yt-dlp download backend
- FFmpeg for video/audio merge and audio extraction
- FastMCP HTTP server
- uv for dependency management

## Architecture

- `ytdl_cli.py` — thin absolute-import entry for the standalone Windows console; calls the same canonical CLI, no second parser or Python-child shim.
- `build/ytdl_cli.spec` / `build/build.py --target cli` — console onedir in new external work/dist roots; full bundle required, not one EXE.
- `app.py` — existing GUI entry point; default GUI build/spec/installer remain separate.
- `main.py` — compatibility wrapper `initialize_app`, preserving service keys and exposing `runtime`.
- `src/bootstrap.py` — explicit `create_runtime`, paths, lazy factories and writer lease acquisition.
- `src/domain/` — data models and protocols.
- `src/application/` — ApplicationAPI, command/query semantics, DTOs, queue coordinator and owned/borrowed runtime lifetime.
- `src/interfaces/cli/` — parser, formatting, readonly/writable selection and process lifetime; bootstrap reexports the infrastructure MCP factory.
- `src/infrastructure/` — yt-dlp, repositories, FFmpeg detection, canonical MCP factory and owned HTTP socket/server/thread handle.
- `src/ui/` — PySide6 widgets, managers, theme, icons.
- `tests/` — offline unit tests plus opt-in E2E tests.

## Working style

- Make narrow, reviewable changes.
- Preserve Windows packaging behavior unless the task is explicitly Linux-only.
- Name verification level honestly: unit, offline integration, GUI smoke, MCP smoke, real YouTube E2E.
- Update README or these instructions when setup behavior changes.
- Keep `AGENTS.md` as the required entry point and put detailed agent rules under `docs/agent-instructions/`.
- Canonical testing/logging procedures remain in `.github/instructions/` and are linked
  from AGENTS; do not duplicate those policies under a second editable owner.
- S1–S6 are independently accepted within the agreed offline boundary: real CLI/stdio/HTTP/Qt paths, token wiring, owned/borrowed lifetime, S5-R1 handler preservation and final CI isolation/module-command qualification. GUI managers use the same API, detached settings and the existing modal; no repository fallback or visual redesign. Readonly queries/own-add wait/standalone OWNER_REQUIRED are distinct; --data-dir is not attach. S6 executed the actual workflow preparation and commands locally on Windows/Python3.14.2, not hosted CI/Linux/Python3.12/pwsh7. Those S6 proofs alone did not qualify native Trash restore, live/codec, EXE/manual visual or blanket legacy privacy; Q2's narrower console/local-codec result below does not certify GUI/live/general privacy. Normative PLAN/CONTRACT remain requirements; current disposition is in [verification](../command-first/VERIFICATION.md).
- Q2 is independently ACCEPTED_Q2_LOCAL_OFFLINE: Windows x64 console759-file distribution, relocation without checkout/development PATH assistance, all11 CLI leaves in fresh native71-row aggregate plus8 complements. Real own loopback video/audio, durable native reopen and SDK stdio/HTTP/EOF/next owner were exercised; source gates308/7 e2e deselected/0 skipped, mypy0/68, configured1090, changed6 E/F/I0, four module smokes0. See [console start](../../README.md) and [build instructions](../../.github/instructions/build_system.instructions.md).
- The local fixture proves MPEG-4+AAC MP4 and AAC/M4A audio-only, not YouTube/720p/remote sidecars. Native Trash was PARTIAL_DELETE/TRASH_UNAVAILABLE UNKNOWN (source absent/history retained), not recoverable-success; destination/restore remain unqualified. HTTP Ctrl+C is native1/INTERRUPTED. External YouTube is WAITING_FOR_USER_URL / NOT_RUN; no URL may be chosen on the user's behalf.
- GUI build/layout/design/visual/manual acceptance, other platforms/hosted CI, optional remote extras, whole legacy privacy and legal redistribution certification are outside Q2. Unchanged automated GUI compatibility is not a GUI executable build.
