"""MCP инструмент: get_transcript — читает субтитры/транскрипцию из файла.

Поддерживает .vtt и .srt форматы. Агент может получить текстовый контент
субтитров по ID загрузки и языку, а также абсолютный путь к файлу.

Каждый инструмент в отдельном модуле: большие docstring становятся промптами
для LLM-агентов, поэтому читаемость и изоляция критически важны.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Лимит на очищенный текст (после удаления таймкодов/тегов)
# Raw VTT обычно в 3-4x больше чистого текста — читаем файл целиком
_MAX_CHARS = 1_000_000  # 1 млн символов ~ 1 MB чистого текста


def create_get_transcript_tool(mcp: Any, history_repo: Any) -> None:
    """Регистрирует инструмент get_transcript в FastMCP.

    Args:
        mcp: Экземпляр FastMCP.
        history_repo: IHistoryRepository.
    """

    @mcp.tool()
    def get_transcript(id: int, lang: str | None = None, raw: bool = False) -> dict:
        """Read subtitle/transcript file content for a downloaded video.

        USE THIS TOOL WHEN:
        - User wants to read what was said in a video (transcript)
        - User asks for subtitles of a specific download
        - You need the transcript text for summarization, translation, or analysis
        - User wants to find a specific moment or quote from a video

        TRIGGER PHRASES:
        - "show me the transcript of download #5"
        - "read the subtitles for that video"
        - "what was said in download 12?"
        - "get the Russian transcript of download 3"
        - "can you summarize the transcript for download 7?"
        - "find the subtitle file for video ID 10"
        - "get the path to the English subtitles for download 4"

        WORKFLOW:
        1. Use list_downloads() or search_downloads() to find the ID.
        2. Call get_transcript(id) to get the transcript text.
        3. If multiple subtitle files exist, use lang= to pick a specific language.
        4. Set raw=True only if you need the raw .vtt/.srt markup with timestamps.

        NOTE: Subtitles are only available if save_subtitles=True was set when
        downloading. Check subtitle_paths in get_download(id) first.

        LANGUAGE DETECTION:
        - File names follow pattern: <title>.<lang>.vtt (e.g. "video.ru.vtt")
        - If lang is not specified, the first available subtitle file is returned.
        - To get Russian: lang="ru". English: lang="en". Auto-detected: lang="en-orig".

        TEXT FORMAT:
        - By default (raw=False): returns clean text without VTT/SRT markup and
          without duplicate lines (consecutive identical lines merged).
        - raw=True: returns the original file content with all timestamps.

        EXAMPLES:
        - get_transcript(id=5)               → clean text of first subtitle file
        - get_transcript(id=5, lang="ru")    → Russian subtitles text
        - get_transcript(id=5, lang="en")    → English subtitles text
        - get_transcript(id=5, raw=True)     → raw .vtt/.srt with timestamps
        - get_transcript(id=12, lang="auto") → auto-generated subtitles (if "auto" in name)

        Args:
            id: Numeric download ID.
            lang: Optional language code to select a specific subtitle file.
                  E.g. "ru", "en", "kk", "en-orig". None = first available.
            raw: If True, return raw VTT/SRT content with timestamps.
                 Default False = clean readable text.

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
            entry = history_repo.get_by_id(id)
            if entry is None:
                return {
                    "error": f"Download #{id} not found",
                    "hint": "Use list_downloads() to see valid IDs",
                }

            subtitle_paths: list[Path] = [
                Path(p) for p in (entry.subtitle_paths or []) if p and Path(p).exists()
            ]

            if not subtitle_paths:
                return {
                    "id": id,
                    "title": entry.playlist_title or entry.title or "",
                    "transcript_path": None,
                    "transcript_text": None,
                    "lang_detected": None,
                    "format": None,
                    "truncated": False,
                    "available_langs": [],
                    "hint": (
                        "No subtitle files found for this download. "
                        "Re-download with save_subtitles=True to get them."
                    ),
                }

            # Определяем доступные языки
            available_langs = [_extract_lang(p) for p in subtitle_paths]

            # Выбираем нужный файл
            chosen: Path | None = None
            if lang:
                lang_lower = lang.lower().strip()
                for p in subtitle_paths:
                    if lang_lower in p.name.lower():
                        chosen = p
                        break
                if chosen is None:
                    return {
                        "error": f"No subtitle file found for language '{lang}'",
                        "hint": f"Available languages: {', '.join(available_langs)}",
                        "available_langs": available_langs,
                        "id": id,
                    }
            else:
                chosen = subtitle_paths[0]

            # Читаем файл целиком — лимит применяем ПОСЛЕ очистки
            # (raw VTT ~3-4x больше чистого текста по объёму)
            content = chosen.read_text(encoding="utf-8", errors="replace")

            fmt = "srt" if chosen.suffix.lower() == ".srt" else "vtt"
            lang_detected = _extract_lang(chosen)

            if raw:
                text = content
            else:
                text = _clean_subtitle_text(content, fmt)

            # Обрезаем если текст превышает лимит
            truncated = len(text) > _MAX_CHARS
            if truncated:
                text = text[:_MAX_CHARS]

            logger.info(
                "mcp.get_transcript id=%d lang=%s text_len=%d",
                id,
                lang_detected,
                len(text),
            )

            return {
                "id": id,
                "title": entry.playlist_title or entry.title or "",
                "transcript_path": str(chosen),
                "transcript_text": text or None,
                "lang_detected": lang_detected,
                "format": fmt,
                "truncated": truncated,
                "available_langs": available_langs,
            }

        except Exception as exc:
            logger.error("mcp.get_transcript.error id=%d", id, exc_info=True)
            return {"error": str(exc), "hint": "Check app logs for details"}


