# 04 — MCP and GUI

## GUI smoke on Linux/headless

Use Qt offscreen for non-interactive smoke checks:

```bash
QT_QPA_PLATFORM=offscreen uv run python <script>
```

A useful smoke creates `QApplication`, calls `initialize_app()`, applies the theme, creates `MainWindow`, shows it, processes events, then closes it.

Do not claim full GUI verification from this smoke alone. It only proves initialization.

## MCP smoke

The MCP server is created from initialized services:

```python
from main import initialize_app
from src.infrastructure.mcp.server import create_mcp_server

mcp = create_mcp_server(initialize_app())
tools = await mcp.list_tools()
```

Expected tools currently include:

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

## Real MCP server

Starting the HTTP server binds to a port. Check port availability before long-running server tests. Do not leave background servers running unless needed.
