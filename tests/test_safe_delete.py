"""S4 connected policy/real JSON/owned files; only OS Trash is substituted."""

from __future__ import annotations

import io
import json
import logging
import os
import subprocess
from pathlib import Path
from threading import Event

import pytest

from src.application.command_api import CommandError
from src.bootstrap import create_runtime
from src.domain.models import HistoryEntry, VideoInfo
from src.domain.models.download_task import DownloadStatus


class SyntheticTrash:
    def __init__(self, root):
        self.root = root
        self.moves = []

    def move_to_trash(self, path):
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{len(self.moves)}-{path.name}"
        path.rename(target)
        self.moves.append((path, target))
        return True

    def close(self):
        pass


def make_owner(tmp_path, *, backend_factory=None):
    trash = SyntheticTrash(tmp_path / "synthetic-trash")
    runtime = create_runtime(
        tmp_path / "profile",
        settings_overrides={"output_dir": tmp_path / "output"},
        backend_factory=backend_factory,
        file_remover_factory=lambda: trash,
    )
    return runtime, trash


def seed(runtime, tmp_path, ident=1):
    directory = tmp_path / "output" / f"download-{ident}"
    directory.mkdir(parents=True, exist_ok=True)
    video, sidecar = directory / "owned.mp4", directory / "owned.description"
    video.write_bytes(b"distinctive owned media")
    sidecar.write_bytes(b"distinctive owned description")
    runtime.history_repo.add(
        HistoryEntry(
            id=ident,
            url="https://example.invalid/owned",
            title="Owned result",
            status=DownloadStatus.DONE,
            output_root=tmp_path / "output",
            output_dir=directory,
            video_path=video,
            description_path=sidecar,
            artifact_paths=[video, sidecar],
        )
    )
    return video, sidecar


def test_no_token_refuses_record_only_deletion_before_any_effect(tmp_path: Path) -> None:
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        before = (tmp_path / "profile/data/history.json").read_bytes()
        with pytest.raises(CommandError) as denied:
            runtime.api.delete_download(1, delete_files=False)
        assert denied.value.code == "CONFIRMATION_REQUIRED"
        assert (tmp_path / "profile/data/history.json").read_bytes() == before
        assert runtime.history_repo.get_by_id(1) is not None
        assert media.read_bytes() == b"distinctive owned media"
        assert sidecar.read_bytes() == b"distinctive owned description"
        assert trash.moves == []
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def history_bytes(tmp_path):
    return (tmp_path / "profile/data/history.json").read_bytes()


def reopen(tmp_path):
    reader = create_runtime(tmp_path / "profile", read_only=True)
    try:
        return reader.api.list_history_entries()
    finally:
        assert reader.close().closed


def test_exact_known_files_preview_moves_recovery_and_durable_replay(tmp_path):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        parent, root = media.parent, tmp_path / "output"
        unlisted, sibling = parent / "unlisted.keep", root / "sibling.keep"
        unlisted.write_bytes(b"unlisted preserve")
        sibling.write_bytes(b"sibling preserve")
        entry = runtime.history_repo.get_by_id(1)
        assert entry is not None
        audio, subtitle = parent / "audio.mp3", parent / "sub.ru.vtt"
        audio.write_bytes(b"audio owned")
        subtitle.write_bytes(b"subtitle owned")
        entry.audio_path, entry.subtitle_paths = audio, [subtitle]
        entry.artifact_paths += [media, audio, subtitle]
        runtime.history_repo.update(entry)
        before = history_bytes(tmp_path)
        expected = {p: p.read_bytes() for p in [media, sidecar, audio, subtitle]}
        preview = runtime.api.prepare_delete_download(1)
        assert preview.file_count == 4 and preview.missing_count == 0
        assert {Path(f.path) for f in preview.files} == set(expected)
        assert preview == runtime.api.prepare_delete_download(1)
        preview.files.clear()  # DTO is detached; token/effect are not caller-owned mutable policy.
        assert runtime.api.prepare_delete_download(1).file_count == 4
        assert history_bytes(tmp_path) == before
        assert all(p.read_bytes() == value for p, value in expected.items())
        assert trash.moves == []
        result = runtime.api.delete_download(1, expected_plan=preview.plan_token)
        assert result.deleted and result.files_removed and result.moved_count == 4
        assert result.missing_count == 0 and all(f.status == "moved" for f in result.files)
        assert {source: target.read_bytes() for source, target in trash.moves} == expected
        assert all(not source.exists() for source in expected)
        assert parent.is_dir() and root.is_dir()
        assert (
            unlisted.read_bytes() == b"unlisted preserve"
            and sibling.read_bytes() == b"sibling preserve"
        )
        assert runtime.history_repo.get_by_id(1) is None and reopen(tmp_path) == []
        assert json.loads(history_bytes(tmp_path))["entries"] == []
        with pytest.raises(CommandError) as denied:
            runtime.api.delete_download(1, expected_plan=preview.plan_token)
        assert denied.value.code == "NOT_FOUND" and len(trash.moves) == 4
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_keep_files_is_token_bound_durable_record_only_and_preserves_bytes(tmp_path):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        preview = runtime.api.prepare_delete_download(1, delete_files=False)
        assert preview.file_count == 0 and preview.files == []
        result = runtime.api.delete_download(
            1, delete_files=False, expected_plan=preview.plan_token
        )
        assert result.deleted and not result.files_removed and result.moved_count == 0
        assert media.read_bytes() == b"distinctive owned media"
        assert sidecar.read_bytes() == b"distinctive owned description"
        assert trash.moves == [] and reopen(tmp_path) == []
    finally:
        assert runtime.close(cancel=False, wait=True).closed