def _extract_lang(path: Path) -> str:
    """Извлекает код языка из имени файла.

    Паттерн: <title>.<lang>.vtt или <title>.<lang>.srt
    Например: "video.ru.vtt" → "ru", "title.en-orig.vtt" → "en-orig"

    Args:
        path: Путь к файлу субтитров.

    Returns:
        Код языка или "unknown".
    """
    stem = path.stem  # "video.ru" или "video.en-orig"
    parts = stem.rsplit(".", 1)
    if len(parts) == 2:
        candidate = parts[1]
        # Проверяем что это похоже на код языка (2-10 символов, только буквы-дефис)
        if re.match(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]+)*$", candidate):
            return candidate.lower()
    return "unknown"


def _clean_subtitle_text(content: str, fmt: str) -> str:
    """Преобразует VTT/SRT в читаемый текст без разметки и дублей.

    Args:
        content: Содержимое файла субтитров.
        fmt: Формат — "vtt" или "srt".

    Returns:
        Чистый текст без временных меток, тегов и дублей.
    """
    lines = content.splitlines()
    text_lines: list[str] = []
    in_header = fmt == "vtt"  # VTT начинается с WEBVTT-заголовка

    # Паттерны для определения служебных строк
    _timestamp_vtt = re.compile(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}")
    _timestamp_srt = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}")
    _index_srt = re.compile(r"^\d+$")
    _html_tag = re.compile(r"<[^>]+>")
    _vtt_cue_settings = re.compile(r"^\d{2}:\d{2}.*-->.*(line|align|position|size):")

    for line in lines:
        stripped = line.strip()

        # Пропускаем VTT заголовок
        if in_header:
            if stripped == "" and text_lines == []:
                in_header = False
            elif stripped.startswith("WEBVTT"):
                continue
            elif stripped.startswith("NOTE") or stripped.startswith("STYLE"):
                continue
            continue

        # Пропускаем временные метки
        if _timestamp_vtt.match(stripped) or _timestamp_srt.match(stripped):
            continue
        if _vtt_cue_settings.match(stripped):
            continue

        # Пропускаем порядковые номера блоков SRT
        if fmt == "srt" and _index_srt.match(stripped):
            continue

        # Убираем HTML-теги (<i>, <b>, <c.cyan> и т.п.)
        clean = _html_tag.sub("", stripped)

        # Убираем специфичные VTT теги типа <00:00:01.000>
        clean = re.sub(r"<\d+:\d+:\d+\.\d+>", "", clean)
        clean = clean.strip()

        if not clean:
            continue

        # Убираем дублирующиеся последовательные строки
        if text_lines and text_lines[-1] == clean:
            continue

        text_lines.append(clean)

    return "\n".join(text_lines)
