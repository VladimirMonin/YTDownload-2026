# 01 — Project overview

YTDownload 2026 is a desktop YouTube downloader with a local MCP server.

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
- `src/application/` — coordinator and queue orchestration.
- `src/infrastructure/` — yt-dlp, repositories, FFmpeg detection, MCP server.
- `src/ui/` — PySide6 widgets, managers, theme, icons.
- `tests/` — offline unit tests plus opt-in E2E tests.

## Working style

- Make narrow, reviewable changes.
- Preserve Windows packaging behavior unless the task is explicitly Linux-only.
- Name verification level honestly: unit, offline integration, GUI smoke, MCP smoke, real YouTube E2E.
- Update README or these instructions when setup behavior changes.
- Keep `AGENTS.md` as the required entry point and put detailed agent rules under `docs/agent-instructions/`.
