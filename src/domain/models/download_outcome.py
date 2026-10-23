"""Backend facts from one attempt; no directory discovery or transport dependencies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DownloadPaths = dict[str, Path | list[Path] | None]


@dataclass(frozen=True)
class DownloadOutcome:
    status: Literal["completed", "cancelled", "failed"]
    video: Path | None = None
    audio: Path | None = None
    subtitles: tuple[Path, ...] = ()
    description: Path | None = None
    thumbnail: Path | None = None
    info_json: Path | None = None
    scan_root: Path | None = None
    artifact_paths: tuple[Path, ...] = ()
    error_code: str | None = None

    def get(self, key: str, default: object = None) -> Path | list[Path] | None:
        """Legacy internal path accessor (not an untyped success outcome)."""
        if key == "subtitles":
            return list(self.subtitles)
        if key in {"video", "audio", "description", "thumbnail", "info_json", "scan_root"}:
            value = getattr(self, key)
            return value if isinstance(value, Path) else None
        return default if isinstance(default, Path) else None

    def __getitem__(self, key: str) -> Path | list[Path] | None:
        return self.get(key)

    @classmethod
    def from_paths(
        cls,
        paths: Mapping[str, object],
        *,
        status: Literal["completed", "cancelled", "failed"] = "completed",
        error_code: str | None = None,
    ) -> DownloadOutcome:
        """Compatibility for existing injected edges; coordinator still validates media."""

        def path(key: str) -> Path | None:
            value = paths.get(key)
            return value if isinstance(value, Path) else None

        subs = paths.get("subtitles")
        subtitles = (
            tuple(p for p in subs if isinstance(p, Path)) if isinstance(subs, (list, tuple)) else ()
        )
        artifacts = paths.get("artifact_paths")
        known = (
            list(p for p in artifacts if isinstance(p, Path))
            if isinstance(artifacts, (list, tuple))
            else []
        )
        known.extend(
            p
            for key in ("video", "audio", "description", "thumbnail", "info_json")
            if (p := path(key)) is not None
        )
        known.extend(subtitles)
        return cls(
            status,
            path("video"),
            path("audio"),
            subtitles,
            path("description"),
            path("thumbnail"),
            path("info_json"),
            path("scan_root"),
            tuple(dict.fromkeys(known)),
            error_code,
        )
