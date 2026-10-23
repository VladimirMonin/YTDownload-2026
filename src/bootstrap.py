"""Composition only: explicit paths, lazy defaults, and one writable store owner."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from contextlib import ExitStack, nullcontext
from pathlib import Path

from src.application.command_api import ValidationError
from src.application.download_coordinator import DownloadCoordinator
from src.application.runtime import ApplicationRuntime, recover_interrupted
from src.core.event_bus import EventBus
from src.domain.download_rules import DownloadRuleError, validate_settings
from src.domain.models import AppSettings
from src.domain.protocols.download_service import IDownloadService
from src.domain.protocols.file_remover import IFileRemover
from src.domain.protocols.runtime_resource import RuntimeResource
from src.infrastructure.repositories import JsonHistoryRepository, JsonSettingsRepository
from src.infrastructure.runtime_lock import RuntimeLease

logger = logging.getLogger(__name__)


def create_runtime(
    data_root: Path | None = None, *, read_only: bool = False,
    settings_overrides: Mapping[str, object] | None = None,
    backend_factory: Callable[[], IDownloadService] | None = None,
    file_remover_factory: Callable[[], IFileRemover] | None = None,
    ffmpeg_path: Path | None = None,
) -> ApplicationRuntime:
    """Construct an independent runtime without Qt/transport SDK or import effects.

    Root: explicit -> YTDL_DATA_DIR -> APPDATA/YTDownloader (home fallback).
    Factories own partial acquisition failures internally. Borrowed ready resources
    can instead be supplied directly to ApplicationRuntime with owns_coordinator=False.
    Settings overrides are effective for this runtime, not silently persisted.
    read_only ignores effect factories and never creates storage/executor/lease.
    """
    selected = data_root if data_root is not None else os.environ.get("YTDL_DATA_DIR") or None
    root = (
        Path(selected) if selected is not None
        else Path(os.environ.get("APPDATA") or Path.home()) / "YTDownloader"
    ).expanduser().resolve()
    with ExitStack() as cleanup:
        lease = None
        resources: list[RuntimeResource] = []
        if not read_only:
            lease = RuntimeLease.acquire(root)
            cleanup.callback(lease.close)
            resources.append(lease)
            for directory in (root / "config", root / "data", root / "logs"):
                directory.mkdir(parents=True, exist_ok=True)
        guard = lease.mutation if lease is not None else nullcontext
        history = JsonHistoryRepository(root / "data", read_only=read_only, write_guard=guard)
        settings_repo = JsonSettingsRepository(
            root / "config", read_only=read_only, write_guard=guard
        )
        settings = settings_repo.load()
        if settings_overrides is not None:
            data = settings.to_dict()
            if set(settings_overrides) - data.keys():
                raise ValidationError("Unknown settings override")
            data.update(settings_overrides)
            try:
                settings = validate_settings(AppSettings.from_dict(data))
            except (DownloadRuleError, TypeError, ValueError):
                raise ValidationError("Invalid settings override") from None
        event_bus = EventBus()
        coordinator = None
        remover = None
        if not read_only:
            recover_interrupted(history)
            if file_remover_factory is None:
                from src.infrastructure.file_remover import QtFileRemover

                file_remover_factory = QtFileRemover
            remover = file_remover_factory()
            cleanup.callback(remover.close)
            resources.append(remover)
            # Neither discovery nor default backend SDK is imported for read-only snapshots.
            from src.infrastructure.ffmpeg import find_ffmpeg

            ffmpeg_path = ffmpeg_path if ffmpeg_path is not None else find_ffmpeg()
            if backend_factory is None:
                def default_backend() -> IDownloadService:
                    from src.infrastructure.ytdlp_service import YtDlpService

                    return YtDlpService(ffmpeg_path=ffmpeg_path)

                backend_factory = default_backend
            coordinator = DownloadCoordinator(
                history, settings, event_bus, ffmpeg_path=ffmpeg_path,
                service_factory=backend_factory,
            )
            cleanup.callback(coordinator.close, cancel=False, wait=True)
        runtime = ApplicationRuntime(
            data_root=root, history_repo=history, settings_repo=settings_repo,
            settings=settings, event_bus=event_bus, coordinator=coordinator,
            file_remover=remover, owned_resources=tuple(resources),
        )
        cleanup.pop_all()  # Ownership transferred, not a GC/__del__ cleanup policy.
        logger.info("runtime.created read_only=%s", read_only)
        return runtime
