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
- `main.py` — dependency wiring / DI container.
- `src/domain/` — data models and protocols.
- `src/application/` — ApplicationAPI, command/query semantics, DTOs and queue coordinator.
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
- GUI layout/design is out of scope for the current command-first refactor.
