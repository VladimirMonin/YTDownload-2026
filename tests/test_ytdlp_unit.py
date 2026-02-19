"""Unit тесты для моделей, репозиториев и форматных строк yt-dlp.

Тесты работают БЕЗ сети — все внешние зависимости замоканы.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# AppSettings
# ─────────────────────────────────────────────────────────────────────────────


class TestAppSettings:
    """Тесты сериализации AppSettings."""

    def test_to_dict_roundtrip(self, tmp_path: Path) -> None:
        from src.domain.models.app_settings import AppSettings, QualityOption, DownloadType

        s = AppSettings(
            output_dir=tmp_path,
            quality=QualityOption.P1080,
            download_type=DownloadType.AUDIO,
            proxy="socks5://127.0.0.1:1080",
            save_subtitles=True,
            subtitle_lang="ru",
        )
        restored = AppSettings.from_dict(s.to_dict())
        assert restored.quality == QualityOption.P1080
        assert restored.download_type == DownloadType.AUDIO
        assert restored.proxy == "socks5://127.0.0.1:1080"
        assert restored.subtitle_lang == "ru"

    def test_output_dir_serialized_as_string(self, tmp_path: Path) -> None:
        from src.domain.models.app_settings import AppSettings

        s = AppSettings(output_dir=tmp_path)
        d = s.to_dict()
        assert isinstance(d["output_dir"], str)


# ─────────────────────────────────────────────────────────────────────────────
# HistoryEntry
# ─────────────────────────────────────────────────────────────────────────────


class TestHistoryEntry:
    """Тесты HistoryEntry сериализации."""

    def test_paths_roundtrip(self, tmp_path: Path) -> None:
        from src.domain.models.history_entry import HistoryEntry

        entry = HistoryEntry(
            id=42,
            url="https://youtu.be/test",
            title="Test Video",
            status="done",
            video_path=tmp_path / "video.mp4",
            subtitle_paths=[tmp_path / "ru.vtt", tmp_path / "en.vtt"],
        )
        restored = HistoryEntry.from_dict(entry.to_dict())
        assert restored.id == 42
        assert restored.video_path == tmp_path / "video.mp4"
        assert len(restored.subtitle_paths) == 2

    def test_optional_paths_none(self) -> None:
        from src.domain.models.history_entry import HistoryEntry

        entry = HistoryEntry(id=1, url="https://youtu.be/x", status="queued")
        d = entry.to_dict()
        assert d["video_path"] is None
        restored = HistoryEntry.from_dict(d)
        assert restored.video_path is None


# ─────────────────────────────────────────────────────────────────────────────
# JsonHistoryRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestJsonHistoryRepository:
    """Тесты JSON репозитория истории."""

    def test_next_id_increments(self, tmp_path: Path) -> None:
        from src.infrastructure.repositories import JsonHistoryRepository

        repo = JsonHistoryRepository(tmp_path)
        assert repo.next_id() == 1
        assert repo.next_id() == 2
        assert repo.next_id() == 3

    def test_next_id_persists_across_instances(self, tmp_path: Path) -> None:
        from src.infrastructure.repositories import JsonHistoryRepository

        repo1 = JsonHistoryRepository(tmp_path)
        repo1.next_id()
        repo1.next_id()

        repo2 = JsonHistoryRepository(tmp_path)
        assert repo2.next_id() == 3  # продолжает с 3

    def test_next_id_thread_safe(self, tmp_path: Path) -> None:
        from src.infrastructure.repositories import JsonHistoryRepository

        repo = JsonHistoryRepository(tmp_path)
        results = []

        def get_id():
            results.append(repo.next_id())

        threads = [threading.Thread(target=get_id) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Все ID должны быть уникальными
        assert len(set(results)) == 20

    def test_add_and_get_by_id(self, tmp_path: Path) -> None:
        from src.domain.models.history_entry import HistoryEntry
        from src.infrastructure.repositories import JsonHistoryRepository

        repo = JsonHistoryRepository(tmp_path)
        entry = HistoryEntry(
            id=repo.next_id(),
            url="https://youtu.be/test",
            title="Test",
            status="done",
        )
        repo.add(entry)

        retrieved = repo.get_by_id(entry.id)
        assert retrieved is not None
        assert retrieved.title == "Test"

    def test_search(self, tmp_path: Path) -> None:
        from src.domain.models.history_entry import HistoryEntry
        from src.infrastructure.repositories import JsonHistoryRepository

        repo = JsonHistoryRepository(tmp_path)
        for i, title in enumerate(["Python Tutorial", "Cat Video", "Python Tips"]):
            e = HistoryEntry(
                id=repo.next_id(), url=f"https://youtu.be/{i}", title=title, status="done"
            )
            repo.add(e)

        results = repo.search("python")
        assert len(results) == 2
        assert all("python" in r.title.lower() for r in results)

    def test_update(self, tmp_path: Path) -> None:
        from src.domain.models.history_entry import HistoryEntry
        from src.infrastructure.repositories import JsonHistoryRepository

        repo = JsonHistoryRepository(tmp_path)
        entry = HistoryEntry(id=repo.next_id(), url="https://youtu.be/x", status="queued")
        repo.add(entry)
        entry.status = "done"
        entry.title = "Updated"
        repo.update(entry)

        updated = repo.get_by_id(entry.id)
        assert updated is not None
        assert updated.status == "done"
        assert updated.title == "Updated"


# ─────────────────────────────────────────────────────────────────────────────
# YtDlpService — format strings
# ─────────────────────────────────────────────────────────────────────────────


class TestYtDlpFormatStrings:
    """Тесты форматных строк yt-dlp (без сети)."""

    def test_build_format_best(self) -> None:
        from src.domain.models.app_settings import QualityOption, DownloadType
        from src.domain.models.download_task import DownloadTask
        from src.infrastructure.ytdlp_service import _build_format_string

        task = DownloadTask(id=1, url="https://youtu.be/x", quality=QualityOption.BEST)
        fmt = _build_format_string(task)
        assert "bestvideo" in fmt or "best" in fmt

    def test_build_format_1080p(self) -> None:
        from src.domain.models.app_settings import QualityOption
        from src.domain.models.download_task import DownloadTask
        from src.infrastructure.ytdlp_service import _build_format_string

        task = DownloadTask(id=1, url="https://youtu.be/x", quality=QualityOption.P1080)
        fmt = _build_format_string(task)
        assert "1080" in fmt

    def test_build_format_audio_only(self) -> None:
        from src.domain.models.app_settings import QualityOption, DownloadType
        from src.domain.models.download_task import DownloadTask
        from src.infrastructure.ytdlp_service import _build_format_string

        task = DownloadTask(
            id=1,
            url="https://youtu.be/x",
            quality=QualityOption.AUDIO,
            download_type=DownloadType.AUDIO,
        )
        fmt = _build_format_string(task)
        assert "bestaudio" in fmt


# ─────────────────────────────────────────────────────────────────────────────
# JsonSettingsRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestJsonSettingsRepository:
    """Тесты репозитория настроек."""

    def test_load_defaults_when_missing(self, tmp_path: Path) -> None:
        from src.infrastructure.repositories import JsonSettingsRepository

        repo = JsonSettingsRepository(tmp_path)
        settings = repo.load()
        assert settings is not None

    def test_save_and_load(self, tmp_path: Path) -> None:
        from src.domain.models.app_settings import AppSettings, QualityOption
        from src.infrastructure.repositories import JsonSettingsRepository

        repo = JsonSettingsRepository(tmp_path)
        settings = AppSettings(output_dir=tmp_path, quality=QualityOption.P720)
        repo.save(settings)

        loaded = repo.load()
        assert loaded.quality == QualityOption.P720


# ─────────────────────────────────────────────────────────────────────────────
# DownloadStatus
# ─────────────────────────────────────────────────────────────────────────────


class TestDownloadStatus:
    """Тесты методов DownloadStatus."""

    def test_is_terminal(self) -> None:
        from src.domain.models.download_task import DownloadStatus

        assert DownloadStatus.DONE.is_terminal()
        assert DownloadStatus.FAILED.is_terminal()
        assert DownloadStatus.CANCELLED.is_terminal()
        assert not DownloadStatus.QUEUED.is_terminal()
        assert not DownloadStatus.DOWNLOADING.is_terminal()

    def test_is_active(self) -> None:
        from src.domain.models.download_task import DownloadStatus

        assert DownloadStatus.DOWNLOADING.is_active()
        assert DownloadStatus.MERGING.is_active()
        # QUEUED is not "actively downloading" — it's waiting in queue
        assert not DownloadStatus.QUEUED.is_active()
        assert not DownloadStatus.DONE.is_active()
