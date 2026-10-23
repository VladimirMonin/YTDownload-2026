# 04 — MCP and GUI

## Common checks

Use the existing environment from the project root, with pre-process isolation per
[testing](../../.github/instructions/testing.instructions.md). The checked-in smokes
allocate a narrower owned subtree before application/Qt/MCP imports; an optional
`YTDL_SMOKE_ROOT` points to an existing owned parent. They retain synthetic files,
restore env, close their handlers and join their own legacy coordinator executor.
They explicitly override YTDL_DATA_DIR into that subtree as well as APPDATA/home;
an inherited profile must not be opened/recovered. R1 checks real child success,
unchanged competing history/artifacts/no-lock and present/absent × normal/failure
restoration. The transitional private join notifies the runtime owner. Core S3
cooperative cancellation/outcome schedules are accepted separately; this discovery
smoke is not active-job/standalone/GUI adapter-lifetime acceptance (still S5).

```bash
uv run --locked --no-sync python -m scripts.smoke_cli_help
uv run --locked --no-sync python -m scripts.smoke_mcp
uv run --locked --no-sync python -m scripts.smoke_mcp_stdio
uv run --locked --no-sync python -m scripts.smoke_gui
```

`smoke_cli_help.py` covers the unified `src.interfaces.cli` command tree and
help/examples. `smoke_mcp.py` and `smoke_mcp_stdio.py` cover MCP discovery
parity. None of these replace real add/cancel/download validation.

## GUI smoke on Linux/headless

Use Qt offscreen for non-interactive smoke checks. The checked-in script sets this automatically:

```bash
QT_QPA_PLATFORM=offscreen uv run --locked --no-sync python -m scripts.smoke_gui
```

A useful smoke creates `QApplication`, calls `initialize_app()`, applies the theme, creates `MainWindow`, shows it, processes events, then closes it.

Do not claim full GUI verification from this smoke alone. It only proves initialization and basic event-loop startup, not full interactive GUI behavior.

## MCP smoke

The offline smoke initializes real services, passes them to `create_mcp_server`,
checks `list_tools()` with a timeout, then joins its coordinator in `finally`,
including factory/discovery failures. It does not bind HTTP or invoke download tools.

Expected tools currently include 10 user-facing tools:

- `list_downloads`
- `get_download`
- `search_downloads`
- `search_with_description`
- `get_file_paths`
- `get_transcript`
- `read_description`
- `add_download`
- `cancel_download`
- `delete_download`

Canonical source of truth for these names/counts lives in
`src/infrastructure/mcp/manifest.py`; `scripts/mcp_expected_tools.py` imports
that manifest for smoke checks, and regression tests verify this markdown list
matches the manifest too.

This smoke proves tool-registration parity for the shared `create_mcp_server(...)` path. It does not, by itself, prove a full end-to-end stdio session.

## Stdio MCP entry point

Hermes native MCP can run the project over stdio via:

```bash
uv run --locked --no-sync python -m src.interfaces.cli server stdio
```

Compatibility wrapper: `uv run --locked --no-sync python mcp_stdio_server.py`
delegates into the same module path. The earlier spelling
`uv run python -m src.interfaces.cli server stdio` names that same canonical path;
for existing-environment checks use the locked/no-sync command above, not an
implicit environment sync.

The stdio command initializes the same services as the HTTP server and calls
`mcp.run(transport="stdio", show_banner=False)`.

Because both transports reuse `create_mcp_server(...)`, keep user-facing tool docs and expected tool counts aligned with `scripts/smoke_mcp.py` and `src/infrastructure/mcp/server.py`.

For an offline parity check against the real stdio boundary, run:

```bash
uv run --locked --no-sync python -m scripts.smoke_mcp_stdio
```

The real MCP client starts the current interpreter with
`-m scripts.smoke_mcp_stdio --serve`, explicitly passing the isolated environment.
That child creates its own services and calls the real CLI
`main(["server", "stdio"], services=...)`, joining the legacy coordinator in finally.
Discovery is bounded (30 s; separate transport cleanup limit 10 s), keep-alive is
disabled, and an owned cleanup receipt is checked after close. Independent S1
also observed actual child exits with an outer watchdog, not just that flag.
Report this as `stdio MCP smoke / parity`, not tool-effect E2E or proof of the
unchanged standalone CLI's lifetime. Real synthetic tool effects and complete
standalone stdio lifetime/finally wiring remain S5; [current evidence](../command-first/VERIFICATION.md).

## Current application ownership boundary

`main.initialize_app()` is a `create_runtime` wrapper with the same facade aliases
and an additional owning `runtime`. Separate processes on one writable canonical
root now refuse with OWNER_BUSY, rather than sharing an in-memory queue. A direct
Python readonly/task/wait APIs and S3 runtime-owned cancellation are available;
new real-backend artifacts use output_root/download-<task_id>/… and actual stored
paths, not title-based ownership. Current CLI queries/standalone server cleanup
have not yet been migrated to the complete S5 contract. Do not describe shared
library/services as external attach, or expose the local HTTP endpoint to an
untrusted network based on this offline smoke evidence.

## Real validation gate

Keep these separate from offline smoke:

- real `add_download` / `queue add` against a live YouTube URL;
- real `cancel_download` / `queue cancel --confirm` on an active task;
- sidecar artifact propagation (`.description`, subtitles, thumbnail,
  `.info.json`) on a real download;
- real stdio tool invocation through the unified path with live side effects.

## Real MCP server

Starting the HTTP server binds to a port. Check port availability before long-running server tests. Do not leave background servers running unless needed.
