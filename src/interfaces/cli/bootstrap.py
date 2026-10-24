"""CLI composition adapter and backwards-compatible MCP re-exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.infrastructure.mcp.server import create_mcp_server, run_http_server, run_stdio_server


def initialize_services(
    *, data_root: Path | None = None, read_only: bool = False
) -> dict[str, Any]:
    """Create exactly one explicit owner (or a resource-free read-only snapshot)."""
    from main import initialize_app

    return initialize_app(data_root, read_only=read_only)


__all__ = ["initialize_services", "create_mcp_server", "run_http_server", "run_stdio_server"]
