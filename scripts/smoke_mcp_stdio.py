# pyright: reportMissingImports=false

"""Offline stdio MCP parity smoke.

Starts the checked-in stdio wrapper with the same
`uv run python -m src.interfaces.cli server stdio` command Hermes can use and
verifies tool discovery through a
real stdio MCP client. This is intentionally a smoke/parity check, not a full
end-to-end download flow.
"""

from __future__ import annotations

from pathlib import Path

import anyio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from scripts.mcp_expected_tools import EXPECTED_TOOLS

PROJECT_ROOT = Path(__file__).resolve().parent.parent


async def _main() -> None:
    transport = StdioTransport(
        command="uv",
        args=["run", "python", "-m", "src.interfaces.cli", "server", "stdio"],
        cwd=str(PROJECT_ROOT),
    )
    async with Client(transport) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools}
    missing = EXPECTED_TOOLS - names
    unexpected = names - EXPECTED_TOOLS
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing={sorted(missing)}")
        if unexpected:
            details.append(f"unexpected={sorted(unexpected)}")
        raise SystemExit("stdio-mcp-smoke mismatch " + " ".join(details))
    print(f"stdio-mcp-smoke ok tools={len(names)}")


def main() -> None:
    anyio.run(_main)


if __name__ == "__main__":
    main()