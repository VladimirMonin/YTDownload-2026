# 04 — MCP and GUI

## Common checks

Use the checked-in smoke scripts instead of ad-hoc snippets when possible:

```bash
uv run python scripts/smoke_cli_help.py
uv run python scripts/smoke_mcp.py
uv run python scripts/smoke_mcp_stdio.py
uv run python scripts/smoke_gui.py
```

`smoke_cli_help.py` covers the unified `src.interfaces.cli` command tree and
help/examples. `smoke_mcp.py` and `smoke_mcp_stdio.py` cover MCP discovery
parity. None of these replace real add/cancel/download validation.

## GUI smoke on Linux/headless

Use Qt offscreen for non-interactive smoke checks. The checked-in script sets this automatically:

```bash
QT_QPA_PLATFORM=offscreen uv run python <script>
```

A useful smoke creates `QApplication`, calls `initialize_app()`, applies the theme, creates `MainWindow`, shows it, processes events, then closes it.

Do not claim full GUI verification from this smoke alone. It only proves initialization and basic event-loop startup, not full interactive GUI behavior.

## MCP smoke

The offline smoke script verifies tool discovery from initialized services:

```python
from main import initialize_app
from src.infrastructure.mcp.server import create_mcp_server

mcp = create_mcp_server(initialize_app())
tools = await mcp.list_tools()
```

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
uv run python -m src.interfaces.cli server stdio
```

Compatibility wrapper: `uv run python mcp_stdio_server.py` delegates into the
same `src.interfaces.cli server stdio` path for older scripts.

The stdio command initializes the same services as the HTTP server and calls
`mcp.run(transport="stdio", show_banner=False)`.

Because both transports reuse `create_mcp_server(...)`, keep user-facing tool docs and expected tool counts aligned with `scripts/smoke_mcp.py` and `src/infrastructure/mcp/server.py`.

For an offline parity check against the real stdio boundary, run:

```bash
uv run python scripts/smoke_mcp_stdio.py
```

This starts `uv run python -m src.interfaces.cli server stdio` under a real
stdio MCP client and compares discovered tool names with the checked-in expected
tool set. Report it as `stdio MCP smoke / parity`, not full E2E.

## Real validation gate

Keep these separate from offline smoke:

- real `add_download` / `queue add` against a live YouTube URL;
- real `cancel_download` / `queue cancel --confirm` on an active task;
- sidecar artifact propagation (`.description`, subtitles, thumbnail,
  `.info.json`) on a real download;
- real stdio tool invocation through the unified path with live side effects.

## Real MCP server

Starting the HTTP server binds to a port. Check port availability before long-running server tests. Do not leave background servers running unless needed.
