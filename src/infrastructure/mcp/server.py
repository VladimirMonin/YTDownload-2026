"""MCP сервер YT Downloader.

Запуск:
    uv run python -m src.infrastructure.mcp.server

Транспорт: Streamable HTTP + SSE (порт 8765 по умолчанию).
Endpoint: http://localhost:8765/mcp
"""

from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def create_mcp_server(services: dict):  # type: ignore[return]
    """Создаёт и настраивает экземпляр FastMCP.

    Args:
        services: Словарь сервисов (history_repo, coordinator, ...).

    Returns:
        Настроенный экземпляр FastMCP.
    """
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

    from .tools import register_all_tools

    register_all_tools(mcp, services)
    logger.info("mcp.server.created tools_registered=True")
    return mcp


def run_server(services: dict, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Запускает MCP сервер с uvicorn.

    Args:
        services: Словарь сервисов.
        host: Хост для прослушивания (по умолчанию localhost).
        port: Порт (по умолчанию 8765).
    """
    import uvicorn

    mcp = create_mcp_server(services)

    logger.info("mcp.server.starting host=%s port=%d", host, port)
    print(f"MCP server starting at http://{host}:{port}/mcp", flush=True)

    # Получаем ASGI-приложение из FastMCP
    app = mcp.http_app(path="/mcp")

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    from src.core.logging_setup import setup_logging

    setup_logging()

    parser = argparse.ArgumentParser(description="YT Downloader MCP Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    from main import initialize_app

    services = initialize_app()
    run_server(services, host=args.host, port=args.port)