@pytest.mark.parametrize(
    "dimension",
    [
        "id",
        "mode",
        "root",
        "fallback_root",
        "record",
        "file_set",
        "size",
        "mtime",
        "replacement",
        "token",
    ],
)
def test_every_material_plan_dimension_refuses_stale_without_file_effect(tmp_path, dimension):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        if dimension == "fallback_root":
            legacy = runtime.history_repo.get_by_id(1)
            legacy.output_root = None
            runtime.history_repo.update(legacy)
        preview = runtime.api.prepare_delete_download(1)
        ident, mode, token = 1, True, preview.plan_token
        entry = runtime.history_repo.get_by_id(1)
        assert entry is not None
        if dimension == "id":
            seed(runtime, tmp_path, 2)
            ident = 2
        elif dimension == "mode":
            mode = False
        elif dimension == "root":
            entry.output_root = tmp_path / "other-output"
            runtime.history_repo.update(entry)
        elif dimension == "fallback_root":
            settings = runtime.api.get_settings()
            settings.output_dir = tmp_path / "changed-default-output"
            runtime.api.update_settings(settings)
        elif dimension == "record":
            entry.title = "Updated version"
            runtime.history_repo.update(entry)
        elif dimension == "file_set":
            extra = media.parent / "extra.owned"
            extra.write_bytes(b"additional real file")
            entry.artifact_paths += [extra]
            runtime.history_repo.update(entry)
        elif dimension == "size":
            media.write_bytes(b"new longer modified bytes")
        elif dimension == "mtime":
            info = media.stat()
            os.utime(media, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
        elif dimension == "replacement":
            old = media.with_name("old-preserved.mp4")
            media.rename(old)
            media.write_bytes(old.read_bytes())
            original = old.stat()
            os.utime(media, ns=(original.st_atime_ns, original.st_mtime_ns))
            assert media.stat().st_size == original.st_size
            assert media.stat().st_mtime_ns == original.st_mtime_ns
            assert media.stat().st_ino != original.st_ino
        elif dimension == "token":
            token = "wrong-token"
        before, current = history_bytes(tmp_path), media.read_bytes()
        with pytest.raises(CommandError) as denied:
            runtime.api.delete_download(ident, delete_files=mode, expected_plan=token)
        assert denied.value.code == "STALE_PLAN"
        assert history_bytes(tmp_path) == before and trash.moves == []
        assert (
            media.read_bytes() == current
            and sidecar.read_bytes() == b"distinctive owned description"
        )
    finally:
        assert runtime.close(cancel=False, wait=True).closed


@pytest.mark.parametrize("ident", [True, False, 0, -1, "1", None])
def test_delete_id_validation_before_effect(tmp_path, ident):
    runtime, trash = make_owner(tmp_path)
    try:
        seed(runtime, tmp_path)
        before = history_bytes(tmp_path)
        for operation in (runtime.api.prepare_delete_download, runtime.api.delete_download):
            with pytest.raises(CommandError) as denied:
                operation(ident)
            assert denied.value.code == "INVALID_ARGUMENT"
        assert history_bytes(tmp_path) == before and trash.moves == []
    finally:
        assert runtime.close(cancel=False, wait=True).closed


@pytest.mark.parametrize("mode", [0, 1, "true", None])
def test_delete_mode_must_be_boolean(tmp_path, mode):
    runtime, trash = make_owner(tmp_path)
    try:
        seed(runtime, tmp_path)
        before = history_bytes(tmp_path)
        for operation in (runtime.api.prepare_delete_download, runtime.api.delete_download):
            with pytest.raises(CommandError) as denied:
                operation(1, delete_files=mode)
            assert denied.value.code == "INVALID_ARGUMENT"
        assert history_bytes(tmp_path) == before and trash.moves == []
    finally:
        assert runtime.close(cancel=False, wait=True).closed


@pytest.mark.parametrize(
    "scope",
    [
        "volume",
        "home",
        "data",
        "project",
        "outside",
        "directory",
        "folder_only",
        "shared",
        "shared_alias",
    ],
)
def test_unsafe_root_scope_and_shared_references_preserve_files_and_store(tmp_path, scope):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        entry = runtime.history_repo.get_by_id(1)
        assert entry is not None
        roots = {
            "volume": Path(media.anchor),
            "home": Path.home(),
            "data": runtime.data_root,
            "project": Path.cwd(),
        }
        if scope in roots:
            entry.output_root = roots[scope]
        elif scope == "outside":
            outside = tmp_path / "outside-owned.mp4"
            outside.write_bytes(b"outside preserve")
            entry.artifact_paths.append(outside)
        elif scope == "directory":
            entry.artifact_paths.append(media.parent)
        elif scope == "folder_only":
            entry.artifact_paths, entry.video_path, entry.description_path = [], None, None
        elif scope in {"shared", "shared_alias"}:
            alias = media
            if scope == "shared_alias":
                nested = media.parent / "nested"
                nested.mkdir()
                alias = nested / ".." / media.name
            runtime.history_repo.add(
                HistoryEntry(
                    id=2,
                    url="https://example.invalid/other",
                    title="Other",
                    status=DownloadStatus.DONE,
                    output_root=tmp_path / "output",
                    artifact_paths=[alias],
                )
            )
        runtime.history_repo.update(entry)
        before = history_bytes(tmp_path)
        with pytest.raises(CommandError) as denied:
            runtime.api.prepare_delete_download(1)
        assert denied.value.code == "UNSAFE_FILE_SCOPE"
        assert history_bytes(tmp_path) == before and trash.moves == []
        assert media.read_bytes() == b"distinctive owned media"
        assert sidecar.read_bytes() == b"distinctive owned description"
        # Unsafe file scope does not forbid checked keep-files recovery.
        preview = runtime.api.prepare_delete_download(1, delete_files=False)
        assert runtime.api.delete_download(
            1, delete_files=False, expected_plan=preview.plan_token
        ).deleted
        assert media.exists() and sidecar.exists()
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_real_second_move_failure_retains_first_bytes_record_and_safe_repreview(
    tmp_path, monkeypatch
):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        preview = runtime.api.prepare_delete_download(1)
        before = history_bytes(tmp_path)
        expected = {p: p.read_bytes() for p in (media, sidecar)}
        real_move = trash.move_to_trash

        def move(path):
            if trash.moves:
                raise OSError("PRIVATE_RAW_ERROR_SENTINEL")
            return real_move(path)

        monkeypatch.setattr(trash, "move_to_trash", move)
        with pytest.raises(CommandError) as denied:
            runtime.api.delete_download(1, expected_plan=preview.plan_token)
        assert denied.value.code == "PARTIAL_DELETE"
        result = denied.value.result
        assert result is not None and result["history_deleted"] is False
        assert (result["moved_count"], result["failed_count"], result["unknown_count"]) == (1, 1, 0)
        assert result["recovery"] == "repreview"
        assert [f["status"] for f in result["files"]] == ["moved", "failed"]
        source, saved = trash.moves[0]
        assert saved.read_bytes() == expected[source] and not source.exists()
        second = next(p for p in expected if p != source)
        assert second.read_bytes() == expected[second]
        assert history_bytes(tmp_path) == before and len(reopen(tmp_path)) == 1
        # Original response lost/partial: replacement at the same spelling is a NEW target.
        source.write_bytes(b"new same-name replacement")
        with pytest.raises(CommandError) as stale:
            runtime.api.delete_download(1, expected_plan=preview.plan_token)
        assert stale.value.code == "STALE_PLAN" and len(trash.moves) == 1
        assert source.read_bytes() == b"new same-name replacement"
        replacement = runtime.api.prepare_delete_download(1)
        assert replacement.plan_token != preview.plan_token
        keep = runtime.api.prepare_delete_download(1, delete_files=False)
        assert runtime.api.delete_download(
            1, delete_files=False, expected_plan=keep.plan_token
        ).deleted
        assert (
            second.exists()
            and source.exists()
            and saved.read_bytes() == expected[trash.moves[0][0]]
        )
        assert reopen(tmp_path) == []
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_history_replace_failure_after_real_moves_is_not_deleted_and_reopens(tmp_path, monkeypatch):
    import src.infrastructure.repositories as repositories

    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        preview = runtime.api.prepare_delete_download(1)
        before, entry_before = history_bytes(tmp_path), runtime.history_repo.get_by_id(1)
        expected = {p: p.read_bytes() for p in (media, sidecar)}
        replace = repositories.os.replace

        def fail_owned(source, target):
            if Path(target) == tmp_path / "profile/data/history.json":
                raise OSError("PRIVATE_RAW_REPLACE_SENTINEL")
            return replace(source, target)

        with monkeypatch.context() as patch:
            patch.setattr(repositories.os, "replace", fail_owned)
            with pytest.raises(CommandError) as denied:
                runtime.api.delete_download(1, expected_plan=preview.plan_token)
        assert denied.value.code == "PERSISTENCE_FAILED"
        result = denied.value.result
        assert result is not None and result["history_deleted"] is False
        assert result["moved_count"] == 2 and result["unknown_count"] == 0
        assert all(f["status"] == "moved" for f in result["files"])
        assert {source: target.read_bytes() for source, target in trash.moves} == expected
        assert not media.exists() and not sidecar.exists()
        assert (
            history_bytes(tmp_path) == before and runtime.history_repo.get_by_id(1) == entry_before
        )
        assert reopen(tmp_path) == [entry_before]
        retained = list((tmp_path / "profile/data").glob("*.tmp"))
        assert len(retained) == 1  # Accepted atomic writer retains an uncommitted failed candidate.
        assert json.loads(retained[0].read_text(encoding="utf-8"))["entries"] == []
        retained[0].rename(
            tmp_path / "closed-uncommitted-candidate.tmp"
        )  # Windows handle is closed.
        with pytest.raises(CommandError) as stale:
            runtime.api.delete_download(1, expected_plan=preview.plan_token)
        assert stale.value.code == "STALE_PLAN" and len(trash.moves) == 2
        next_plan = runtime.api.prepare_delete_download(1)
        assert next_plan.file_count == 2 and next_plan.missing_count == 2
        result = runtime.api.delete_download(1, expected_plan=next_plan.plan_token)
        assert result.deleted and not result.files_removed and result.missing_count == 2
        assert len(trash.moves) == 2 and reopen(tmp_path) == []
    finally:
        assert runtime.close(cancel=False, wait=True).closed


@pytest.mark.parametrize("missing", [1, 2])
def test_missing_candidates_and_mixed_aliases_have_honest_deduplicated_counts(tmp_path, missing):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        preserved = tmp_path / "separately-preserved"
        preserved.mkdir()
        media.rename(preserved / media.name)
        if missing == 2:
            sidecar.rename(preserved / sidecar.name)
        entry = runtime.history_repo.get_by_id(1)
        assert entry is not None
        nested = media.parent / "nested"
        nested.mkdir()
        entry.artifact_paths += [nested / ".." / media.name, sidecar]
        runtime.history_repo.update(entry)
        preview = runtime.api.prepare_delete_download(1)
        assert preview.file_count == 2 and preview.missing_count == missing
        result = runtime.api.delete_download(1, expected_plan=preview.plan_token)
        assert (
            result.deleted and result.missing_count == missing and result.moved_count == 2 - missing
        )
        assert result.files_removed is (missing == 1)
        assert len(trash.moves) == 2 - missing
        assert (preserved / media.name).read_bytes() == b"distinctive owned media"
        assert media.parent.is_dir() and nested.is_dir() and reopen(tmp_path) == []
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_saved_nonterminal_readonly_preview_and_unquiesced_live_cancel_refuse(tmp_path):
    entered, release = Event(), Event()

    class Edge:
        def fetch_info(self, url, settings):
            entered.set()
            assert release.wait(8)
            return VideoInfo(title="Blocked result")

        def cancel(self):
            pass

        def download(self, task, settings, progress_callback=None):
            raise AssertionError("cancelled fetch must not proceed to media")

    runtime, trash = make_owner(tmp_path, backend_factory=Edge)
    try:
        media, sidecar = seed(runtime, tmp_path)
        plan = runtime.api.prepare_delete_download(1)
        task = runtime.api.queue_add_download(url="https://example.invalid/active")
        assert entered.wait(4)
        reader = create_runtime(tmp_path / "profile", read_only=True)
        try:
            before = history_bytes(tmp_path)
            with pytest.raises(CommandError) as denied:
                reader.api.prepare_delete_download(task.task_id, delete_files=False)
            assert denied.value.code == "ACTIVE_DOWNLOAD"
            assert history_bytes(tmp_path) == before
        finally:
            assert reader.close().closed
        assert runtime.api.cancel_download(task.task_id).status == "cancel_requested"
        snapshot = runtime.api.get_task(task.task_id)
        assert snapshot.cancel_requested and snapshot.status not in {"cancelled", "done", "failed"}
        before = history_bytes(tmp_path)
        for mode in (False, True):
            with pytest.raises(CommandError) as denied:
                runtime.api.prepare_delete_download(task.task_id, delete_files=mode)
            assert denied.value.code == "ACTIVE_DOWNLOAD"
        with pytest.raises(CommandError) as denied:
            runtime.api.delete_download(1, expected_plan=plan.plan_token)
        assert denied.value.code == "ACTIVE_DOWNLOAD"
        assert history_bytes(tmp_path) == before and trash.moves == []
        assert media.exists() and sidecar.exists()
        release.set()
        terminal = runtime.api.wait_for_download(task.task_id, timeout=4)
        assert terminal.status == "cancelled" and terminal.result_persisted is True
        keep = runtime.api.prepare_delete_download(task.task_id, delete_files=False)
        assert runtime.api.delete_download(
            task.task_id, delete_files=False, expected_plan=keep.plan_token
        ).deleted
        # A useful file operation is admitted only after worker/callback quiescence.
        next_plan = runtime.api.prepare_delete_download(1)
        assert runtime.api.delete_download(1, expected_plan=next_plan.plan_token).moved_count == 2
        assert reopen(tmp_path) == []
    finally:
        release.set()
        assert runtime.close(cancel=True, wait=True).closed


def test_each_effect_revalidates_replaced_second_file_and_preserves_new_target(
    tmp_path, monkeypatch
):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        plan = runtime.api.prepare_delete_download(1)
        first, second = [Path(f.path) for f in plan.files]
        expected_first, expected_second = first.read_bytes(), second.read_bytes()
        move = trash.move_to_trash

        def replace_after_first(path):
            assert (
                runtime.coordinator._lock._is_owned()
            )  # Real admission/finalization boundary, not another lock.
            result = move(path)
            if len(trash.moves) == 1:
                second.rename(second.with_name("preserved-before-replacement.bin"))
                second.write_bytes(b"new checkpoint replacement")
            return result

        monkeypatch.setattr(trash, "move_to_trash", replace_after_first)
        before = history_bytes(tmp_path)
        with pytest.raises(CommandError) as denied:
            runtime.api.delete_download(1, expected_plan=plan.plan_token)
        assert denied.value.code == "PARTIAL_DELETE" and denied.value.result["moved_count"] == 1
        assert len(trash.moves) == 1 and trash.moves[0][1].read_bytes() == expected_first
        assert second.read_bytes() == b"new checkpoint replacement"
        assert second.with_name("preserved-before-replacement.bin").read_bytes() == expected_second
        assert history_bytes(tmp_path) == before and len(reopen(tmp_path)) == 1
        with pytest.raises(CommandError) as stale:
            runtime.api.delete_download(1, expected_plan=plan.plan_token)
        assert stale.value.code == "STALE_PLAN" and len(trash.moves) == 1
        assert runtime.api.prepare_delete_download(1).missing_count == 1
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_unknown_post_move_exception_is_honest_and_old_token_cannot_replay(tmp_path, monkeypatch):
    runtime, trash = make_owner(tmp_path)
    try:
        seed(runtime, tmp_path)
        plan = runtime.api.prepare_delete_download(1)
        move = trash.move_to_trash

        def unknown(path):
            move(path)
            raise OSError("PRIVATE_POST_EFFECT_SENTINEL")

        monkeypatch.setattr(trash, "move_to_trash", unknown)
        before = history_bytes(tmp_path)
        with pytest.raises(CommandError) as denied:
            runtime.api.delete_download(1, expected_plan=plan.plan_token)
        assert denied.value.code == "PARTIAL_DELETE"
        result = denied.value.result
        assert result["history_deleted"] is False and result["unknown_count"] == 1
        assert result["moved_count"] == 0 and result["failed_count"] == 0
        assert (
            result["files"][0]["status"] == "unknown"
            and result["files"][1]["status"] == "not_attempted"
        )
        assert len(trash.moves) == 1 and trash.moves[0][1].read_bytes()
        assert history_bytes(tmp_path) == before and len(reopen(tmp_path)) == 1
        with pytest.raises(CommandError) as stale:
            runtime.api.delete_download(1, expected_plan=plan.plan_token)
        assert stale.value.code == "STALE_PLAN" and len(trash.moves) == 1
        keep = runtime.api.prepare_delete_download(1, delete_files=False)
        assert runtime.api.delete_download(
            1, delete_files=False, expected_plan=keep.plan_token
        ).deleted
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_shared_hardlink_cannot_bypass_attribution_by_different_spelling(tmp_path):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        alias = media.parent / "different-name-hardlink.mp4"
        os.link(media, alias)
        assert media.stat().st_ino == alias.stat().st_ino
        runtime.history_repo.add(
            HistoryEntry(
                id=2,
                url="https://example.invalid/alias",
                title="Other owner",
                status=DownloadStatus.DONE,
                output_root=tmp_path / "output",
                artifact_paths=[alias],
            )
        )
        before = history_bytes(tmp_path)
        with pytest.raises(CommandError) as denied:
            runtime.api.prepare_delete_download(1)
        assert denied.value.code == "UNSAFE_FILE_SCOPE" and trash.moves == []
        assert history_bytes(tmp_path) == before and alias.read_bytes() == media.read_bytes()
        assert sidecar.exists()
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def _native_link_env(root):
    # A cmd child gets its own selectors too, even though it cannot import product Python.
    env = os.environ.copy()
    for key in (
        "APPDATA",
        "LOCALAPPDATA",
        "HOME",
        "USERPROFILE",
        "TMP",
        "TEMP",
        "TMPDIR",
        "UV_CACHE_DIR",
        "RUFF_CACHE_DIR",
        "MYPY_CACHE_DIR",
        "XDG_CACHE_HOME",
        "YTDL_LOG_DIR",
        "YTDL_DATA_DIR",
    ):
        path = root / key.lower()
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path.resolve())
    return env


