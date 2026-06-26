"""MCP инструмент: list_downloads — список загрузок с фильтром по статусу.

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
from typing import Any

from src.application.dto import serialize_for_transport

logger = logging.getLogger(__name__)


def create_list_downloads_tool(mcp: Any, api: Any) -> None:
    """Регистрирует инструмент list_downloads в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        api: Shared application API.
    """

    @mcp.tool()
    def list_downloads(status: str | None = None, limit: int = 50) -> list[dict] | dict:
        """List download history entries, optionally filtered by status.

        CLI PARITY: `ytdl history list [--status ... --limit ...]`

        USE THIS TOOL WHEN:
        - User asks to see their downloads
        - User wants to know what's in the download queue
        - User asks about failed or cancelled downloads

        TRIGGER PHRASES:
        - "show my downloads"
        - "what have I downloaded"
        - "list all downloads"
        - "show recent downloads"
        - "what downloads are in progress"
        - "show failed downloads"

        WORKFLOW:
        1. Optionally specify status to filter results.
        2. Returns entries sorted newest-first.
        3. Use get_download(id) to get full details + file paths.

        EXAMPLES:
        - list_downloads() → all entries (up to 50)
        - list_downloads(status="done") → completed downloads only
        - list_downloads(status="failed") → anything that errored
        - list_downloads(status="downloading", limit=10) → active only

        STATUS VALUES:
        - "queued"      — in queue, not started yet
        - "downloading" — actively downloading
        - "merging"     — merging video+audio via FFmpeg
        - "done"        — successfully completed
        - "failed"      — error occurred
        - "cancelled"   — user cancelled

        Args:
            status: Filter by status string (see STATUS VALUES). None = all.
            limit: Max entries to return (default 50, max 200).

        Returns:
            List of dicts with: id, url, title, playlist_title, is_playlist,
            status, quality, download_type, created_at, finished_at, error_message.
            Returns {"error": ..., "hint": ...} on failure.
        """
        try:
            result = serialize_for_transport(api.list_downloads(status=status, limit=limit))
            logger.info("mcp.list_downloads count=%d status_filter=%s", len(result), status)
            return result
        except Exception as exc:
            logger.error("mcp.list_downloads.error", exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}
