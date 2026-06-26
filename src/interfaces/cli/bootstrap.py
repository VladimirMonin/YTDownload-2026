"""Shared bootstrap helpers for CLI and MCP server transports."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def initialize_services() -> dict:
    """Build the shared dependency graph for CLI/MCP entry points."""
    from main import initialize_app

    return initialize_app()


def create_mcp_server(services: dict) -> Any:
    """Create the FastMCP server from initialized services."""
    try:
        from fastmcp import FastMCP
    except ImportError:
        logger.error("mcp.server.fastmcp_missing — install with: uv add fastmcp")
        raise

    mcp = FastMCP(
        name="ytdownload-2026",
        instructions=(
            "YTDownload 2026 MCP server. "
            "Tools for managing YouTube downloads: list, search, add, delete, read content. "
            "Start with list_downloads() to see history. "
            "Use add_download(url) to queue a new video or playlist. "
            "Use get_transcript(id) for subtitle text, read_description(id) for description. "
            "Use get_file_paths(id) to get absolute file paths to downloaded media."
        ),
    )

    from src.infrastructure.mcp.tools import register_all_tools

    register_all_tools(mcp, services)
    logger.info("mcp.server.created tools_registered=True")
    return mcp


def run_http_server(services: dict, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the MCP server over HTTP."""
    import uvicorn

    mcp = create_mcp_server(services)
    logger.info("mcp.server.starting host=%s port=%d", host, port)
    print(f"MCP server starting at http://{host}:{port}/mcp", flush=True)
    app = mcp.http_app(path="/mcp")
    uvicorn.run(app, host=host, port=port, log_level="warning")


def run_stdio_server(services: dict) -> None:
    """Run the MCP server over stdio."""
    mcp = create_mcp_server(services)
    logger.info("mcp.server.starting transport=stdio")
    mcp.run(transport="stdio", show_banner=False)
