"""Synchronous notifications; state belongs to the publisher, never a subscriber."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event: str, callback: Callable[..., Any]) -> None:
        with self._lock:
            self._subscribers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., Any]) -> None:
        with self._lock:
            try:
                self._subscribers[event].remove(callback)
            except ValueError:
                pass

    def publish(self, event: str, **kwargs: Any) -> None:
        with self._lock:
            callbacks = tuple(self._subscribers.get(event, ()))
        for callback in callbacks:
            try:
                callback(**kwargs)
            except Exception:
                # Neither arbitrary event names, payloads nor exception chains are diagnostic data.
                task_id = kwargs.get("task_id")
                safe_id = task_id if type(task_id) is int and task_id > 0 else None
                logger.error("event.handler.failed id=%s reason_code=SUBSCRIBER_FAILED", safe_id)
