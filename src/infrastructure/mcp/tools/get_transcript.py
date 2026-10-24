"""MCP инструмент: get_transcript — читает субтитры/транскрипцию из файла.

Поддерживает .vtt и .srt форматы. Агент может получить текстовый контент
субтитров по ID загрузки и языку, а также абсолютный путь к файлу.

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
from typing import Any

from src.application.api import ApplicationAPI
from src.application.dto import serialize_for_transport
from src.infrastructure.mcp.tools._utils import error_payload

logger = logging.getLogger(__name__)


def create_get_transcript_tool(mcp: Any, api: ApplicationAPI) -> None:
    """Регистрирует инструмент get_transcript в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        api: Shared application API.
    """

    @mcp.tool()
    def get_transcript(
        id: int,
        lang: str | None = None,
        raw: bool = False,
        timestamps: bool = False,
    ) -> dict:
        """Read subtitle/transcript file content for a downloaded video.

        CLI PARITY: `ytdl history transcript <id> [--lang ... --timestamps --raw]`

        USE THIS TOOL WHEN:
        - User wants to read what was said in a video (transcript)
        - User asks for subtitles of a specific download
        - You need the transcript text for summarization, translation, or analysis
        - User wants to find a specific moment or quote from a video
        - User asks "at what time did they say X" → use timestamps=True

        TRIGGER PHRASES:
        - "show me the transcript of download #5"
        - "read the subtitles for that video"
        - "what was said in download 12?"
        - "get the Russian transcript of download 3"
        - "can you summarize the transcript for download 7?"
        - "find the subtitle file for video ID 10"
        - "at what moment did they talk about X?" → use timestamps=True

        WORKFLOW:
        1. Use list_downloads() or search_downloads() to find the ID.
        2. Call get_transcript(id) to get the transcript text.
        3. If multiple subtitle files exist, use lang= to pick a specific language.
        4. Use timestamps=True to get [HH:MM:SS] markers before each phrase.
        5. Set raw=True only if you need the raw .vtt/.srt markup.

        NOTE: Subtitles are only available if save_subtitles=True was set when
        downloading. Check subtitle_paths in get_download(id) first.

        LANGUAGE DETECTION:
        - File names follow pattern: <title>.<lang>.vtt (e.g. "video.ru.vtt")
        - If lang is not specified, the first available subtitle file is returned.
        - To get Russian: lang="ru". English: lang="en". Auto-detected: lang="en-orig".

        TEXT FORMAT:
        - raw=False, timestamps=False (default): clean text, no markup, no duplicates.
        - raw=False, timestamps=True: clean text with [HH:MM:SS] before each phrase.
          Best for finding specific moments: "[00:03:42] Вот как устроена архитектура"
        - raw=True: original VTT/SRT file content with all timing markup.

        EXAMPLES:
        - get_transcript(id=5)                        → clean plain text
        - get_transcript(id=5, timestamps=True)       → [00:01:23] phrase per line
        - get_transcript(id=5, lang="ru")             → Russian subtitles
        - get_transcript(id=5, lang="en", timestamps=True) → English with timecodes
        - get_transcript(id=5, raw=True)              → raw .vtt/.srt with all markup

        Args:
            id: Numeric download ID.
            lang: Optional language code to select a specific subtitle file.
                  E.g. "ru", "en", "kk", "en-orig". None = first available.
            raw: If True, return raw VTT/SRT content with all timing markup.
                 Default False = clean readable text.
            timestamps: If True, prefix each phrase with [HH:MM:SS] timecode.
                  Useful when user wants to find specific moments in a video.
                  Ignored when raw=True.

        Returns:
            Dict with:
            - id: download ID
            - title: video/playlist title
            - transcript_path: absolute path to the subtitle file used
            - transcript_text: clean text content (or raw if raw=True)
            - lang_detected: language code extracted from filename
            - format: "vtt" or "srt"
            - truncated: True if text was cut to 1M char limit
            - available_langs: list of all available language codes
            Returns {"error": ..., "hint": ...} if not found or no subtitles.
        """
        try:
            result = serialize_for_transport(
                api.get_transcript(id, lang=lang, raw=raw, timestamps=timestamps)
            )
            text = result.get("transcript_text")
            logger.info(
                "mcp.get_transcript id=%d timestamps=%s text_len=%d",
                id,
                timestamps,
                len(text) if isinstance(text, str) else 0,
            )
            return result

        except Exception as error:
            payload = error_payload(error)
            logger.error("mcp.get_transcript.failed reason_code=%s", payload["code"])
            return payload
