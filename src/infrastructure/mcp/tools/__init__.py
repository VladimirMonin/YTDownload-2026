"""Пакет MCP инструментов YTDownload 2026.

Каждый инструмент — в отдельном модуле. Большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.

Инструменты:
    list_downloads          — список загрузок с фильтром по статусу
    get_download            — детали загрузки по ID (с путями)
    search_downloads        — поиск по названию/URL
    search_with_description — поиск + текст описания ролика из файла
    get_file_paths          — все абсолютные пути к файлам загрузки
    get_transcript          — читает субтитры/транскрипцию из .vtt/.srt файла
    add_download            — добавить URL в очередь (видео, аудио, плейлист)
    cancel_download         — отмена загрузки (двухфазная)
    delete_download         — удаление из истории + файлы с диска (двухфазная)
    read_description        — читает текст .description файла

Готовность к SQLite/PeeWee:
    - history_repo принимает любой IHistoryRepository
    - _utils.py нормализует enum/строки через _ev()
    - Поля в ответах совпадают с будущей схемой таблицы downloads
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_all_tools(mcp: Any, services: dict) -> None:
    """Регистрирует все MCP инструменты в FastMCP.

    Вызывается из server.py при создании экземпляра сервера.
    Каждый tool импортируется из своего модуля.

    Args:
        mcp: Экземпляр FastMCP.
        services: Словарь сервисов: history_repo, coordinator.
    """
    history_repo = services["history_repo"]
    coordinator = services["coordinator"]

    from .list_downloads import create_list_downloads_tool
    from .get_download import create_get_download_tool
    from .search_downloads import create_search_downloads_tool
    from .get_file_paths import create_get_file_paths_tool
    from .get_transcript import create_get_transcript_tool
    from .add_download import create_add_download_tool
    from .cancel_download import create_cancel_download_tool
    from .delete_download import create_delete_download_tool
    from .read_description import create_read_description_tool

    create_list_downloads_tool(mcp, history_repo)
    create_get_download_tool(mcp, history_repo)
    create_search_downloads_tool(mcp, history_repo)
    create_get_file_paths_tool(mcp, history_repo)
    create_get_transcript_tool(mcp, history_repo)
    create_add_download_tool(mcp, coordinator)
    create_cancel_download_tool(mcp, coordinator)
    create_delete_download_tool(mcp, history_repo)
    create_read_description_tool(mcp, history_repo)

    logger.info("mcp.tools.registered count=9")


__all__ = ["register_all_tools"]
