"""MCP инструмент: search_downloads — поиск по истории.

Два режима:
    search_downloads       — быстрый поиск, только мета-данные.
    search_with_description — поиск + подгружает текст описания из файла.

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
from typing import Any

from src.application.dto import serialize_for_transport

logger = logging.getLogger(__name__)

def create_search_downloads_tool(mcp: Any, api: Any) -> None:
    """Регистрирует инструменты поиска в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        api: Shared application API.
    """

    @mcp.tool()
    def search_downloads(query: str, limit: int = 20) -> list[dict] | dict:
        """Search download history by title or URL (case-insensitive substring).

        CLI PARITY: `ytdl history search <query>`

        USE THIS TOOL WHEN:
        - User asks to find a specific video/playlist by name
        - User wants to know if something was downloaded before
        - User searches for downloads from a specific channel or about a topic

        TRIGGER PHRASES:
        - "find download with 'python tutorial'"
        - "search for Rick Astley"
        - "did I download anything about Django?"
        - "find all downloads from channel MongoDB"
        - "was this video downloaded?"

        WORKFLOW:
        1. Provide a query string — it will be matched against title and URL.
        2. Empty string matches everything (same as list_downloads).
        3. Use get_download(id) to get full details + file paths of a result.

        EXAMPLES:
        - search_downloads("python") → all entries with "python" in title or URL
        - search_downloads("MongoDB", limit=5) → first 5 matching MongoDB videos
        - search_downloads("") → all downloads (same as list_downloads)
        - search_downloads("playlist") → playlist downloads

        Args:
            query: Case-insensitive substring to search in title and URL.
                   Empty string returns all (respects limit).
            limit: Maximum results to return (default 20, max 100).

        Returns:
            List of matching dicts (short format, no file paths).
            Use get_download(id) to get file paths.
            Returns {"error": ..., "hint": ...} on failure.
        """
        try:
            result = serialize_for_transport(api.search_downloads(query, limit=limit))
            logger.info("mcp.search_downloads count=%d query_len=%d", len(result), len(query))
            return result
        except Exception as exc:
            logger.error("mcp.search_downloads.error", exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}

    @mcp.tool()
    def search_with_description(query: str, limit: int = 10) -> list[dict] | dict:
        """Search downloads and include saved video description text in results.

        CLI PARITY: `ytdl history search <query> --with-description`

        USE THIS TOOL WHEN:
        - User wants to find videos by their content (not just title)
        - User asks "what was that video about Python decorators about?"
        - User needs to find videos with specific content that may be in description

        TRIGGER PHRASES:
        - "search downloads including descriptions"
        - "find what was written in the description of that download"
        - "look for downloads that mention OAuth in their description"
        - "search video content about async/await"

        WORKFLOW:
        1. Searches history by title/URL (same as search_downloads).
        2. For each result, loads and attaches the saved .description file text.
        3. If no description was saved, description_text will be null.

        NOTE: Use a smaller limit (5-10) because descriptions can be long.

        EXAMPLES:
        - search_with_description("python") → matching videos with their descriptions
        - search_with_description("lesson 1", limit=5) → first 5 matches + descriptions

        Args:
            query: Case-insensitive substring to search in title and URL.
                   Empty string returns most recent downloads.
            limit: Max results (default 10, max 30). Keep low — descriptions are large.

        Returns:
            List of dicts (full format + description_text field).
            description_text: string content of .description file, or null if not saved.
            Returns {"error": ..., "hint": ...} on failure.
        """
        try:
            result = serialize_for_transport(
                api.search_downloads(query, limit=limit, with_description=True)
            )

            logger.info(
                "mcp.search_with_description count=%d query_len=%d",
                len(result),
                len(query),
            )
            return result
        except Exception as exc:
            logger.error("mcp.search_with_description.error", exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}
