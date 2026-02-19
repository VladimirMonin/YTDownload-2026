"""Протокол репозитория истории загрузок."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..models import HistoryEntry


class IHistoryRepository(ABC):
    """Интерфейс репозитория истории загрузок.

    Хранит список HistoryEntry с автоинкрементным ID.
    """

    @abstractmethod
    def next_id(self) -> int:
        """Возвращает следующий доступный ID (автоинкремент).

        Returns:
            Числовой ID для новой записи.
        """

    @abstractmethod
    def add(self, entry: HistoryEntry) -> None:
        """Добавляет запись в историю.

        Args:
            entry: Запись для добавления.
        """

    @abstractmethod
    def update(self, entry: HistoryEntry) -> None:
        """Обновляет существующую запись.

        Args:
            entry: Запись с обновлёнными данными.

        Raises:
            KeyError: Если запись с таким ID не найдена.
        """

    @abstractmethod
    def get_by_id(self, entry_id: int) -> Optional[HistoryEntry]:
        """Возвращает запись по ID.

        Args:
            entry_id: ID записи.

        Returns:
            HistoryEntry или None если не найдена.
        """

    @abstractmethod
    def get_all(self) -> list[HistoryEntry]:
        """Возвращает все записи, новые первыми.

        Returns:
            Список записей.
        """

    @abstractmethod
    def search(self, query: str) -> list[HistoryEntry]:
        """Ищет записи по названию или URL.

        Args:
            query: Строка поиска (нечувствительна к регистру).

        Returns:
            Список подходящих записей.
        """

    @abstractmethod
    def delete(self, entry_id: int) -> None:
        """Удаляет запись по ID.

        Args:
            entry_id: ID записи.
        """
