from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_history_entry_title(entry: Any) -> str:
    return entry.playlist_title or entry.title or entry.url[:80]


def resolve_history_entry_folder(entry: Any) -> Path | None:
    if entry.output_dir:
        path = Path(entry.output_dir)
        if path.exists():
            return path
    if entry.video_path:
        path = Path(entry.video_path).parent
        if path.exists():
            return path
    if entry.audio_path:
        path = Path(entry.audio_path).parent
        if path.exists():
            return path
    return None


def history_entry_matches_query(entry: Any, query: str) -> bool:
    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return True

    haystacks = [
        entry.playlist_title or "",
        entry.title or "",
        entry.url or "",
    ]
    return any(normalized_query in value.lower() for value in haystacks)