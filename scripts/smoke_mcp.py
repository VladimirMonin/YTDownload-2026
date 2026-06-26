"""MCP tool discovery smoke test."""

from __future__ import annotations

import anyio

from main import initialize_app
from scripts.mcp_expected_tools import EXPECTED_TOOLS, MCP_TOOL_COUNT
from src.infrastructure.mcp.server import create_mcp_server


async def _main() -> None:
    mcp = create_mcp_server(initialize_app())
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    missing = EXPECTED_TOOLS - names
    unexpected = names - EXPECTED_TOOLS
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing={sorted(missing)}")
        if unexpected:
            details.append(f"unexpected={sorted(unexpected)}")
        raise SystemExit("mcp-smoke mismatch " + " ".join(details))
    print(f"mcp-smoke ok tools={len(names)} expected={MCP_TOOL_COUNT}")


def main() -> None:
    anyio.run(_main)


if __name__ == "__main__":
    main()
