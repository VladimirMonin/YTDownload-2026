"""MCP сервер YT Downloader.

Запуск:
    uv run python -m src.infrastructure.mcp.server

Транспорт: Streamable HTTP + SSE (порт 8765 по умолчанию).
Endpoint: http://localhost:8765/mcp
"""

from __future__ import annotations

import sys

from src.interfaces.cli.bootstrap import create_mcp_server, run_http_server

__all__ = ["create_mcp_server", "run_server"]


def run_server(services: dict, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Запускает MCP сервер с uvicorn.

    Args:
        services: Словарь сервисов.
        host: Хост для прослушивания (по умолчанию localhost).
        port: Порт (по умолчанию 8765).
    """
    run_http_server(services, host=host, port=port)


if __name__ == "__main__":
    from src.interfaces.cli import main

    raise SystemExit(main(["server", "http", *sys.argv[1:]]))
