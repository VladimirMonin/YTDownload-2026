"""MCP инструмент: read_description — читает текст описания видео из файла.

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
from typing import Any

from src.application.dto import serialize_for_transport

logger = logging.getLogger(__name__)

def create_read_description_tool(mcp: Any, api: Any) -> None:
    """Регистрирует инструмент read_description в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        api: Shared application API.
    """

    @mcp.tool()
    def read_description(id: int) -> dict:
        """Read the full saved video description text for a download.

        CLI PARITY: `ytdl history description <id>`

        USE THIS TOOL WHEN:
        - User wants to read the description of a downloaded video
        - User asks "what is this video about" for a specific download
        - You need the full description text for summarization or analysis
        - User asks for details about the course/playlist from description

        TRIGGER PHRASES:
        - "show me the description of download #5"
        - "what was written in the description of that video?"
        - "read the description for download 12"
        - "show the video description for ID 7"
        - "what does this course describe? (download #3)"

        WORKFLOW:
        1. Load HistoryEntry by ID.
        2. Read the .description file that was saved during download.
        3. Returns the full text (up to 64 KB).

        NOTE: Description is only available if save_description=True was set
        when the download was queued. Check description_path != null in get_download().

        EXAMPLES:
        - read_description(id=5)  → full description text for download #5
        - read_description(id=12) → course description for playlist download #12

        Args:
            id: Numeric download ID.

        Returns:
            Dict with:
            - id: download ID
            - title: video/playlist title
            - description_path: absolute path to the file (or null)
            - description_text: full text content (or null if not saved)
            - truncated: true if text was cut to 64 KB limit
            Returns {"error": ..., "hint": ...} if download not found.
        """
        try:
            result = serialize_for_transport(api.read_description(id))
            logger.info(
                "mcp.read_description id=%d text_len=%d",
                id,
                len(result.get("description_text") or ""),
            )
            return result

        except Exception as exc:
            logger.error("mcp.read_description.error id=%d", id, exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}
