"""DI Container — создание и связывание всех сервисов приложения.

Функции:
    initialize_app: Создаёт сервисы и возвращает словарь зависимостей.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.application.download_coordinator import DownloadCoordinator
from src.core.event_bus import EventBus
from src.infrastructure.repositories import (
    JsonHistoryRepository,
    JsonSettingsRepository,
)

logger = logging.getLogger(__name__)


def initialize_app() -> dict:
    """Создаёт все сервисы и возвращает dict зависимостей.

    Используется как DI Container — все зависимости разрешаются здесь
    и передаются в MainWindow и другие потребители.

    Returns:
        Словарь: coordinator, history_repo, settings_repo, settings, event_bus.
    """
    # Пути хранения данных
    app_data = Path(os.getenv("APPDATA", Path.home())) / "YTDownloader"
    config_dir = app_data / "config"
    data_dir = app_data / "data"
    logs_dir = app_data / "logs"
    for d in (config_dir, data_dir, logs_dir):
        d.mkdir(parents=True, exist_ok=True)

    # FFmpeg (vendor поставка)
    _ffmpeg_env = os.getenv("YTDL_FFMPEG_PATH", "")
    ffmpeg_path = (
        Path(_ffmpeg_env)
        if _ffmpeg_env
        else Path(__file__).parent / "vendor" / "ffmpeg" / "bin" / "ffmpeg.exe"
    )

    # Репозитории (JSON)
    settings_repo = JsonSettingsRepository(config_dir)
    history_repo = JsonHistoryRepository(data_dir)

    # Настройки (загружаем или defaults)
    settings = settings_repo.load()

    # EventBus
    event_bus = EventBus()

    # Координатор (оркестрация загрузок)
    coordinator = DownloadCoordinator(
        history_repo=history_repo,
        settings=settings,
        event_bus=event_bus,
        ffmpeg_path=ffmpeg_path,
    )

    logger.info("di.initialized data_dir=%s", data_dir)

    return {
        "coordinator": coordinator,
        "history_repo": history_repo,
        "settings_repo": settings_repo,
        "settings": settings,
        "event_bus": event_bus,
    }
