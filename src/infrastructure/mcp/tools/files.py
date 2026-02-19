"""MCP инструменты для работы с файлами загрузки.

Инструменты:
    get_file_paths: Пути ко всем файлам конкретной загрузки.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_file_tools(mcp: Any, history_repo: Any) -> None:
    """Регистрирует инструменты работы с файлами.

    Args:
        mcp: Экземпляр FastMCP.
        history_repo: IHistoryRepository.
    """

    @mcp.tool()
    def get_file_paths(id: int) -> dict:
        """Get all file paths for a completed download.

        TRIGGER PHRASES:
        - "where is the video file for download 42"
        - "get the subtitle path for download #10"
        - "show me the thumbnail path of download 7"
        - "what files were saved for download 3"
        - "give me the path to the downloaded audio from ID 15"

        WORKFLOW:
        1. Load HistoryEntry by ID from JSON storage.
        2. Return all stored file paths.
        3. Paths are absolute filesystem paths.

        EXAMPLES:
        - get_file_paths(id=42) → all paths for download 42
        - get_file_paths(id=1) → paths for very first download

        Args:
            id: Numeric download ID.

        Returns:
            Dict with keys:
            - video_path: Absolute path to video file (or null).
            - audio_path: Absolute path to audio file (or null).
            - subtitle_paths: List of absolute paths to subtitle files.
            - description_path: Absolute path to description .txt (or null).
            - thumbnail_path: Absolute path to thumbnail image (or null).
            - info_json_path: Absolute path to yt-dlp .info.json (or null).
            - output_dir: Absolute path to the download folder (or null).
            Returns {"error": ..., "hint": ...} if not found.
        """
        try:
            entry = history_repo.get_by_id(id)
            if entry is None:
                return {
                    "error": f"Download #{id} not found",
                    "hint": "Use list_downloads() to see valid IDs",
                }

            result = {
                "id": id,
                "title": entry.title or "",
                "status": entry.status,
                "video_path": str(entry.video_path) if entry.video_path else None,
                "audio_path": str(entry.audio_path) if entry.audio_path else None,
                "subtitle_paths": [str(p) for p in entry.subtitle_paths],
                "description_path": str(entry.description_path) if entry.description_path else None,
                "thumbnail_path": str(entry.thumbnail_path) if entry.thumbnail_path else None,
                "info_json_path": str(entry.info_json_path) if entry.info_json_path else None,
                "output_dir": str(entry.output_dir) if entry.output_dir else None,
            }
            logger.info("mcp.get_file_paths id=%d status=%s", id, entry.status)
            return result

        except Exception as exc:
            logger.error("mcp.get_file_paths.error", exc_info=True)
            return {"error": str(exc), "hint": "Check logs for details"}
