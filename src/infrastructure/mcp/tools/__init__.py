"""Пакет MCP инструментов YT Downloader."""

from __future__ import annotations

from typing import Any


def register_all_tools(mcp: Any, services: dict) -> None:
    """Регистрирует все MCP инструменты.

    Args:
        mcp: Экземпляр FastMCP.
        services: Словарь сервисов: history_repo, coordinator.
    """
    from .downloads import register_download_tools
    from .files import register_file_tools
    from .queue import register_queue_tools

    register_download_tools(mcp, services["history_repo"])
    register_file_tools(mcp, services["history_repo"])
    register_queue_tools(mcp, services["coordinator"])


__all__ = ["register_all_tools"]
