"""MCP инструмент: get_file_paths — пути ко всем файлам загрузки.

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
from typing import Any

from ._utils import entry_to_dict_full

logger = logging.getLogger(__name__)


def create_get_file_paths_tool(mcp: Any, history_repo: Any) -> None:
    """Регистрирует инструмент get_file_paths в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        history_repo: IHistoryRepository.
    """

    @mcp.tool()
    def get_file_paths(id: int) -> dict:
        """Get all absolute file paths for a completed download.

        USE THIS TOOL WHEN:
        - User asks where a downloaded file is stored
        - You need to programmatically access a downloaded file
        - User wants to open or process a downloaded video/audio/subtitle

        TRIGGER PHRASES:
        - "where is the video file for download 42"
        - "get the subtitle path for download #10"
        - "show me the thumbnail path of download 7"
        - "what files were saved for download 3"
        - "give me the path to the downloaded audio from ID 15"
        - "open the folder with download 5"

        WORKFLOW:
        1. Use list_downloads() or search_downloads() to find the numeric ID.
        2. Call get_file_paths(id) to get all stored paths.
        3. Paths are absolute filesystem paths ready to use.

        EXAMPLES:
        - get_file_paths(id=42) → all saved paths for download #42
        - get_file_paths(id=1)  → paths for the very first download

        Args:
            id: Numeric download ID from list_downloads() or search_downloads().

        Returns:
            Dict with keys:
            - id, title, status
            - video_path: Absolute path to .mp4 video file (or null)
            - audio_path: Absolute path to .m4a audio file (or null)
            - subtitle_paths: List of absolute paths to .vtt/.srt subtitle files
            - description_path: Absolute path to .description .txt (or null)
            - thumbnail_path: Absolute path to thumbnail image (or null)
            - info_json_path: Absolute path to yt-dlp .info.json (or null)
            - output_dir: Absolute path to containing folder (or null)
            Returns {"error": ..., "hint": ...} if ID not found.
        """
        try:
            entry = history_repo.get_by_id(id)
            if entry is None:
                return {
                    "error": f"Download #{id} not found",
                    "hint": "Use list_downloads() or search_downloads() to find valid IDs",
                }
            result = entry_to_dict_full(entry)
            logger.info("mcp.get_file_paths id=%d", id)
            return result
        except Exception as exc:
            logger.error("mcp.get_file_paths.error id=%d", id, exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}
