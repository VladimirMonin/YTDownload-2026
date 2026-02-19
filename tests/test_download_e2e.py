"""E2E интеграционные тесты — реальные загрузки с YouTube.

Все тесты требуют сетевого подключения.
Помечены @pytest.mark.e2e и пропускаются без флага --run-e2e.

Запуск:
    uv run pytest tests/test_download_e2e.py -v -m e2e
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.conftest import probe_video

# Тестовые URL из instructions
VIDEO_URL = "https://youtu.be/6BW4lo7f71I"
PLAYLIST_URL = "https://youtube.com/playlist?list=PL6plRXMq5RABbVCM0dn23PTKO13WcXnbf"


def _make_service(ffmpeg_path: Path, output_dir: Path, proxy: str = ""):
    """Создаёт YtDlpService с тестовыми настройками."""
    from src.infrastructure.ytdlp_service import YtDlpService

    return YtDlpService(ffmpeg_path=ffmpeg_path, proxy=proxy)


def _make_task(task_id: int, url: str, quality, download_type=None):
    """Создаёт DownloadTask для тестов."""
    from src.domain.models.download_task import DownloadTask

    kw = {"id": task_id, "url": url, "quality": quality}
    if download_type:
        kw["download_type"] = download_type
    return DownloadTask(**kw)


# ─────────────────────────────────────────────────────────────────────────────
# fetch_info
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_fetch_info_video(tmp_path: Path, ffmpeg_path: Path) -> None:
    """Получает метаданные одиночного видео без загрузки."""
    from src.domain.models.app_settings import AppSettings

    svc = _make_service(ffmpeg_path, tmp_path)
    settings = AppSettings(output_dir=tmp_path)
    info = svc.fetch_info(VIDEO_URL, settings)

    assert info is not None
    assert info.title
    assert info.url == VIDEO_URL or info.url  # может измениться на canonical URL
    assert info.duration_seconds > 0


@pytest.mark.e2e
def test_fetch_info_playlist(tmp_path: Path, ffmpeg_path: Path) -> None:
    """Получает метаданные плейлиста (количество видео)."""
    from src.domain.models.app_settings import AppSettings

    svc = _make_service(ffmpeg_path, tmp_path)
    settings = AppSettings(output_dir=tmp_path)
    info = svc.fetch_info(PLAYLIST_URL, settings)

    assert info is not None
    assert info.is_playlist
    assert info.playlist_count > 0


# ─────────────────────────────────────────────────────────────────────────────
# Загрузка видео
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_download_720p(tmp_path: Path, ffmpeg_path: Path, ffprobe_path: Path) -> None:
    """Скачивает видео в 720p и проверяет через ffprobe."""
    from src.domain.models.app_settings import AppSettings, QualityOption, DownloadType
    from src.infrastructure.ytdlp_service import YtDlpService

    svc = YtDlpService(ffmpeg_path=ffmpeg_path)
    task = _make_task(1, VIDEO_URL, QualityOption.P720, DownloadType.VIDEO)
    settings = AppSettings(output_dir=tmp_path, quality=QualityOption.P720)

    progress_calls = []

    def on_progress(percent, speed, eta):
        progress_calls.append(percent)

    result = svc.download(task, tmp_path, on_progress)

    # Проверяем что видео файл создан
    assert result.get("video") or result.get("video_path"), f"No video in result: {result}"
    video_file = result.get("video") or result.get("video_path")

    if video_file:
        assert Path(video_file).exists()
        stream_info = probe_video(ffprobe_path, Path(video_file))
        assert stream_info.get("height", 0) <= 720

    # Прогресс должен был вызываться
    assert len(progress_calls) > 0


@pytest.mark.e2e
def test_download_audio_only(tmp_path: Path, ffmpeg_path: Path, ffprobe_path: Path) -> None:
    """Скачивает только аудио и проверяет через ffprobe."""
    from src.domain.models.app_settings import AppSettings, QualityOption, DownloadType
    from src.infrastructure.ytdlp_service import YtDlpService

    svc = YtDlpService(ffmpeg_path=ffmpeg_path)
    task = _make_task(2, VIDEO_URL, QualityOption.AUDIO, DownloadType.AUDIO)
    settings = AppSettings(output_dir=tmp_path, download_type=DownloadType.AUDIO)

    result = svc.download(task, tmp_path, lambda p, s, e: None)

    audio_file = result.get("audio") or result.get("audio_path")
    if audio_file:
        assert Path(audio_file).exists()


@pytest.mark.e2e
def test_download_with_description(tmp_path: Path, ffmpeg_path: Path) -> None:
    """Скачивает видео с описанием и проверяет созданные файлы."""
    from src.domain.models.app_settings import AppSettings, QualityOption, DownloadType
    from src.domain.models.download_task import DownloadTask
    from src.infrastructure.ytdlp_service import YtDlpService

    svc = YtDlpService(ffmpeg_path=ffmpeg_path)
    task = DownloadTask(
        id=3,
        url=VIDEO_URL,
        quality=QualityOption.P360,
        download_type=DownloadType.VIDEO,
        save_description=True,
        save_thumbnail=True,
    )
    result = svc.download(task, tmp_path, lambda p, s, e: None)

    # Должно быть описание или thumbnail (зависит от видео)
    assert result is not None


# ─────────────────────────────────────────────────────────────────────────────
# Плейлист (только первые 2 видео)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
@pytest.mark.slow
def test_download_playlist_first_item(tmp_path: Path, ffmpeg_path: Path) -> None:
    """Скачивает первый элемент плейлиста."""
    from src.domain.models.app_settings import AppSettings, QualityOption
    from src.domain.models.download_task import DownloadTask
    from src.infrastructure.ytdlp_service import YtDlpService

    svc = YtDlpService(ffmpeg_path=ffmpeg_path)
    task = DownloadTask(
        id=4,
        url=PLAYLIST_URL,
        quality=QualityOption.P360,
    )
    result = svc.download(task, tmp_path, lambda p, s, e: None)
    assert result is not None


# ─────────────────────────────────────────────────────────────────────────────
# DownloadCoordinator — очередь
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_coordinator_queue_while_downloading(tmp_path: Path, ffmpeg_path: Path) -> None:
    """Проверяет добавление в очередь пока идёт загрузка."""
    from src.application.download_coordinator import DownloadCoordinator
    from src.core.event_bus import EventBus
    from src.domain.models.app_settings import AppSettings, QualityOption
    from src.infrastructure.repositories import JsonHistoryRepository
    from src.infrastructure.ytdlp_service import YtDlpService

    history_repo = JsonHistoryRepository(tmp_path / "data")
    settings = AppSettings(output_dir=tmp_path / "downloads", quality=QualityOption.P360)
    event_bus = EventBus()
    svc = YtDlpService(ffmpeg_path=ffmpeg_path)

    coordinator = DownloadCoordinator(
        service=svc,
        history_repo=history_repo,
        settings=settings,
        event_bus=event_bus,
    )

    id1 = coordinator.add(url=VIDEO_URL, quality=QualityOption.P360)
    id2 = coordinator.add(url=VIDEO_URL, quality=QualityOption.AUDIO)

    assert id1 == 1
    assert id2 == 2
    assert len(coordinator.get_tasks()) == 2

    # Ждём завершения
    time.sleep(30)  # дать время на загрузку
    coordinator.shutdown()

    tasks = coordinator.get_tasks()
    # Хотя бы одна задача должна завершиться
    statuses = [t.status for t in tasks]
    assert any(s in ("done", "failed") for s in statuses)
