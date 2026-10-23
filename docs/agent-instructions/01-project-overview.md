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

- `app.py` — GUI entry point.
- `main.py` — compatibility wrapper `initialize_app`, preserving service keys and exposing `runtime`.
- `src/bootstrap.py` — explicit `create_runtime`, paths, lazy factories and writer lease acquisition.
- `src/domain/` — data models and protocols.
- `src/application/` — ApplicationAPI, command/query semantics, DTOs, queue coordinator and owned/borrowed runtime lifetime.
- `src/interfaces/cli/` — existing CLI parser and transport bootstrap.
- `src/infrastructure/` — yt-dlp, repositories, FFmpeg detection, MCP server.
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
- S1–S3 are independently accepted for their bounded scopes, including owned cancellation/outcomes, consistent query projections and task-scoped output attribution. Safe deletion and complete adapter lifetime/platform qualification remain S4–S6, not already-implemented guarantees. See [verification](../command-first/VERIFICATION.md).
- GUI layout/design is out of scope for the current command-first refactor.
