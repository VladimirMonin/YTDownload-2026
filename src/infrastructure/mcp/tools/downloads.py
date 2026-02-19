"""MCP инструменты для работы с историей загрузок.

Инструменты:
    list_downloads: Список загрузок с фильтрацией по статусу.
    get_download: Детали конкретной загрузки по ID.
    search_downloads: Полнотекстовый поиск по названию/URL.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_download_tools(mcp: Any, history_repo: Any) -> None:
    """Регистрирует инструменты для работы с историей загрузок.

    Args:
        mcp: Экземпляр FastMCP.
        history_repo: IHistoryRepository.
    """

    @mcp.tool()
    def list_downloads(status: str | None = None, limit: int = 50) -> list[dict]:
        """List download history entries.

        TRIGGER PHRASES:
        - "show my downloads"
        - "what have I downloaded"
        - "list all downloads"
        - "show recent downloads"
        - "downloads in progress"

        WORKFLOW:
        1. Load all history entries from JSON storage.
        2. Optionally filter by status.
        3. Return sorted by created_at desc (newest first).

        EXAMPLES:
        - list_downloads() → all downloads
        - list_downloads(status="done") → completed downloads only
        - list_downloads(status="failed", limit=20) → recent failures

        Args:
            status: Filter by status. One of: queued, downloading,
                    merging, done, failed, cancelled. None = all.
            limit: Maximum number of entries to return (default 50).

        Returns:
            List of download dicts with id, title, url, status, quality,
            created_at, finished_at.
        """
        try:
            entries = history_repo.get_all()
            if status:
                entries = [e for e in entries if e.status == status]
            # По убыванию даты
            entries.sort(key=lambda e: e.created_at or "", reverse=True)
            entries = entries[:limit]
            result = [_entry_to_dict(e, short=True) for e in entries]
            logger.info("mcp.list_downloads count=%d status=%s", len(result), status)
            return result
        except Exception as exc:
            logger.error("mcp.list_downloads.error", exc_info=True)
            return [{"error": str(exc), "hint": "Check logs for details"}]

    @mcp.tool()
    def get_download(id: int) -> dict:
        """Get full details of a single download by ID.

        TRIGGER PHRASES:
        - "show download #42"
        - "what files were downloaded for ID 10"
        - "details of download 5"
        - "where is the video file for download 3"

        WORKFLOW:
        1. Load entry from history by numeric ID.
        2. Return all fields including all file paths.

        EXAMPLES:
        - get_download(id=42) → full details with all file paths
        - get_download(id=1) → very first download

        Args:
            id: Numeric auto-increment download ID.

        Returns:
            Full download dict including video_path, audio_path,
            subtitle_paths, description_path, thumbnail_path.
            Returns {"error": ..., "hint": ...} if not found.
        """
        try:
            entry = history_repo.get_by_id(id)
            if entry is None:
                return {
                    "error": f"Download #{id} not found",
                    "hint": "Use list_downloads() to see valid IDs",
                }
            logger.info("mcp.get_download id=%d status=%s", id, entry.status)
            return _entry_to_dict(entry, short=False)
        except Exception as exc:
            logger.error("mcp.get_download.error", exc_info=True)
            return {"error": str(exc), "hint": "Check logs for details"}

    @mcp.tool()
    def search_downloads(query: str, limit: int = 20) -> list[dict]:
        """Search downloads by title or URL (case-insensitive substring).

        TRIGGER PHRASES:
        - "find download with 'python tutorial'"
        - "search for Rick Astley"
        - "did I download anything about cats?"
        - "find all downloads from channel X"

        WORKFLOW:
        1. Search history by case-insensitive substring in title + URL.
        2. Sort by relevance (exact title match first, then partial).
        3. Return up to limit results.

        EXAMPLES:
        - search_downloads("python") → all downloads with "python" in title or URL
        - search_downloads("playlist", limit=5) → first 5 matching

        Args:
            query: Search query string.
            limit: Maximum results to return (default 20).

        Returns:
            List of matching download dicts (short format).
        """
        try:
            entries = history_repo.search(query)[:limit]
            result = [_entry_to_dict(e, short=True) for e in entries]
            logger.info("mcp.search_downloads count=%d", len(result))
            return result
        except Exception as exc:
            logger.error("mcp.search_downloads.error", exc_info=True)
            return [{"error": str(exc), "hint": "Check logs for details"}]


def _entry_to_dict(entry: Any, short: bool = True) -> dict:
    """Сериализует HistoryEntry в dict для MCP ответов."""
    d: dict = {
        "id": entry.id,
        "url": entry.url,
        "title": entry.title or "",
        "status": entry.status,
        "quality": entry.quality,
        "download_type": entry.download_type,
        "created_at": entry.created_at,
        "finished_at": entry.finished_at,
    }
    if not short:
        d["video_path"] = str(entry.video_path) if entry.video_path else None
        d["audio_path"] = str(entry.audio_path) if entry.audio_path else None
        d["subtitle_paths"] = [str(p) for p in entry.subtitle_paths]
        d["description_path"] = str(entry.description_path) if entry.description_path else None
        d["thumbnail_path"] = str(entry.thumbnail_path) if entry.thumbnail_path else None
        d["info_json_path"] = str(entry.info_json_path) if entry.info_json_path else None
        d["output_dir"] = str(entry.output_dir) if entry.output_dir else None
    return d
