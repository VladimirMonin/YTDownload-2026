"""Backward-compatible MCP utility serializers.

Historically MCP tools imported ``entry_to_dict_short`` / ``entry_to_dict_full``
from this module. The shared query refactor moved the canonical transport logic
into ``src.application.history_queries`` and briefly replaced these callables with
broken re-exports to non-existent names.

Keep this shim importable and preserve the legacy dict shape so older call sites
and approval/review flows can still import the helpers directly while the new
CLI/MCP stack reuses transport-neutral DTOs elsewhere.
"""

from __future__ import annotations

from typing import Any


def _ev(value: Any) -> Any:
    """Normalize enum-like values while tolerating plain scalars."""
    return value.value if hasattr(value, "value") else value


def _fmt_dt(value: Any) -> str | None:
    """Format datetime-like values into the legacy ISO/string transport shape."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def entry_to_dict_short(entry: Any) -> dict[str, Any]:
    """Legacy short serializer retained for compatibility.

    Returns the historical MCP/list/query payload shape without file paths.
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
        "created_at": _fmt_dt(getattr(entry, "created_at", None)),
        "finished_at": _fmt_dt(getattr(entry, "finished_at", None)),
        "error_message": entry.error_message or "",
    }


def entry_to_dict_full(entry: Any) -> dict[str, Any]:
    """Legacy full serializer retained for compatibility.

    Extends ``entry_to_dict_short`` with historical file-path fields.
    """

    payload = entry_to_dict_short(entry)
    payload.update(
        {
            "video_path": str(entry.video_path) if entry.video_path else None,
            "audio_path": str(entry.audio_path) if entry.audio_path else None,
            "subtitle_paths": [str(path) for path in (entry.subtitle_paths or [])],
            "description_path": str(entry.description_path) if entry.description_path else None,
            "thumbnail_path": str(entry.thumbnail_path) if entry.thumbnail_path else None,
            "info_json_path": str(entry.info_json_path) if entry.info_json_path else None,
            "output_dir": str(entry.output_dir) if entry.output_dir else None,
        }
    )
    return payload


__all__ = ["entry_to_dict_full", "entry_to_dict_short"]
