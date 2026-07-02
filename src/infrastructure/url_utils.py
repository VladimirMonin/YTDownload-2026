"""Утилиты для разбора и нормализации YouTube URL.

Функции:
    parse_youtube_url(url: str) -> tuple[str, bool]
        Определяет тип ссылки и возвращает очищенный URL + флаг плейлиста.
    is_valid_youtube_url(url: str) -> bool
        Проверяет, похоже ли на ссылку YouTube.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Домены, которые считаем YouTube
_YOUTUBE_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}

# Паттерн для "любого допустимого http(s) URL"
_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)

# Паттерн для YouTube-подобного URL
_YOUTUBE_PATTERN = re.compile(
    r"^https?://(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com|music\.youtube\.com)/",
    re.IGNORECASE,
)


def is_valid_youtube_url(url: str) -> bool:
    """Проверяет, является ли строка валидным YouTube URL.

    Args:
        url: Строка для проверки.

    Returns:
        True если URL начинается с http(s) и содержит YouTube домен.
    """
    if not _URL_PATTERN.match(url):
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return host in _YOUTUBE_DOMAINS
    except Exception:
        return False


def parse_youtube_url(url: str) -> tuple[str, bool]:
    """Определяет тип YouTube ссылки и возвращает очищенный URL.

    Логика:
        - ``/playlist?list=XXX`` → явный плейлист (is_playlist=True)
        - ``/watch?v=XXX&list=YYY`` → одно видео, параметр ``list`` вырезается
        - ``/watch?v=XXX`` → одно видео
        - ``youtu.be/XXX?list=YYY`` → одно видео, параметр ``list`` вырезается

    Args:
        url: Оригинальный URL.

    Returns:
        Кортеж (очищенный_url, is_playlist).
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return url, False

    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    qs = parse_qs(parsed.query, keep_blank_values=True)

    # Явный плейлист: /playlist?list=...
    if "/playlist" in path and "list" in qs:
        return url, True

    # Короткая ссылка youtu.be/VIDEO_ID?list=...
    if host == "youtu.be":
        if "list" in qs:
            # Вырезаем list, si и прочие playlist-параметры
            cleaned_qs = {k: v for k, v in qs.items() if k not in ("list", "index", "si")}
            new_query = urlencode(cleaned_qs, doseq=True)
            cleaned = urlunparse(parsed._replace(query=new_query))
            return cleaned, False
        return url, False

    # watch?v=XXX — проверяем наличие &list=
    if "/watch" in path and "v" in qs:
        if "list" in qs:
            # Вырезаем playlist-параметры, оставляем только v (и t, если есть)
            keep_keys = {"v", "t"}
            cleaned_qs = {k: v for k, v in qs.items() if k in keep_keys}
            new_query = urlencode(cleaned_qs, doseq=True)
            cleaned = urlunparse(parsed._replace(query=new_query))
            return cleaned, False
        return url, False

    # Всё остальное — передаём как есть (например, channel URL)
    return url, False