@pytest.mark.parametrize("kind", ["direct", "ancestor"])
def test_native_link_capability_and_scope_guard_where_supported(tmp_path, kind):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        link = media.parent / ("direct-link.mp4" if kind == "direct" else "ancestor-link")
        target = media if kind == "direct" else media.parent / "real-directory"
        if kind == "ancestor":
            target.mkdir()
            (target / "owned-extra.bin").write_bytes(b"ancestry preserve")
        try:
            link.symlink_to(target, target_is_directory=kind == "ancestor")
            mechanism = "native-symlink"
        except OSError:
            assert os.name == "nt", "Unix host must support owned symlinks for this gate"
            (tmp_path / "file-symlink-NOT_RUN.json").write_text(
                json.dumps(
                    {
                        "boundary": kind,
                        "status": "NOT_RUN",
                        "reason": (
                            "native symlink privilege unavailable; "
                            "actual junction guard is exercised instead"
                        ),
                    }
                )
            )
            if kind == "direct":
                target = media.parent / "real-directory"
                target.mkdir()
                (target / "owned-extra.bin").write_bytes(b"direct reparse preserve")
            child = tmp_path / "junction-command"
            child.mkdir()
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                cwd=child,
                env=_native_link_env(child),
                capture_output=True,
                timeout=5,
            )
            (child / "stdout.bin").write_bytes(result.stdout)
            (child / "stderr.bin").write_bytes(result.stderr)
            (child / "exit.txt").write_text(str(result.returncode))
            assert result.returncode == 0 and link.is_junction()
            mechanism = "native-junction"
        entry = runtime.history_repo.get_by_id(1)
        entry.artifact_paths.append(link if kind == "direct" else link / "owned-extra.bin")
        runtime.history_repo.update(entry)
        before = history_bytes(tmp_path)
        with pytest.raises(CommandError) as denied:
            runtime.api.prepare_delete_download(1)
        assert denied.value.code == "UNSAFE_FILE_SCOPE" and trash.moves == []
        assert (
            history_bytes(tmp_path) == before and media.read_bytes() == b"distinctive owned media"
        )
        assert sidecar.read_bytes() == b"distinctive owned description"
        (tmp_path / "native-link-proof.json").write_text(
            json.dumps(
                {
                    "boundary": kind,
                    "status": "PROVED",
                    "mechanism": mechanism,
                    "code": denied.value.code,
                }
            )
        )
    finally:
        assert runtime.close(cancel=False, wait=True).closed


