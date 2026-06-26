from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class _MappingLikeDTO:
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass(frozen=True, slots=True)
class QueryErrorDTO(_MappingLikeDTO):
    error: str
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class DownloadSummaryDTO(_MappingLikeDTO):
    id: int
    url: str
    title: str
    playlist_title: str
    is_playlist: bool
    status: str | None
    quality: str | None
    download_type: str | None
    created_at: str | None
    finished_at: str | None
    error_message: str
    description_path: str | None = None
    description_text: str | None = None


@dataclass(frozen=True, slots=True)
class DownloadDetailsDTO(DownloadSummaryDTO):
    video_path: str | None = None
    audio_path: str | None = None
    subtitle_paths: list[str] | None = None
    thumbnail_path: str | None = None
    info_json_path: str | None = None
    output_dir: str | None = None


@dataclass(frozen=True, slots=True)
class DescriptionResultDTO(_MappingLikeDTO):
    id: int
    title: str
    description_path: str | None
    description_text: str | None
    truncated: bool
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class TranscriptResultDTO(_MappingLikeDTO):
    id: int
    title: str
    transcript_path: str | None
    transcript_text: str | None
    lang_detected: str | None
    format: str | None
    truncated: bool
    available_langs: list[str]
    hint: str | None = None


QueryResultDTO = DownloadDetailsDTO | DescriptionResultDTO | TranscriptResultDTO | QueryErrorDTO


def serialize_for_transport(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        payload = asdict(value)
        return {key: serialize_for_transport(item) for key, item in payload.items()}
    if isinstance(value, list):
        return [serialize_for_transport(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_for_transport(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_for_transport(item) for key, item in value.items()}
    return normalize_scalar(value)


def normalize_scalar(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return value
