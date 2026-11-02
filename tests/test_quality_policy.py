"""Shared quality policy: real enums/settings and the installed yt-dlp selector.

Synthetic format tables are selection fixtures, never live/source-availability proof.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yt_dlp
from yt_dlp.utils import ExtractorError

from src.bootstrap import create_runtime
from src.domain.download_rules import DownloadRuleError, normalize_options
from src.domain.models.app_settings import DownloadType, QualityOption
from src.domain.models.download_task import DownloadTask
from src.infrastructure.ytdlp_service import _build_format_string


def _format(ident: str, height: int | None, *, ext: str, audio: bool = False) -> dict:
    return {
        "format_id": ident,
        "url": f"http://127.0.0.1:9/owned-{ident}.{ext}",
        "ext": ext,
        "height": height,
        "width": height * 16 // 9 if height is not None else None,
        "vcodec": "none" if audio else "vp9" if ext == "webm" else "avc1.640028",
        "acodec": "mp4a.40.2" if audio else "none",
        "abr": 128 if audio else 0,
        "tbr": 128 if audio else height or 100,
    }


def _selected(quality: str, formats: list[dict], *, audio: bool = False) -> dict:
    task = DownloadTask(
        id=1,
        url="http://127.0.0.1:9/owned",
        quality=QualityOption(quality),
        download_type=DownloadType.AUDIO if audio else DownloadType.VIDEO,
    )
    # process_ie_result performs the real SDK sorting/format selection, no HTTP request.
    with yt_dlp.YoutubeDL(
        {
            "quiet": True,
            "no_warnings": True,
            "cachedir": False,
            "format": _build_format_string(task),
        }
    ) as downloader:
        return downloader.process_ie_result(
            {
                "id": "owned",
                "title": "Synthetic formats",
                "formats": formats,
                "extractor": "owned",
                "extractor_key": "Owned",
            },
            download=False,
        )


@pytest.mark.parametrize("quality", ["1440p", "2160p"])
def test_higher_quality_domain_admission_and_real_settings_reopen(tmp_path: Path, quality: str):
    selected, download_type = normalize_options(quality, "video")
    assert selected is QualityOption(quality) and download_type is DownloadType.VIDEO
    with create_runtime(tmp_path / "profile") as runtime:
        settings = runtime.api.get_settings()
        settings.quality = selected
        saved = runtime.api.update_settings(settings)
        assert saved.quality.value == quality
    with create_runtime(tmp_path / "profile", read_only=True) as reopened:
        assert reopened.api.get_settings().quality.value == quality


@pytest.mark.parametrize("height", [360, 480, 720, 1080, 1440, 2160])
def test_real_selector_prefers_available_height_over_lower_mp4(height: int):
    formats = [
        _format("lower-mp4", height // 2, ext="mp4"),
        _format("at-cap-webm", height, ext="webm"),
        _format("over-cap-mp4", height * 2, ext="mp4"),
        _format("audio-m4a", None, ext="m4a", audio=True),
    ]
    result = _selected(f"{height}p", formats)
    video, audio = result["requested_formats"]
    assert video["format_id"] == "at-cap-webm" and video["height"] == height
    assert audio["format_id"] == "audio-m4a" and audio["acodec"] != "none"


@pytest.mark.parametrize("height", [1080, 1440, 2160])
def test_real_selector_never_escapes_explicit_cap_through_best_fallback(height: int):
    formats = [_format("too-high-muxed", height * 2, ext="mp4")]
    formats[0]["acodec"] = "mp4a.40.2"
    with pytest.raises(ExtractorError, match="Requested format is not available"):
        _selected(f"{height}p", formats)


@pytest.mark.parametrize("height", [1080, 1440, 2160])
def test_below_cap_and_unknown_height_do_not_claim_exact_requested_height(height: int):
    muxed = _format("below-cap", 720, ext="mp4")
    muxed["acodec"] = "mp4a.40.2"
    result = _selected(f"{height}p", [muxed])
    assert result["height"] == 720 and result["height"] < height
    generic = _format("generic-unknown", None, ext="mp4")
    generic["acodec"] = "mp4a.40.2"
    unknown = _selected(f"{height}p", [generic])
    assert unknown["format_id"] == "generic-unknown" and unknown.get("height") is None


def test_legacy_best_audio_alias_and_invalid_quality_are_preserved():
    best = DownloadTask(id=1, url="http://127.0.0.1:9/owned", quality=QualityOption.BEST)
    assert _build_format_string(best) == (
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
    )
    assert normalize_options("audio", "video") == (QualityOption.BEST, DownloadType.AUDIO)
    formats = [_format("audio-m4a", None, ext="m4a", audio=True)]
    assert _selected("best", formats, audio=True)["format_id"] == "audio-m4a"
    with pytest.raises(DownloadRuleError):
        normalize_options("4320p", "video")
