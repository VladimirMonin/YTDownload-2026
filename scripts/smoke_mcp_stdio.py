"""Offline real stdio discovery through the existing CLI parser/bootstrap.

The current-interpreter child injects its own services into CLI main so it can
join the legacy coordinator in finally. This is discovery, not download E2E or
proof of standalone CLI runtime shutdown (that lifecycle is a later slice).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from scripts.smoke_support import close_services, isolated_smoke

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _serve() -> None:
    from main import initialize_app
    from src.interfaces.cli import main as cli_main

    services = None
    result = None
    try:
        services = initialize_app()
        result = cli_main(["server", "stdio"], services=services)
    finally:
        try:
            close_services(services)
        finally:
            logging.shutdown()
        # Own smoke receipt, never written to MCP protocol stdout.
        receipt = Path(os.environ["YTDL_LOG_DIR"]) / "stdio-child-cleanup.txt"
        receipt.write_text(
            f"coordinator_joined={services is not None}\ncli_exit={result}\n", encoding="utf-8"
        )
    raise SystemExit(result)


async def _main() -> None:
    import anyio
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    from scripts.mcp_expected_tools import EXPECTED_TOOLS

    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "scripts.smoke_mcp_stdio", "--serve"],
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
        keep_alive=False,
    )
    try:
        with anyio.fail_after(30):
            async with Client(transport) as client:
                tools = await client.list_tools()
    finally:
        # Also covers connect/initialization failure before Client.__aenter__.
        with anyio.CancelScope(shield=True):
            with anyio.fail_after(10):
                await transport.close()
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
    receipt = Path(os.environ["YTDL_LOG_DIR"]) / "stdio-child-cleanup.txt"
    if receipt.read_text(encoding="utf-8") != "coordinator_joined=True\ncli_exit=0\n":
        raise SystemExit("stdio-mcp-smoke child cleanup was not confirmed")
    print(f"stdio-mcp-smoke ok tools={len(names)} child_coordinator_joined=True")


def main() -> None:
    if sys.argv[1:] == ["--serve"]:
        _serve()
    else:
        with isolated_smoke():
            import anyio

            anyio.run(_main)


if __name__ == "__main__":
    main()
