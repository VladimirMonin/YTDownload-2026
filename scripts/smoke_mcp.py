"""MCP tool discovery smoke test."""

from __future__ import annotations

import anyio

from main import initialize_app
from src.infrastructure.mcp.server import create_mcp_server

EXPECTED_TOOLS = {
    "add_download",
    "cancel_download",
    "delete_download",
    "get_download",
    "get_file_paths",
    "get_transcript",
    "list_downloads",
    "read_description",
    "search_downloads",
    "search_with_description",
}


async def _main() -> None:
    mcp = create_mcp_server(initialize_app())
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    missing = EXPECTED_TOOLS - names
    if missing:
        raise SystemExit(f"missing MCP tools: {sorted(missing)}")
    print(f"mcp-smoke ok tools={len(names)}")


def main() -> None:
    anyio.run(_main)


if __name__ == "__main__":
    main()
