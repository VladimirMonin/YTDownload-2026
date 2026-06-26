"""MCP инструмент: get_download — полные детали одной загрузки по ID.

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
from typing import Any

from src.application.dto import serialize_for_transport

logger = logging.getLogger(__name__)


def create_get_download_tool(mcp: Any, api: Any) -> None:
    """Регистрирует инструмент get_download в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        api: Shared application API.
    """

    @mcp.tool()
    def get_download(id: int) -> dict:
        """Get full details of a single download entry by numeric ID.

        CLI PARITY: `ytdl history get <id>`

        USE THIS TOOL WHEN:
        - User asks about a specific download by number
        - You need to find file paths after a download completes
        - User wants to know what files were saved and where

        TRIGGER PHRASES:
        - "show download #42"
        - "what files were saved for download 10"
        - "details of download 5"
        - "where is the video file for download 3"
        - "get info about download ID 7"

        WORKFLOW:
        1. Call list_downloads() first if you don't know the ID.
        2. Call get_download(id) with the numeric ID.
        3. Returns all file paths — video, audio, subtitles, description, thumbnail.

        EXAMPLES:
        - get_download(id=42) → full record with all file paths
        - get_download(id=1)  → very first download in history

        Args:
            id: Numeric auto-increment download ID (from list_downloads or search_downloads).

        Returns:
            Full dict including all file paths:
            id, url, title, playlist_title, status, quality, download_type,
            created_at, finished_at, error_message,
            video_path, audio_path, subtitle_paths, description_path,
            thumbnail_path, info_json_path, output_dir.
            Returns {"error": ..., "hint": ...} if not found.
        """
        try:
            result = serialize_for_transport(api.get_download(id))
            logger.info("mcp.get_download id=%d", id)
            return result
        except Exception as exc:
            logger.error("mcp.get_download.error id=%d", id, exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}
