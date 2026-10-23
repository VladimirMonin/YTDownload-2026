"""Bounded deletion policy. One existing live mutation owner, deterministic detached plans.

No directory discovery, permanent deletion, rollback or durable plan registry.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.application.command_api import CommandError, DeletePreview, DeleteResult, NotFoundError
from src.application.dto import DeleteFileDTO
from src.domain.models import HistoryEntry
from src.domain.protocols import IHistoryRepository
from src.domain.protocols.file_remover import IFileRemover
from src.domain.protocols.history_repository import StorageError

if TYPE_CHECKING:
    from src.application.download_coordinator import DownloadCoordinator

logger = logging.getLogger(__name__)


def _refuse(code: str) -> CommandError:
    return CommandError(
        "Deletion is not permitted for the current plan", "Repreview before retrying", code=code
    )


def recorded_paths(entry: HistoryEntry) -> tuple[Path, ...]:
    paths = list(entry.artifact_paths)
    paths.extend(
        p
        for p in (
            entry.video_path,
            entry.audio_path,
            entry.description_path,
            entry.thumbnail_path,
            entry.info_json_path,
        )
        if p is not None
    )
    paths.extend(entry.subtitle_paths)
    return tuple(paths)


def _key(path: Path) -> str:
    return os.path.normcase(str(path))


def _stat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        raise _refuse("ARTIFACT_READ_FAILED") from None


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except (OSError, ValueError, RuntimeError):
        raise _refuse("ARTIFACT_READ_FAILED") from None


def _reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _file_id(info: os.stat_result | None) -> tuple[int, ...] | None:
    if info is None:
        return None
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _ancestry(path: Path, *, directory: bool = False) -> tuple[tuple[object, ...], ...]:
    # Inspect the lexical spelling BEFORE resolving '..' or links. No file bodies are read.
    raw = path if path.is_absolute() else Path.cwd() / path
    parts = list(reversed(raw.parents)) + ([raw] if directory else [])
    facts: list[tuple[object, ...]] = []
    for parent in parts:
        info = _stat(parent)
        if info is not None:
            if _reparse(info) or not stat.S_ISDIR(info.st_mode):
                raise _refuse("UNSAFE_FILE_SCOPE")
            # Directory mtime/size change when an agreed child is moved; identity does not.
            facts.append((_key(parent), info.st_dev, info.st_ino, info.st_mode))
        else:
            facts.append((_key(parent), None))
    return tuple(facts)


@dataclass(frozen=True)
class _Candidate:
    path: Path
    identity: tuple[int, ...] | None
    parents: tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class _Plan:
    entry: HistoryEntry
    delete_files: bool
    root: Path | None
    root_facts: tuple[tuple[object, ...], ...]
    version: str
    files: tuple[_Candidate, ...]
    token: str


class DeletionPolicy:
    def __init__(
        self,
        history: IHistoryRepository,
        coordinator: DownloadCoordinator | None,
        remover: IFileRemover | None,
        data_root: Path | None,
        output_root: Path | None,
    ) -> None:
        self.history, self.coordinator, self.remover = history, coordinator, remover
        self.data_root, self.output_root = data_root, output_root

    def _boundary(self) -> AbstractContextManager[object]:
        # Same RLock already serializes admission, terminal history publication and settings.
        # Do not create a second lock which download finalization would not share.
        return self.coordinator._lock if self.coordinator is not None else nullcontext()

    def _entry(self, ident: int) -> tuple[HistoryEntry, str]:
        entry = self.history.get_by_id(ident)
        if entry is None:
            raise NotFoundError(f"Download #{ident} not found")
        payload: dict[str, object] = {"record": entry.to_dict()}
        if self.coordinator is not None:
            task = self.coordinator.get_task(ident)
            if task is not None:
                entry = self.coordinator.project(entry, task)
                payload["live"] = {
                    "entry": entry.to_dict(),
                    "cancel_requested": task.cancel_requested,
                    "result_persisted": task.result_persisted,
                }
        return entry, self._digest(payload)

    @staticmethod
    def _digest(value: object) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _root(self, entry: HistoryEntry) -> Path | None:
        fallback = (
            self.coordinator.get_settings().output_dir
            if self.coordinator is not None
            else self.output_root
        )
        selected = entry.output_root or fallback
        return Path(selected).expanduser() if selected is not None else None

    def _safe_root(self, entry: HistoryEntry) -> tuple[Path, tuple[tuple[object, ...], ...]]:
        root = self._root(entry)
        if root is None:
            raise _refuse("UNSAFE_FILE_SCOPE")
        facts = _ancestry(root, directory=True)
        root = _resolve(root)
        forbidden = [Path(root.anchor), _resolve(Path.home()), Path(__file__).resolve().parents[2]]
        if self.data_root is not None:
            forbidden.append(_resolve(self.data_root))
        if any(target == root or target.is_relative_to(root) for target in forbidden):
            raise _refuse("UNSAFE_FILE_SCOPE")
        return root, facts

    @staticmethod
    def _candidate(path: Path, root: Path) -> _Candidate:
        _ancestry(path)
        lexical_info = _stat(path)
        if lexical_info is not None and _reparse(lexical_info):
            raise _refuse("UNSAFE_FILE_SCOPE")
        canonical = _resolve(path)
        if canonical == root or not canonical.is_relative_to(root):
            raise _refuse("UNSAFE_FILE_SCOPE")
        info = _stat(canonical)
        if info is not None and (not stat.S_ISREG(info.st_mode) or _reparse(info)):
            raise _refuse("UNSAFE_FILE_SCOPE")
        return _Candidate(canonical, _file_id(info), _ancestry(canonical))

    def _plan(self, ident: int, delete_files: bool) -> _Plan:
        entry, version = self._entry(ident)
        selected = self._root(entry)
        root: Path | None = (
            _resolve(selected) if selected is not None and not delete_files else None
        )
        root_facts: tuple[tuple[object, ...], ...] = ()
        candidates: dict[str, _Candidate] = {}
        if delete_files:
            root, root_facts = self._safe_root(entry)
            paths = recorded_paths(entry)
            if not paths:
                raise _refuse("UNSAFE_FILE_SCOPE")
            for path in paths:
                candidate = self._candidate(path, root)
                candidates.setdefault(_key(candidate.path), candidate)
        files = tuple(candidates[key] for key in sorted(candidates))
        token = "delete-v1:" + self._digest(
            {
                "id": ident,
                "delete_files": delete_files,
                "version": version,
                "root": _key(root) if root is not None else None,
                "root_facts": root_facts,
                "files": [(str(c.path), c.identity, c.parents) for c in files],
            }
        )
        return _Plan(entry, delete_files, root, root_facts, version, files, token)

    def _idle(self, plan: _Plan) -> None:
        pending = set(self.coordinator.close_state()[1]) if self.coordinator is not None else set()
        if not plan.entry.status.is_terminal() or plan.entry.id in pending:
            raise _refuse("ACTIVE_DOWNLOAD")
        if not plan.delete_files:
            return
        live = (
            {task.id: task for task in self.coordinator.get_tasks()}
            if self.coordinator is not None
            else {}
        )
        for entry in self.history.get_all():
            task = live.pop(entry.id, None)
            terminal = task.status.is_terminal() if task is not None else entry.status.is_terminal()
            root = (
                (task.output_root or entry.output_root) if task is not None else entry.output_root
            )
            if not terminal or entry.id in pending:
                self._active_area(root, plan.root)
        # A legacy bypass/lost history row does not erase the authoritative live task.
        for task in live.values():
            if not task.status.is_terminal() or task.id in pending:
                self._active_area(task.output_root, plan.root)

    @staticmethod
    def _active_area(root: Path | None, planned_root: Path | None) -> None:
        # A legacy nonterminal has no admission snapshot: current reader defaults are not evidence.
        if root is None or planned_root is None:
            raise _refuse("ACTIVE_DOWNLOAD")
        root = _resolve(root)
        if root.is_relative_to(planned_root) or planned_root.is_relative_to(root):
            raise _refuse("ACTIVE_DOWNLOAD")

    def _unshared(self, plan: _Plan) -> None:
        if not plan.delete_files:
            return
        by_path = {_key(c.path) for c in plan.files}
        by_inode = {(c.identity[0], c.identity[1]) for c in plan.files if c.identity is not None}
        for other in self.history.get_all():
            if other.id == plan.entry.id:
                continue
            if self.coordinator is not None:
                task = self.coordinator.get_task(other.id)
                if task is not None:
                    other = self.coordinator.project(other, task)
            for path in recorded_paths(other):
                canonical = _resolve(path)
                info = _stat(canonical)
                if _key(canonical) in by_path or (
                    info is not None and (info.st_dev, info.st_ino) in by_inode
                ):
                    raise _refuse("UNSAFE_FILE_SCOPE")

    def preview(self, ident: int, delete_files: bool) -> DeletePreview:
        with self._boundary():
            entry, _ = self._entry(ident)
            pending = self.coordinator.close_state()[1] if self.coordinator is not None else []
            if not entry.status.is_terminal() or ident in pending:
                raise _refuse("ACTIVE_DOWNLOAD")
            plan = self._plan(ident, delete_files)
            self._idle(plan)
            self._unshared(plan)
            files = [
                DeleteFileDTO(str(c.path), "planned" if c.identity is not None else "missing")
                for c in plan.files
            ]
            return DeletePreview(
                ident,
                plan.entry.playlist_title or plan.entry.title or plan.entry.url[:80],
                str(plan.entry.output_dir) if plan.entry.output_dir else None,
                len(files),
                delete_files,
                plan.token,
                files,
                sum(c.identity is None for c in plan.files),
                str(plan.root) if plan.root is not None else None,
            )

    def _revalidate(self, plan: _Plan, candidate: _Candidate | None = None) -> None:
        entry, version = self._entry(plan.entry.id)
        if version != plan.version:
            raise _refuse("STALE_PLAN")
        self._idle(plan)
        if plan.delete_files:
            root, facts = self._safe_root(entry)
            if root != plan.root or facts != plan.root_facts:
                raise _refuse("STALE_PLAN")
            self._unshared(plan)
            for path in recorded_paths(entry):
                self._candidate(
                    path, root
                )  # Recheck lexical aliases/ancestry too, without adopting files.
            if candidate is not None and self._candidate(candidate.path, root) != candidate:
                raise _refuse("STALE_PLAN")

    def _failure(self, plan: _Plan, files: list[DeleteFileDTO], code: str) -> CommandError:
        try:
            deleted = self.history.get_by_id(plan.entry.id) is None
        except Exception:
            deleted = None
        error = _refuse(code)
        error.result = {
            "id": plan.entry.id,
            "history_deleted": deleted,
            "files": [{"path": f.path, "status": f.status, "code": f.code} for f in files],
            "moved_count": sum(f.status == "moved" for f in files),
            "missing_count": sum(f.status == "missing" for f in files),
            "failed_count": sum(f.status == "failed" for f in files),
            "unknown_count": sum(f.status == "unknown" for f in files),
            "recovery": "repreview",
        }
        logger.error(
            "deletion.failed id=%d reason_code=%s moved_count=%d",
            plan.entry.id,
            code,
            error.result["moved_count"],
        )
        return error

    def apply(self, ident: int, delete_files: bool, expected_plan: str | None) -> DeleteResult:
        with self._boundary():
            self._entry(ident)  # NOT_FOUND on replay after success, without any file action.
            if not isinstance(expected_plan, str) or not expected_plan:
                raise _refuse("CONFIRMATION_REQUIRED")
            if self.coordinator is None:
                raise _refuse("OWNER_REQUIRED")
            if self.coordinator._closing:
                raise _refuse("RUNTIME_CLOSING")
            try:
                plan = self._plan(ident, delete_files)
            except CommandError as error:
                if error.code in {"UNSAFE_FILE_SCOPE", "ARTIFACT_READ_FAILED"}:
                    raise _refuse("STALE_PLAN") from None
                raise
            if plan.token != expected_plan:
                raise _refuse("STALE_PLAN")
            self._idle(plan)
            self._unshared(plan)
            files = [DeleteFileDTO(str(c.path), "not_attempted") for c in plan.files]
            for index, candidate in enumerate(plan.files):
                try:
                    self._revalidate(plan, candidate)
                except CommandError:
                    files[index] = DeleteFileDTO(str(candidate.path), "failed", "STALE_PLAN")
                    if any(f.status == "moved" for f in files):
                        raise self._failure(plan, files, "PARTIAL_DELETE") from None
                    raise _refuse("STALE_PLAN") from None
                if candidate.identity is None:
                    files[index] = DeleteFileDTO(str(candidate.path), "missing")
                    continue
                try:
                    if self.remover is None:
                        raise _refuse("TRASH_UNAVAILABLE")
                    moved = self.remover.move_to_trash(candidate.path)
                    now = _file_id(_stat(candidate.path))
                    if moved is not True or now == candidate.identity:
                        raise _refuse("TRASH_UNAVAILABLE")
                    files[index] = DeleteFileDTO(str(candidate.path), "moved")
                except Exception:
                    try:
                        state = (
                            "failed"
                            if _file_id(_stat(candidate.path)) == candidate.identity
                            else "unknown"
                        )
                    except CommandError:
                        state = "unknown"
                    files[index] = DeleteFileDTO(str(candidate.path), state, "TRASH_UNAVAILABLE")
                    code = (
                        "PARTIAL_DELETE"
                        if state == "unknown" or any(f.status == "moved" for f in files)
                        else "TRASH_UNAVAILABLE"
                    )
                    raise self._failure(plan, files, code) from None
            try:
                self._revalidate(plan)
            except CommandError:
                raise self._failure(
                    plan,
                    files,
                    "PARTIAL_DELETE" if any(f.status == "moved" for f in files) else "STALE_PLAN",
                ) from None
            try:
                self.history.delete(ident)
                if self.history.get_by_id(ident) is not None:
                    raise StorageError("History deletion unconfirmed", code="PERSISTENCE_FAILED")
            except StorageError:
                raise self._failure(plan, files, "PERSISTENCE_FAILED") from None
            moved_count = sum(f.status == "moved" for f in files)
            missing = sum(f.status == "missing" for f in files)
            logger.info(
                "deletion.completed id=%d moved_count=%d missing_count=%d",
                ident,
                moved_count,
                missing,
            )
            return DeleteResult(ident, True, moved_count > 0, files, moved_count, missing)
