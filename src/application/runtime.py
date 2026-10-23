"""Explicit application lifetime and owned/borrowed resources, without OS/SDK choices.

The coordinator owns cooperative cancellation and terminal persistence. This owner
closes admission, joins its executor, reports persistence debt and releases resources.
"""

from __future__ import annotations

import logging
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from src.application.api import ApplicationAPI
from src.application.command_api import CommandError, ValidationError
from src.application.download_coordinator import DownloadCoordinator
from src.application.dto import ShutdownResultDTO
from src.core.event_bus import EventBus
from src.domain.download_rules import DownloadRuleError, validate_settings
from src.domain.models import AppSettings
from src.domain.models.download_task import DownloadStatus
from src.domain.protocols import IHistoryRepository, ISettingsRepository
from src.domain.protocols.file_remover import IFileRemover
from src.domain.protocols.runtime_resource import RuntimeResource

logger = logging.getLogger(__name__)


def recover_interrupted(history_repo: IHistoryRepository) -> None:
    """Called only after exclusive writable ownership; no backend/filesystem replay."""
    interrupted = [entry for entry in history_repo.get_all() if not entry.status.is_terminal()]
    if not interrupted:
        return
    recovered_at = datetime.now()
    for entry in interrupted:
        entry.status = DownloadStatus.FAILED
        entry.error_code = "INTERRUPTED"
        entry.error_message = "Execution interrupted by an earlier process exit"
        entry.finished_at = recovered_at
    history_repo.update_many(interrupted)
    logger.info("runtime.recovered count=%d reason_code=INTERRUPTED", len(interrupted))


class ApplicationRuntime:
    """Own supplied resources, or borrow a coordinator without closing its owner.

    Dependencies are already constructed. No environment access, server, Qt,
    backend construction or global logging setup occurs here.
    """

    def __init__(
        self, *, data_root: Path, history_repo: IHistoryRepository,
        settings_repo: ISettingsRepository, settings: AppSettings, event_bus: EventBus,
        coordinator: DownloadCoordinator | None = None,
        file_remover: IFileRemover | None = None,
        owns_coordinator: bool = True,
        owned_resources: tuple[RuntimeResource, ...] = (),
    ) -> None:
        if not owns_coordinator and owned_resources:
            raise ValueError("Borrowed runtime cannot own its caller's resources")
        self.data_root = data_root
        self.log_dir = data_root / "logs"
        self.history_repo = history_repo
        self.settings_repo = settings_repo
        self.event_bus = event_bus
        self.coordinator = coordinator
        self.file_remover = file_remover
        self._settings = validate_settings(settings)
        self._owns_coordinator = owns_coordinator
        self._resources = list(owned_resources)
        self._mutex = threading.RLock()
        self._closing = False
        self._closed = False
        self._cleanup_errors: set[str] = set()
        self.api = ApplicationAPI(history_repo, coordinator, self)
        if coordinator is not None and owns_coordinator:
            coordinator.bind_lifecycle(self._mark_closing, self._finish_close)

    @property
    def read_only(self) -> bool:
        return self.coordinator is None

    @property
    def closed(self) -> bool:
        with self._mutex:
            return self._closed

    def require_writable(self) -> None:
        with self._mutex:
            if self._closing:
                raise CommandError("Runtime is closing", code="RUNTIME_CLOSING")
            if self.read_only:
                raise CommandError("A writable owner is required", code="OWNER_REQUIRED")

    def get_settings(self) -> AppSettings:
        if self.coordinator is not None:
            return self.coordinator.get_settings()
        with self._mutex:
            return deepcopy(self._settings)

    def update_settings(self, settings: AppSettings) -> AppSettings:
        try:
            candidate = validate_settings(settings)
        except DownloadRuleError as exc:
            raise ValidationError(str(exc), exc.hint) from None
        with self._mutex:
            self.require_writable()
            self.settings_repo.save(candidate)
            if self.coordinator is not None:
                self.coordinator.update_settings(candidate)
            self._settings = candidate
        return deepcopy(candidate)

    def _mark_closing(self) -> None:
        with self._mutex:
            self._closing = True

    def _finish_close(self) -> None:
        # Called only after owned executor join, or for a resource-free read-only view.
        with self._mutex:
            self._closing = True
            if self._closed:
                return
            while self._resources:
                try:
                    self._resources[-1].close()
                except Exception:
                    self._cleanup_errors.add("INTERNAL_ERROR")
                    logger.error("runtime.close.failed reason_code=INTERNAL_ERROR")
                    return  # Keep earlier resources (in particular the lease) held.
                self._resources.pop()
            self._closed = True

    def close(self, *, cancel: bool = True, wait: bool = True) -> ShutdownResultDTO:
        """Close admission, then drain/join before resource release.

        cancel=True signals active work and cancels queued work through its owner.
        wait=False retains ownership until a later real join. Persistence errors
        remain visible even after resources close. Borrowed wrappers never close
        their caller's coordinator.
        """
        self._mark_closing()
        if self.coordinator is not None and self._owns_coordinator:
            try:
                self.coordinator.close(cancel=cancel, wait=wait)
            except Exception:
                with self._mutex:
                    self._cleanup_errors.add("INTERNAL_ERROR")
                logger.error("runtime.close.failed reason_code=INTERNAL_ERROR")
        else:
            self._finish_close()
        _, pending, persistence = (
            self.coordinator.close_state()
            if self.coordinator is not None and self._owns_coordinator else (True, [], [])
        )
        errors = sorted(self._cleanup_errors)
        if persistence:
            errors.append("PERSISTENCE_FAILED")
        return ShutdownResultDTO(self.closed, pending, persistence, errors)

    def as_services(self) -> dict[str, Any]:
        """Legacy adapters receive aliases to this same facade, not another queue."""
        return {
            "runtime": self, "coordinator": self.coordinator,
            "application_api": self.api, "command_api": self.api,
            "history_repo": self.history_repo, "settings_repo": self.settings_repo,
            "settings": self.get_settings(), "event_bus": self.event_bus,
        }

    def __enter__(self) -> ApplicationRuntime:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        result = self.close(cancel=False, wait=True)
        if exc_type is None and (not result.closed or result.error_codes):
            code = result.error_codes[0] if result.error_codes else "INTERNAL_ERROR"
            raise CommandError("Runtime cleanup failed", code=code)