@pytest.mark.parametrize("supported", [False, True])
def test_default_real_adapter_is_wired_to_public_policy_at_only_os_boundary(
    tmp_path, monkeypatch, supported
):
    import src.infrastructure.file_remover as adapter

    trash = SyntheticTrash(tmp_path / "os-boundary-trash")

    class QFile:
        @staticmethod
        def supportsMoveToTrash():
            return supported

        @staticmethod
        def moveToTrash(path):
            trash.move_to_trash(Path(path))
            return True, str(trash.moves[-1][1])

    monkeypatch.setattr(adapter, "_qfile", lambda: QFile)
    runtime = create_runtime(
        tmp_path / "profile", settings_overrides={"output_dir": tmp_path / "output"}
    )
    try:
        media, sidecar = seed(runtime, tmp_path)
        preview = runtime.api.prepare_delete_download(1)
        before = history_bytes(tmp_path)
        assert isinstance(runtime.file_remover, adapter.QtFileRemover)
        if supported:
            result = runtime.api.delete_download(1, expected_plan=preview.plan_token)
            assert result.moved_count == 2 and result.deleted
            assert {p.read_bytes() for _, p in trash.moves} == {
                b"distinctive owned media",
                b"distinctive owned description",
            }
            assert reopen(tmp_path) == []
        else:
            with pytest.raises(CommandError) as denied:
                runtime.api.delete_download(1, expected_plan=preview.plan_token)
            assert denied.value.code == "TRASH_UNAVAILABLE"
            assert (
                denied.value.result["moved_count"] == 0
                and denied.value.result["history_deleted"] is False
            )
            assert trash.moves == [] and history_bytes(tmp_path) == before
            assert (
                media.read_bytes() == b"distinctive owned media"
                and sidecar.read_bytes() == b"distinctive owned description"
            )
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_safe_deletion_real_nonempty_main_error_and_stream_sinks(tmp_path, monkeypatch):
    import src.infrastructure.file_remover as adapter
    from src.core.logging_setup import setup_logging

    root = logging.getLogger()
    previous, level = root.handlers[:], root.level
    previous_yt = logging.getLogger("yt_dlp").level
    root.handlers = []  # Do not close pytest/caller-owned handlers through force=True.
    stream = io.StringIO()
    runtime = None
    sentinels = [
        "PRIVATE_URL_SENTINEL",
        "PRIVATE_TITLE_SENTINEL",
        "PRIVATE_PATH_SENTINEL",
        "PRIVATE_PROXY_SENTINEL",
        "PRIVATE_ERROR_SENTINEL",
    ]
    try:
        setup_logging(log_dir=tmp_path / "sinks", stream=stream)
        owned = tmp_path / sentinels[2]
        trash = SyntheticTrash(owned / "os-boundary-trash")
        runtime = create_runtime(
            owned / "profile", settings_overrides={"output_dir": owned / "output"}
        )
        seed(runtime, owned)
        entry = runtime.history_repo.get_by_id(1)
        entry.url = "https://example.invalid/PRIVATE_URL_SENTINEL"
        entry.title = sentinels[1]
        runtime.history_repo.update(entry)
        settings = runtime.api.get_settings()
        settings.proxy = "http://PRIVATE_PROXY_SENTINEL:password@example.invalid:8080"
        runtime.api.update_settings(settings)

        class QFile:
            @staticmethod
            def supportsMoveToTrash():
                return True

            @staticmethod
            def moveToTrash(path):
                if trash.moves:
                    raise OSError("PRIVATE_ERROR_SENTINEL " + " ".join(sentinels))
                trash.move_to_trash(Path(path))
                return True, str(trash.moves[-1][1])

        monkeypatch.setattr(adapter, "_qfile", lambda: QFile)
        preview = runtime.api.prepare_delete_download(1)
        with pytest.raises(CommandError) as denied:
            runtime.api.delete_download(1, expected_plan=preview.plan_token)
        assert denied.value.code == "PARTIAL_DELETE"
        keep = runtime.api.prepare_delete_download(1, delete_files=False)
        assert runtime.api.delete_download(
            1, delete_files=False, expected_plan=keep.plan_token
        ).deleted
        assert runtime.close(cancel=False, wait=True).closed
        for handler in root.handlers:
            handler.flush()
        main = (tmp_path / "sinks/app.log").read_text(encoding="utf-8")
        error = (tmp_path / "sinks/app.error.log").read_text(encoding="utf-8")
        for output in (main, error, stream.getvalue()):
            assert (
                output.strip()
                and "deletion.failed id=1 reason_code=PARTIAL_DELETE moved_count=1" in output
            )
            assert "trash.move.failed reason_code=TRASH_UNAVAILABLE" in output
            assert not any(value in output for value in sentinels)
        assert "trash.move.completed count=1" in main
        assert "deletion.completed id=1 moved_count=0 missing_count=0" in main
        assert "deletion.completed id=1" in stream.getvalue()
        (tmp_path / "sink-observation.json").write_text(
            json.dumps(
                {
                    "main_bytes": len(main.encode()),
                    "error_bytes": len(error.encode()),
                    "stream_bytes": len(stream.getvalue().encode()),
                    "id": 1,
                    "code": denied.value.code,
                    "moved_count": denied.value.result["moved_count"],
                    "forbidden_sentinels_present": False,
                }
            )
        )
    finally:
        if runtime is not None:
            assert runtime.close(cancel=False, wait=True).closed
        for handler in root.handlers:
            handler.flush()
            handler.close()
        root.handlers = previous
        root.setLevel(level)
        logging.getLogger("yt_dlp").setLevel(previous_yt)


