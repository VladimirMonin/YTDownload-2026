"""Общие утилиты для MCP инструментов.

Функции:
    entry_to_dict_short: Краткое представление HistoryEntry для списков.
    entry_to_dict_full: Полное представление HistoryEntry с путями к файлам.
"""

from __future__ import annotations

from typing import Any


def _ev(v: Any) -> Any:
    """Безопасно извлекает .value из enum или возвращает строку.

    Нужно потому что PySide6 QVariant иногда стрипает str-enum в plain str.
    Готово к будущей миграции на SQLite/PeeWee (там тоже нужна нормализация).

    Args:
        v: Значение (enum или строка).

    Returns:
        .value если enum, иначе str(v).
    """
    return v.value if hasattr(v, "value") else str(v) if v is not None else None


def _fmt_dt(dt: Any) -> str | None:
    """Форматирует datetime в ISO-строку или None."""
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def entry_to_dict_short(entry: Any) -> dict:
    """Краткое представление HistoryEntry для списков и поиска.

    Содержит только мета-данные без путей к файлам. Готово к SQLite —
    поля совпадают с тем что будет в таблице downloads.

    Args:
        entry: HistoryEntry.

    Returns:
        Словарь с полями: id, url, title, playlist_title, status,
        quality, download_type, created_at, finished_at.
    """
    return {
        "id": entry.id,
        "url": entry.url,
        "title": entry.title or "",
        "playlist_title": entry.playlist_title or "",
        "is_playlist": bool(entry.playlist_title),
        "status": _ev(entry.status),
        "quality": _ev(entry.quality),
        "download_type": _ev(entry.download_type),
        "created_at": _fmt_dt(entry.created_at),
        "finished_at": _fmt_dt(entry.finished_at),
        "error_message": entry.error_message or "",
    }


def entry_to_dict_full(entry: Any) -> dict:
    """Полное представление HistoryEntry со всеми путями к файлам.

    Args:
        entry: HistoryEntry.

    Returns:
        Словарь с полями entry_to_dict_short + все пути к файлам.
    """
    d = entry_to_dict_short(entry)
    d.update(
        {
            "video_path": str(entry.video_path) if entry.video_path else None,
            "audio_path": str(entry.audio_path) if entry.audio_path else None,
            "subtitle_paths": [str(p) for p in (entry.subtitle_paths or [])],
            "description_path": (str(entry.description_path) if entry.description_path else None),
            "thumbnail_path": str(entry.thumbnail_path) if entry.thumbnail_path else None,
            "info_json_path": str(entry.info_json_path) if entry.info_json_path else None,
            "output_dir": str(entry.output_dir) if entry.output_dir else None,
        }
    )
    return d
