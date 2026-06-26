from __future__ import annotations

import re
from pathlib import Path

from src.application.dto import (
    DescriptionResultDTO,
    DownloadDetailsDTO,
    DownloadSummaryDTO,
    QueryErrorDTO,
    TranscriptResultDTO,
    normalize_scalar,
)
from src.domain.models import HistoryEntry
from src.domain.protocols import IHistoryRepository

_MAX_DESCRIPTION_BYTES = 8 * 1024
_MAX_DESCRIPTION_READ_BYTES = 64 * 1024
_MAX_TRANSCRIPT_CHARS = 1_000_000


def _summary_dto(
    entry: HistoryEntry,
    *,
    description_path: str | None = None,
    description_text: str | None = None,
) -> DownloadSummaryDTO:
    return DownloadSummaryDTO(
        id=entry.id,
        url=entry.url,
        title=entry.title or "",
        playlist_title=entry.playlist_title or "",
        is_playlist=bool(entry.playlist_title),
        status=normalize_scalar(entry.status),
        quality=normalize_scalar(entry.quality),
        download_type=normalize_scalar(entry.download_type),
        created_at=normalize_scalar(entry.created_at),
        finished_at=normalize_scalar(entry.finished_at),
        error_message=entry.error_message or "",
        description_path=description_path,
        description_text=description_text,
    )


def _details_dto(entry: HistoryEntry) -> DownloadDetailsDTO:
    summary = _summary_dto(entry)
    return DownloadDetailsDTO(
        id=summary.id,
        url=summary.url,
        title=summary.title,
        playlist_title=summary.playlist_title,
        is_playlist=summary.is_playlist,
        status=summary.status,
        quality=summary.quality,
        download_type=summary.download_type,
        created_at=summary.created_at,
        finished_at=summary.finished_at,
        error_message=summary.error_message,
        description_path=summary.description_path,
        description_text=summary.description_text,
        video_path=str(entry.video_path) if entry.video_path else None,
        audio_path=str(entry.audio_path) if entry.audio_path else None,
        subtitle_paths=[str(path) for path in (entry.subtitle_paths or [])],
        thumbnail_path=str(entry.thumbnail_path) if entry.thumbnail_path else None,
        info_json_path=str(entry.info_json_path) if entry.info_json_path else None,
        output_dir=str(entry.output_dir) if entry.output_dir else None,
    )


def list_downloads(
    history_repo: IHistoryRepository,
    status: str | None = None,
    limit: int = 50,
) -> list[DownloadSummaryDTO]:
    bounded_limit = max(1, min(limit, 200))
    entries = history_repo.get_all()
    if status:
        entries = [entry for entry in entries if normalize_scalar(entry.status) == status]
    return [_summary_dto(entry) for entry in entries[:bounded_limit]]


def get_download(
    history_repo: IHistoryRepository,
    download_id: int,
) -> DownloadDetailsDTO | QueryErrorDTO:
    entry = history_repo.get_by_id(download_id)
    if entry is None:
        return QueryErrorDTO(
            error=f"Download #{download_id} not found",
            hint="Use list_downloads() to see valid IDs",
        )
    return _details_dto(entry)


def search_downloads(
    history_repo: IHistoryRepository,
    query: str,
    limit: int = 20,
    *,
    with_description: bool = False,
) -> list[DownloadSummaryDTO]:
    bounded_limit = max(1, min(limit, 30 if with_description else 100))
    entries = history_repo.search(query) if query else history_repo.get_all()
    results: list[DownloadSummaryDTO] = []
    for entry in entries[:bounded_limit]:
        if with_description:
            results.append(
                _summary_dto(
                    entry,
                    description_path=(
                        str(entry.description_path) if entry.description_path else None
                    ),
                    description_text=_load_description_text(
                        entry,
                        max_bytes=_MAX_DESCRIPTION_BYTES,
                    ),
                )
            )
            continue
        results.append(_summary_dto(entry))
    return results


def get_file_paths(
    history_repo: IHistoryRepository,
    download_id: int,
) -> DownloadDetailsDTO | QueryErrorDTO:
    entry = history_repo.get_by_id(download_id)
    if entry is None:
        return QueryErrorDTO(
            error=f"Download #{download_id} not found",
            hint="Use list_downloads() or search_downloads() to find valid IDs",
        )
    return _details_dto(entry)


def read_description(
    history_repo: IHistoryRepository,
    download_id: int,
) -> DescriptionResultDTO | QueryErrorDTO:
    entry = history_repo.get_by_id(download_id)
    if entry is None:
        return QueryErrorDTO(
            error=f"Download #{download_id} not found",
            hint="Use list_downloads() to see valid IDs",
        )

    path = entry.description_path
    if not path or not Path(path).exists():
        return DescriptionResultDTO(
            id=download_id,
            title=entry.playlist_title or entry.title or "",
            description_path=str(path) if path else None,
            description_text=None,
            truncated=False,
            hint=(
                "Description was not saved for this download. "
                "Re-download with save_description=True to get it."
            ),
        )

    raw = Path(path).read_bytes()
    truncated = len(raw) > _MAX_DESCRIPTION_READ_BYTES
    text = raw[:_MAX_DESCRIPTION_READ_BYTES].decode("utf-8", errors="replace").strip()
    return DescriptionResultDTO(
        id=download_id,
        title=entry.playlist_title or entry.title or "",
        description_path=str(path),
        description_text=text or None,
        truncated=truncated,
    )


