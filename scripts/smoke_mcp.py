"""Offline MCP discovery, with isolated paths and an explicitly joined owner."""

from __future__ import annotations

from scripts.smoke_support import close_services, isolated_smoke


async def _main() -> None:
    import anyio

    from main import initialize_app
    from scripts.mcp_expected_tools import EXPECTED_TOOLS, MCP_TOOL_COUNT
    from src.infrastructure.mcp.server import create_mcp_server

    services = None
    try:
        services = initialize_app()
        mcp = create_mcp_server(services)
        with anyio.fail_after(20):
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
    finally:
        close_services(services)
    print(f"mcp-smoke ok tools={len(names)} expected={MCP_TOOL_COUNT}")


def main() -> None:
    with isolated_smoke():
        import anyio

        anyio.run(_main)


if __name__ == "__main__":
    main()
