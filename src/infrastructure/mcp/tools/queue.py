"""MCP инструменты для управления очередью загрузок.

Инструменты:
    add_to_queue: Добавить URL в очередь загрузки.
    cancel_download: Отменить загрузку (двухфазное подтверждение).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_queue_tools(mcp: Any, coordinator: Any) -> None:
    """Регистрирует инструменты управления очередью.

    Args:
        mcp: Экземпляр FastMCP.
        coordinator: DownloadCoordinator.
    """

    @mcp.tool()
    def add_to_queue(
        url: str,
        quality: str = "best",
        download_type: str = "video",
        subtitle_lang: str | None = None,
        save_subtitles: bool = False,
        save_description: bool = False,
        save_thumbnail: bool = False,
    ) -> dict:
        """Add a YouTube URL to the download queue.

        TRIGGER PHRASES:
        - "download this video: <url>"
        - "add to download queue"
        - "fetch this YouTube video"
        - "download playlist <url>"
        - "download audio only from <url>"

        WORKFLOW:
        1. Validate URL (must start with http/https).
        2. Submit to DownloadCoordinator queue.
        3. Return immediately with assigned task ID.

        EXAMPLES:
        - add_to_queue("https://youtu.be/dQw4w9WgXcQ") → adds single video
        - add_to_queue("https://youtu.be/...", quality="1080p") → HD download
        - add_to_queue("https://youtu.be/...", download_type="audio") → audio only
        - add_to_queue("https://youtube.com/playlist?list=...", save_subtitles=True)

        Args:
            url: YouTube video or playlist URL.
            quality: One of: best, 1080p, 720p, 480p, 360p, audio.
            download_type: "video" (video+audio merged) or "audio" (audio only).
            subtitle_lang: Subtitle language code e.g. "ru", "en". None = no subs.
            save_subtitles: Whether to download subtitle files.
            save_description: Whether to save video description as .txt.
            save_thumbnail: Whether to save video thumbnail image.

        Returns:
            Dict with task_id (int) and status (str) "queued".
            Returns {"error": ..., "hint": ...} on failure.
        """
        if not url.startswith(("http://", "https://")):
            return {"error": "Invalid URL", "hint": "URL must start with http:// or https://"}

        try:
            from src.domain.models.app_settings import QualityOption, DownloadType

            quality_map = {
                "best": QualityOption.BEST,
                "1080p": QualityOption.P1080,
                "720p": QualityOption.P720,
                "480p": QualityOption.P480,
                "360p": QualityOption.P360,
                "audio": QualityOption.AUDIO,
            }
            q = quality_map.get(quality, QualityOption.BEST)
            dt = DownloadType.AUDIO if download_type == "audio" else DownloadType.VIDEO

            task_id = coordinator.add(
                url=url,
                quality=q,
                download_type=dt,
                subtitle_lang=subtitle_lang,
                save_subtitles=save_subtitles,
                save_description=save_description,
                save_thumbnail=save_thumbnail,
            )
            logger.info("mcp.add_to_queue id=%d status=queued", task_id)
            return {"task_id": task_id, "status": "queued"}

        except Exception as exc:
            logger.error("mcp.add_to_queue.error", exc_info=True)
            return {"error": str(exc), "hint": "Check logs for details"}

    @mcp.tool()
    def cancel_download(id: int, confirm: bool = False) -> dict:
        """Cancel an active or queued download.

        TRIGGER PHRASES:
        - "cancel download #5"
        - "stop download 12"
        - "abort the current download"

        WORKFLOW (two-phase):
        1. confirm=False (default) → returns preview of what will be cancelled.
        2. confirm=True → actually cancels the download.

        ALWAYS call with confirm=False first to get details,
        then call with confirm=True to actually cancel.

        EXAMPLES:
        - cancel_download(id=5) → preview (safe)
        - cancel_download(id=5, confirm=True) → actually cancels

        Args:
            id: Numeric download ID to cancel.
            confirm: Must be True to actually cancel. Default False = preview only.

        Returns:
            Preview dict if confirm=False, or result dict if confirm=True.
        """
        try:
            task = coordinator.get_task(id)
            if task is None:
                return {
                    "error": f"Download #{id} not found",
                    "hint": "Use list_downloads() to see IDs",
                }

            if task.status.is_terminal():
                return {
                    "error": f"Download #{id} is already {task.status}",
                    "hint": "Can only cancel queued or downloading tasks",
                }

            if not confirm:
                return {
                    "preview": True,
                    "id": id,
                    "title": task.title or task.url,
                    "status": task.status,
                    "message": f"Will cancel download #{id}. Call with confirm=True to proceed.",
                }

            coordinator.cancel(id)
            logger.info("mcp.cancel_download id=%d", id)
            return {"id": id, "status": "cancel_requested"}

        except Exception as exc:
            logger.error("mcp.cancel_download.error", exc_info=True)
            return {"error": str(exc), "hint": "Check logs for details"}