def get_transcript(
    history_repo: IHistoryRepository,
    download_id: int,
    *,
    lang: str | None = None,
    raw: bool = False,
    timestamps: bool = False,
) -> TranscriptResultDTO | QueryErrorDTO:
    entry = history_repo.get_by_id(download_id)
    if entry is None:
        return QueryErrorDTO(
            error=f"Download #{download_id} not found",
            hint="Use list_downloads() to see valid IDs",
        )

    subtitle_paths = [
        Path(path)
        for path in (entry.subtitle_paths or [])
        if path and Path(path).exists()
    ]
    if not subtitle_paths:
        return TranscriptResultDTO(
            id=download_id,
            title=entry.playlist_title or entry.title or "",
            transcript_path=None,
            transcript_text=None,
            lang_detected=None,
            format=None,
            truncated=False,
            available_langs=[],
            hint=(
                "No subtitle files found for this download. "
                "Re-download with save_subtitles=True to get them."
            ),
        )

    available_langs = [_extract_lang(path) for path in subtitle_paths]
    chosen = _select_subtitle_path(subtitle_paths, lang)
    if isinstance(chosen, QueryErrorDTO):
        chosen = QueryErrorDTO(error=chosen.error, hint=chosen.hint)
        return chosen

    content = chosen.read_text(encoding="utf-8", errors="replace")
    fmt = "srt" if chosen.suffix.lower() == ".srt" else "vtt"
    lang_detected = _extract_lang(chosen)

    if raw:
        text = content
    elif timestamps:
        text = _clean_subtitle_text_with_timestamps(content, fmt)
    else:
        text = _clean_subtitle_text(content, fmt)

    truncated = len(text) > _MAX_TRANSCRIPT_CHARS
    if truncated:
        text = text[:_MAX_TRANSCRIPT_CHARS]

    return TranscriptResultDTO(
        id=download_id,
        title=entry.playlist_title or entry.title or "",
        transcript_path=str(chosen),
        transcript_text=text or None,
        lang_detected=lang_detected,
        format=fmt,
        truncated=truncated,
        available_langs=available_langs,
    )


def _select_subtitle_path(
    subtitle_paths: list[Path],
    lang: str | None,
) -> Path | QueryErrorDTO:
    if not lang:
        return subtitle_paths[0]

    lang_lower = lang.lower().strip()
    for path in subtitle_paths:
        if lang_lower in path.name.lower():
            return path
    return QueryErrorDTO(
        error=f"No subtitle file found for language '{lang}'",
        hint="Use one of the available languages returned by the query",
    )


def _load_description_text(entry: HistoryEntry, *, max_bytes: int) -> str | None:
    try:
        path = entry.description_path
        if path is None or not Path(path).exists():
            return None
        text = Path(path).read_bytes()[:max_bytes].decode("utf-8", errors="replace")
        return text.strip() or None
    except Exception:
        return None


def _extract_lang(path: Path) -> str:
    stem = path.stem
    parts = stem.rsplit(".", 1)
    if len(parts) == 2:
        candidate = parts[1]
        if re.match(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]+)*$", candidate):
            return candidate.lower()
    return "unknown"


def _clean_subtitle_text(content: str, fmt: str) -> str:
    lines = content.splitlines()
    text_lines: list[str] = []
    in_header = fmt == "vtt"

    timestamp_vtt = re.compile(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}")
    timestamp_srt = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}")
    index_srt = re.compile(r"^\d+$")
    html_tag = re.compile(r"<[^>]+>")
    vtt_cue_settings = re.compile(r"^\d{2}:\d{2}.*-->.*(line|align|position|size):")

    for line in lines:
        stripped = line.strip()
        if in_header:
            if stripped == "" and text_lines == []:
                in_header = False
            elif stripped.startswith("WEBVTT"):
                continue
            elif stripped.startswith("NOTE") or stripped.startswith("STYLE"):
                continue
            continue

        if timestamp_vtt.match(stripped) or timestamp_srt.match(stripped):
            continue
        if vtt_cue_settings.match(stripped):
            continue
        if fmt == "srt" and index_srt.match(stripped):
            continue

        clean = html_tag.sub("", stripped)
        clean = re.sub(r"<\d+:\d+:\d+\.\d+>", "", clean).strip()
        if not clean:
            continue
        if text_lines and text_lines[-1] == clean:
            continue
        text_lines.append(clean)

    return "\n".join(text_lines)


def _clean_subtitle_text_with_timestamps(content: str, fmt: str) -> str:
    lines = content.splitlines()
    result: list[str] = []
    in_header = fmt == "vtt"
    current_time: str | None = None
    last_clean: str | None = None

    timestamp_vtt = re.compile(r"^(\d{2}:\d{2}:\d{2})[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}")
    timestamp_srt = re.compile(r"^(\d{2}:\d{2}:\d{2}),\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}")
    index_srt = re.compile(r"^\d+$")
    html_tag = re.compile(r"<[^>]+>")
    vtt_cue_settings = re.compile(r"^\d{2}:\d{2}.*-->.*(line|align|position|size):")

    for line in lines:
        stripped = line.strip()
        if in_header:
            if stripped == "":
                in_header = False
            continue

        match = timestamp_vtt.match(stripped) or timestamp_srt.match(stripped)
        if match:
            current_time = match.group(1)
            continue
        if vtt_cue_settings.match(stripped):
            continue
        if fmt == "srt" and index_srt.match(stripped):
            continue

        clean = html_tag.sub("", stripped)
        clean = re.sub(r"<\d+:\d+:\d+\.\d+>", "", clean).strip()
        if not clean:
            continue
        if last_clean == clean:
            continue

        last_clean = clean
        prefix = f"[{current_time}] " if current_time else ""
        result.append(f"{prefix}{clean}")

    return "\n".join(result)

