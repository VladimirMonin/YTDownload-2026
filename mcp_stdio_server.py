"""Stdio MCP entry point for YTDownload 2026.

Hermes native MCP client starts command-based servers over stdio. The main
application exposes an HTTP MCP endpoint for GUI/runtime use; this wrapper
reuses the same FastMCP tool registration but runs it with stdio transport so
Hermes can auto-discover the tools at startup.
"""

from __future__ import annotations

import sys

from src.interfaces.cli import main as cli_main


def main(argv: list[str] | None = None) -> None:
    """Preserve default stdio and forward explicit help/transport options."""
    arguments = sys.argv[1:] if argv is None else argv
    raise SystemExit(cli_main(["server", "stdio", *arguments]))


if __name__ == "__main__":
    main()
