"""Single pure normalization owner shared by local and transport callers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

from src.domain.models.app_settings import AppSettings, DownloadType, QualityOption


class DownloadRuleError(ValueError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


def normalize_url(url: str) -> str:
    if not isinstance(url, str):
        raise DownloadRuleError("Invalid URL", "Use an http or https URL with a host")
    result = url.strip()
    try:
        parsed = urlsplit(result)
        valid = parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except ValueError:
        valid = False
    if not valid:
        raise DownloadRuleError("Invalid URL", "Use an http or https URL with a host")
    return result


def normalize_options(
    quality: str | QualityOption | None,
    download_type: str | DownloadType | None,
) -> tuple[QualityOption | None, DownloadType | None]:
    """None defers to admission settings, unlike explicit False/empty input."""
    try:
        q = quality.value if isinstance(quality, QualityOption) else quality
        t = download_type.value if isinstance(download_type, DownloadType) else download_type
        q = q.strip().lower() if q is not None else None
        t = t.strip().lower() if t is not None else None
        if q == "audio":
            q, t = "best", "audio"
        return (
            QualityOption(q) if q is not None else None,
            DownloadType(t) if t is not None else None,
        )
    except (ValueError, AttributeError):
        raise DownloadRuleError(
            "Invalid download options", "Use a supported quality and video/audio type"
        ) from None


def validate_download_id(value: int) -> int:
    if type(value) is not int or value <= 0:
        raise DownloadRuleError("Invalid download id", "Use a positive integer id")
    return value


def validate_optional_flag(value: bool | None) -> bool | None:
    if value is not None and type(value) is not bool:
        raise DownloadRuleError("Invalid save option", "Use true, false, or None for settings")
    return value


def validate_settings(settings: AppSettings) -> AppSettings:
    """Return a validated detached snapshot; never include proxy/content in errors."""
    candidate = deepcopy(settings)
    try:
        if (
            not isinstance(candidate.output_dir, (str, Path))
            or not str(candidate.output_dir).strip()
        ):
            raise ValueError
        candidate.output_dir = Path(candidate.output_dir)
        candidate.quality = QualityOption(candidate.quality)
        candidate.download_type = DownloadType(candidate.download_type)
        if candidate.theme not in ("dark", "light"):
            raise ValueError
        if type(candidate.max_concurrent) is not int or candidate.max_concurrent < 1:
            raise ValueError
        if type(candidate.mcp_port) is not int or not 1 <= candidate.mcp_port <= 65535:
            raise ValueError
        if not isinstance(candidate.proxy, str):
            raise ValueError
        if not isinstance(candidate.subtitle_lang, str) or not candidate.subtitle_lang.strip():
            raise ValueError
        for flag in (
            candidate.save_subtitles, candidate.save_description, candidate.save_thumbnail
        ):
            if type(flag) is not bool:
                raise ValueError
    except (TypeError, ValueError):
        raise DownloadRuleError(
            "Invalid settings", "Check output, enums, flags, limits and port"
        ) from None
    return candidate
