"""MCP инструмент: add_download — добавить URL в очередь загрузки.

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Допустимые значения для валидации (защита от опечаток агента)
_VALID_QUALITY = {"best", "1080p", "720p", "480p", "360p", "audio"}
_VALID_TYPE = {"video", "audio"}


def create_add_download_tool(mcp: Any, coordinator: Any) -> None:
    """Регистрирует инструмент add_download в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        coordinator: DownloadCoordinator.
    """

    @mcp.tool()
    def add_download(
        url: str,
        quality: str = "720p",
        download_type: str = "video",
        subtitle_lang: str | None = None,
        save_subtitles: bool = False,
        save_description: bool = False,
        save_thumbnail: bool = False,
    ) -> dict:
        """Add a YouTube video or playlist URL to the download queue.

        USE THIS TOOL WHEN:
        - User wants to download a YouTube video or playlist
        - User provides a YouTube URL and asks to fetch/download it
        - User specifies quality, audio-only, or subtitle preferences

        TRIGGER PHRASES:
        - "download this video: <url>"
        - "add to download queue: <url>"
        - "fetch this YouTube video"
        - "download playlist <url>"
        - "download audio only from <url>"
        - "get me the HD version of <url>"
        - "download <url> with Russian subtitles"

        WORKFLOW:
        1. Validate the URL starts with http/https.
        2. Validate quality and download_type values.
        3. Submit to DownloadCoordinator — returns immediately with task_id.
        4. Download runs in background; use list_downloads() to check progress.
        5. Use get_download(task_id) when done to get file paths.

        QUALITY OPTIONS:
        - "best"  → highest available quality
        - "1080p" → Full HD
        - "720p"  → HD (default)
        - "480p"  → SD
        - "360p"  → low quality
        - "audio" → audio track only (sets download_type="audio" automatically)

        DOWNLOAD TYPE:
        - "video" → video + audio merged into .mp4 via FFmpeg (default)
        - "audio" → audio only, saved as .m4a

        EXAMPLES:
        - add_download("https://youtu.be/dQw4w9WgXcQ")
            → 720p video with no extras
        - add_download("https://youtu.be/...", quality="1080p", save_thumbnail=True)
            → 1080p video + thumbnail image
        - add_download("https://youtu.be/...", download_type="audio")
            → audio-only .m4a file
        - add_download("https://youtube.com/playlist?list=...", save_subtitles=True,
                       subtitle_lang="ru")
            → full playlist with Russian subtitles per video
        - add_download("https://youtu.be/...", save_description=True, save_thumbnail=True)
            → video + description .txt + thumbnail image

        Args:
            url: YouTube video or playlist URL (must start with http/https).
            quality: Download quality — see QUALITY OPTIONS above.
            download_type: "video" (merged mp4) or "audio" (m4a only).
            subtitle_lang: Subtitle language code e.g. "ru", "en", "kk". None = skip.
            save_subtitles: Download subtitle files (.vtt/.srt) alongside video.
            save_description: Save video description as .description file.
            save_thumbnail: Save video thumbnail as .webp/.jpg image.

        Returns:
            {"task_id": int, "status": "queued"} on success.
            Use task_id with get_download(id) to check result later.
            Returns {"error": ..., "hint": ...} on failure.
        """
        # Валидация URL
        if not url or not url.strip().startswith(("http://", "https://")):
            return {
                "error": "Invalid URL",
                "hint": "URL must start with http:// or https://",
            }

        # Нормализация quality (если пользователь сказал "audio" в quality)
        quality = quality.lower().strip()
        if quality == "audio":
            download_type = "audio"
            quality = "best"

        if quality not in _VALID_QUALITY:
            return {
                "error": f"Invalid quality '{quality}'",
                "hint": f"Valid values: {', '.join(sorted(_VALID_QUALITY))}",
            }
        if download_type not in _VALID_TYPE:
            return {
                "error": f"Invalid download_type '{download_type}'",
                "hint": "Valid values: video, audio",
            }

        try:
            from src.domain.models.app_settings import DownloadType, QualityOption

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
                url=url.strip(),
                quality=q,
                download_type=dt,
                subtitle_lang=subtitle_lang,
                save_subtitles=save_subtitles,
                save_description=save_description,
                save_thumbnail=save_thumbnail,
            )
            logger.info(
                "mcp.add_download id=%d quality=%s type=%s",
                task_id,
                quality,
                download_type,
            )
            return {
                "task_id": task_id,
                "status": "queued",
                "message": (
                    f"Download #{task_id} queued. "
                    "Use get_download(id) when done to get file paths."
                ),
            }

        except Exception as exc:
            logger.error("mcp.add_download.error", exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}
