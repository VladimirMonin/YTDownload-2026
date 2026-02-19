"""Простая шина событий для cross-layer коммуникации.

Классы:
    EventBus
        Синхронный publish-subscribe брокер событий.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventBus:
    """Синхронный publish-subscribe брокер событий.

    Используется для коммуникации между слоями без прямых зависимостей.
    Коллбэки вызываются в потоке publisher — UI должен использовать Signal Bridge.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    def subscribe(self, event: str, callback: Callable[..., Any]) -> None:
        """Подписывается на событие.

        Args:
            event: Имя события.
            callback: Функция-обработчик.
        """
        self._subscribers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., Any]) -> None:
        """Отписывается от события.

        Args:
            event: Имя события.
            callback: Функция-обработчик для удаления.
        """
        if event in self._subscribers:
            try:
                self._subscribers[event].remove(callback)
            except ValueError:
                pass

    def publish(self, event: str, **kwargs: Any) -> None:
        """Публикует событие всем подписчикам.

        Args:
            event: Имя события.
            **kwargs: Данные события.
        """
        for callback in list(self._subscribers.get(event, [])):
            try:
                callback(**kwargs)
            except Exception:
                logger.error("event.handler.failed event=%s", event, exc_info=True)
