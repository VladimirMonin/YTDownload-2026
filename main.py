"""DI Container — создание и связывание всех сервисов приложения.

Функции:
    initialize_app: Создаёт сервисы и возвращает словарь зависимостей.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.application.api import build_application_api
from src.application.download_coordinator import DownloadCoordinator
from src.core.event_bus import EventBus
from src.infrastructure.ffmpeg import find_ffmpeg
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

    # FFmpeg: explicit env path → bundled vendor binary → system PATH.
    # This keeps Windows vendor builds working and lets Linux dev runs use
    # the distro-provided ffmpeg package.
    ffmpeg_path = find_ffmpeg()

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

    logger.info("di.initialized ok=True")

    application_api = build_application_api(
        {
            "coordinator": coordinator,
            "history_repo": history_repo,
        }
    )

    return {
        "coordinator": coordinator,
        "application_api": application_api,
        "command_api": application_api,
        "history_repo": history_repo,
        "settings_repo": settings_repo,
        "settings": settings,
        "event_bus": event_bus,
    }
