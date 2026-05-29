"""Stdio MCP entry point for YTDownload 2026.

Hermes native MCP client starts command-based servers over stdio. The main
application exposes an HTTP MCP endpoint for GUI/runtime use; this wrapper
reuses the same FastMCP tool registration but runs it with stdio transport so
Hermes can auto-discover the tools at startup.
"""

from __future__ import annotations

from pathlib import Path

from main import initialize_app
from src.core.logging_setup import setup_logging
from src.infrastructure.mcp.server import create_mcp_server

PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    """Run the YTDownload MCP server over stdio."""
    import os

    os.chdir(PROJECT_ROOT)
    setup_logging()
    services = initialize_app()
    mcp = create_mcp_server(services)
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