@pytest.mark.skipif(
    os.name != "nt", reason="Windows junction; POSIX symlink guard has its own case"
)
def test_native_junction_replacement_between_preview_and_apply_is_stale(tmp_path):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        preview = runtime.api.prepare_delete_download(1)
        before = history_bytes(tmp_path)
        original = media.parent
        preserved = original.with_name("preserved-original-directory")
        original.rename(preserved)
        target = original.with_name("other-owned-directory")
        target.mkdir()
        (target / media.name).write_bytes(b"new junction media preserve")
        (target / sidecar.name).write_bytes(b"new junction sidecar preserve")
        child = tmp_path / "native-junction-child"
        child.mkdir()
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(original), str(target)],
            cwd=child,
            env=_native_link_env(child),
            capture_output=True,
            timeout=5,
        )
        (child / "stdout.bin").write_bytes(result.stdout)
        (child / "stderr.bin").write_bytes(result.stderr)
        (child / "exit.txt").write_text(str(result.returncode))
        assert result.returncode == 0 and original.is_junction()
        assert original.resolve().is_relative_to(tmp_path / "output")
        with pytest.raises(CommandError) as unsafe:
            runtime.api.prepare_delete_download(1)
        assert unsafe.value.code == "UNSAFE_FILE_SCOPE"
        with pytest.raises(CommandError) as stale:
            runtime.api.delete_download(1, expected_plan=preview.plan_token)
        assert stale.value.code == "STALE_PLAN" and trash.moves == []
        assert history_bytes(tmp_path) == before
        assert (preserved / media.name).read_bytes() == b"distinctive owned media"
        assert (preserved / sidecar.name).read_bytes() == b"distinctive owned description"
        assert media.read_bytes() == b"new junction media preserve"
        assert sidecar.read_bytes() == b"new junction sidecar preserve"
        (tmp_path / "junction-proof.json").write_text(
            json.dumps(
                {
                    "native_child_exit": result.returncode,
                    "link_is_junction": True,
                    "inside_root": True,
                    "preview_code": unsafe.value.code,
                    "apply_code": stale.value.code,
                    "moved_count": len(trash.moves),
                }
            )
        )
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_unknown_legacy_nonterminal_area_is_not_guessed_from_reader_defaults(tmp_path):
    runtime, trash = make_owner(tmp_path)
    try:
        media, sidecar = seed(runtime, tmp_path)
        confirmed = runtime.api.prepare_delete_download(1)
        unfinished = media.parent.with_name("unfinished-legacy-directory")
        unfinished.mkdir()
        partial = unfinished / "writing.part"
        partial.write_bytes(b"in-progress preserve")
        runtime.history_repo.add(
            HistoryEntry(
                id=2,
                url="https://example.invalid/unfinished",
                title="Unfinished legacy",
                status=DownloadStatus.DOWNLOADING,
                output_root=None,
                output_dir=unfinished,
            )
        )
        before = history_bytes(tmp_path)
        reader = create_runtime(tmp_path / "profile", read_only=True)
        try:
            assert reader.api.get_settings().output_dir != runtime.api.get_settings().output_dir
            with pytest.raises(CommandError) as denied:
                reader.api.prepare_delete_download(1)
            assert denied.value.code == "ACTIVE_DOWNLOAD"
        finally:
            assert reader.close().closed
        with pytest.raises(CommandError) as denied:
            runtime.api.delete_download(1, expected_plan=confirmed.plan_token)
        assert denied.value.code == "ACTIVE_DOWNLOAD"
        assert trash.moves == [] and history_bytes(tmp_path) == before
        assert (
            partial.read_bytes() == b"in-progress preserve" and media.exists() and sidecar.exists()
        )
    finally:
        assert runtime.close(cancel=False, wait=True).closed


def test_readonly_detached_preview_token_applies_at_existing_writable_owner(tmp_path):
    runtime, trash = make_owner(tmp_path)
    try:
        seed(runtime, tmp_path)
        before = history_bytes(tmp_path)
        reader = create_runtime(tmp_path / "profile", read_only=True)
        try:
            preview = reader.api.prepare_delete_download(1)
            assert preview.plan_token == runtime.api.prepare_delete_download(1).plan_token
            assert history_bytes(tmp_path) == before and trash.moves == []
        finally:
            assert reader.close().closed
        result = runtime.api.delete_download(1, expected_plan=preview.plan_token)
        assert result.deleted and result.moved_count == 2 and reopen(tmp_path) == []
        assert {p.read_bytes() for _, p in trash.moves} == {
            b"distinctive owned media",
            b"distinctive owned description",
        }
    finally:
        assert runtime.close(cancel=False, wait=True).closed
