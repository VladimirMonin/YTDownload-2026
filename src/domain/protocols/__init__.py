"""Пакет протоколов доменного слоя."""

from .download_service import IDownloadService
from .history_repository import IHistoryRepository
from .settings_repository import ISettingsRepository

__all__ = [
    "IDownloadService",
    "IHistoryRepository",
    "ISettingsRepository",
]
