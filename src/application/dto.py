from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, overload

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

# Covariant container interfaces describe JSON results; actual containers below
# remain ordinary dict/list, including the legacy MCP list wrapper.
type JSONValue = str | int | float | bool | None | Sequence[JSONValue] | Mapping[str, JSONValue]
type JSONObject = dict[str, JSONValue]


class _MappingLikeDTO:
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass(frozen=True, slots=True)
class QueryErrorDTO(_MappingLikeDTO):
    error: str
    hint: str | None = None
    code: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteFileDTO(_MappingLikeDTO):
    path: str
    status: str
    code: str | None = None


@dataclass(frozen=True, slots=True)
class ShutdownResultDTO(_MappingLikeDTO):
    closed: bool
    pending_task_ids: list[int] = field(default_factory=list)
    persistence_error_ids: list[int] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)


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
    cancel_requested: bool | None = None
    result_persisted: bool | None = None
    error_code: str | None = None
    artifact_paths: list[str] | None = None


@dataclass(frozen=True, slots=True)
class TaskSnapshotDTO(_MappingLikeDTO):
    id: int
    url: str
    title: str
    playlist_title: str
    status: str
    progress: float | None
    speed: float | None
    eta_seconds: int | None
    cancel_requested: bool
    result_persisted: bool | None
    artifact_paths: list[str]
    error_code: str | None
    error_message: str


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


@overload
def serialize_for_transport[T: DataclassInstance](
    value: list[T] | tuple[T, ...],
) -> list[JSONObject]: ...


@overload
def serialize_for_transport(value: DataclassInstance | Mapping[str, object]) -> JSONObject: ...


@overload
def serialize_for_transport(value: object) -> JSONValue: ...


def serialize_for_transport(value: object) -> JSONValue:
    if is_dataclass(value) and not isinstance(value, type):
        payload: dict[str, object] = asdict(value)
        # Preserve exact legacy wire shape when neither live nor persisted S3 facts exist.
        # False/[] and all error outcomes remain explicit, never hidden as 'unknown'.
        execution_fields = ("cancel_requested", "result_persisted", "error_code", "artifact_paths")
        if isinstance(value, DownloadSummaryDTO) and all(
            payload[key] is None for key in execution_fields
        ):
            for key in execution_fields:
                payload.pop(key)
        return serialize_for_transport(payload)
    if isinstance(value, (list, tuple)):
        items: Sequence[object] = value
        return [serialize_for_transport(item) for item in items]
    if isinstance(value, Mapping):
        mapping: Mapping[object, object] = value
        result: JSONObject = {}
        for object_key, item in mapping.items():
            if not isinstance(object_key, str):
                raise TypeError("Transport object keys must be strings")
            result[object_key] = serialize_for_transport(item)
        return result
    scalar = normalize_scalar(value)
    if scalar is None or isinstance(scalar, (str, int, float, bool)):
        return scalar
    raise TypeError("Unsupported transport value")


@overload
def normalize_scalar(value: str | Path | datetime | None) -> str | None: ...


@overload
def normalize_scalar(value: object) -> object: ...


def normalize_scalar(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        enum_value: object = value.value
        return enum_value
    if isinstance(value, datetime):
        return value.isoformat()
    return value
