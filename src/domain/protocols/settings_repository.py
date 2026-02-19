"""Протокол репозитория настроек."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import AppSettings


class ISettingsRepository(ABC):
    """Интерфейс репозитория настроек приложения."""

    @abstractmethod
    def load(self) -> AppSettings:
        """Загружает настройки из хранилища.

        Returns:
            Настройки (defaults если файл не найден).
        """

    @abstractmethod
    def save(self, settings: AppSettings) -> None:
        """Сохраняет настройки в хранилище.

        Args:
            settings: Настройки для сохранения.
        """
