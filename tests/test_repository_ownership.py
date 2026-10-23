"""S2 repository ownership: real bytes/caches, not save-called assertions."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.domain.models import AppSettings, HistoryEntry
from src.infrastructure.repositories import JsonHistoryRepository, JsonSettingsRepository


@pytest.mark.parametrize("reader", ["get_by_id", "get_all", "search"])
def test_history_inputs_and_reads_are_detached(tmp_path: Path, reader: str) -> None:
    repo = JsonHistoryRepository(tmp_path)
    entry = HistoryEntry(id=repo.next_id(), url="https://example.invalid/alpha", title="Before")
    repo.add(entry)
    entry.title = "input mutated without update"
    assert repo.get_by_id(entry.id).title == "Before"
    if reader == "get_by_id":
        returned = repo.get_by_id(entry.id)
    elif reader == "get_all":
        returned = repo.get_all()[0]
    else:
        returned = repo.search("alpha")[0]
    returned.title = "read result mutated without update"
    returned.subtitle_paths.append(tmp_path / "not-saved.vtt")
    assert repo.get_by_id(entry.id).title == "Before"
    assert repo.get_by_id(entry.id).subtitle_paths == []
    reopened = JsonHistoryRepository(tmp_path).get_by_id(entry.id)
    assert reopened.title == "Before"
    assert reopened.subtitle_paths == []


def _fail_replace(monkeypatch, target: Path) -> None:
    original = os.replace

    def fail(source, destination):
        if Path(destination) == target:
            raise OSError("synthetic pre-replace fault — not user data")
        return original(source, destination)

    monkeypatch.setattr(os, "replace", fail)


def test_history_replace_failure_preserves_disk_and_cache(monkeypatch, tmp_path: Path) -> None:
    repo = JsonHistoryRepository(tmp_path)
    repo.add(HistoryEntry(id=1, url="https://example.invalid/old", title="Committed"))
    target = tmp_path / "history.json"
    before = target.read_bytes()
    changed = repo.get_by_id(1)
    changed.title = "Must not commit"
    _fail_replace(monkeypatch, target)
    with pytest.raises(RuntimeError) as caught:
        repo.update(changed)
    assert caught.value.code == "PERSISTENCE_FAILED"
    assert target.read_bytes() == before
    assert repo.get_by_id(1).title == "Committed"
    assert JsonHistoryRepository(tmp_path).get_by_id(1).title == "Committed"


def test_settings_replace_failure_preserves_disk_and_cache(monkeypatch, tmp_path: Path) -> None:
    repo = JsonSettingsRepository(tmp_path)
    repo.save(AppSettings(output_dir=tmp_path / "original", theme="light"))
    target = tmp_path / "settings.json"
    before = target.read_bytes()
    changed = repo.load()
    changed.output_dir = tmp_path / "not-committed"
    _fail_replace(monkeypatch, target)
    with pytest.raises(RuntimeError) as caught:
        repo.save(changed)
    assert caught.value.code == "PERSISTENCE_FAILED"
    assert target.read_bytes() == before
    assert repo.load().output_dir == tmp_path / "original"
    assert JsonSettingsRepository(tmp_path).load().theme == "light"


@pytest.mark.parametrize("kind", ["history", "settings"])
def test_corrupt_file_is_preserved_and_refused(tmp_path: Path, kind: str) -> None:
    target = tmp_path / f"{kind}.json"
    damaged = b'{"synthetic-incomplete":'
    target.write_bytes(damaged)
    with pytest.raises(RuntimeError) as caught:
        if kind == "history":
            JsonHistoryRepository(tmp_path)
        else:
            JsonSettingsRepository(tmp_path).load()
    assert caught.value.code == "STORAGE_CORRUPT"
    assert target.read_bytes() == damaged


def test_settings_inputs_and_reads_are_detached(tmp_path: Path) -> None:
    repo = JsonSettingsRepository(tmp_path)
    settings = AppSettings(output_dir=tmp_path / "output", theme="light", save_description=False)
    repo.save(settings)
    settings.theme = "dark"
    loaded = repo.load()
    assert loaded.theme == "light"
    loaded.theme = "dark"
    assert repo.load().theme == "light"
    assert JsonSettingsRepository(tmp_path).load().save_description is False


def test_legacy_history_roundtrip_keeps_identity_and_paths(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    old = {
        "next_id": 17,
        "entries": [{"id": 12, "url": "https://example.invalid/legacy", "title": "Legacy",
                     "quality": "480p", "download_type": "video", "status": "done",
                     "video_path": str(tmp_path / "legacy.mp4"), "subtitle_paths": [],
                     "created_at": "2025-01-02T03:04:05", "finished_at": None}],
    }
    path.write_text(json.dumps(old), encoding="utf-8")
    original_bytes = path.read_bytes()
    repo = JsonHistoryRepository(tmp_path)
    assert path.read_bytes() == original_bytes
    entry = repo.get_by_id(12)
    assert entry.video_path == tmp_path / "legacy.mp4"
    assert entry.quality.value == "480p"
    entry.title = "Updated legacy"
    repo.update(entry)
    reopened = JsonHistoryRepository(tmp_path)
    assert reopened.get_by_id(12).title == "Updated legacy"
    assert reopened.next_id() == 17
