"""Real lazy infrastructure adapter; replace Qt OS call, never its result policy."""

from __future__ import annotations

from pathlib import Path

import pytest

import src.infrastructure.file_remover as adapter
from src.domain.protocols.file_remover import FileRemovalError


@pytest.mark.parametrize(
    "boundary",
    [
        "missing_qt",
        "missing_capability",
        "unsupported",
        "false_tuple",
        "true_no_effect",
        "malformed",
        "exception",
    ],
)
def test_adapter_capability_or_os_failure_never_falls_back_to_unlink(
    tmp_path, monkeypatch, boundary
):
    source = tmp_path / "owned.bin"
    source.write_bytes(b"source bytes preserved")
    calls = []

    class QFile:
        @staticmethod
        def supportsMoveToTrash():
            return boundary != "unsupported"

        @staticmethod
        def moveToTrash(path):
            calls.append(path)
            if boundary == "exception":
                raise OSError("PRIVATE_OS_ERROR_SENTINEL")
            return {
                "false_tuple": (False, ""),
                "true_no_effect": (True, ""),
                "malformed": True,
            }.get(boundary, (False, ""))

    def load():
        if boundary == "missing_qt":
            raise ImportError("PRIVATE_IMPORT_SENTINEL")
        return QFile

    if boundary == "missing_capability":
        del QFile.supportsMoveToTrash
    monkeypatch.setattr(adapter, "_qfile", load)
    remover = adapter.QtFileRemover()
    try:
        with pytest.raises(FileRemovalError) as denied:
            remover.move_to_trash(source)
        assert denied.value.code == "TRASH_UNAVAILABLE" and denied.value.outcome == "failed"
        assert "PRIVATE_" not in str(denied.value)
        assert source.read_bytes() == b"source bytes preserved"
        assert list(tmp_path.iterdir()) == [source]
        if boundary in {"missing_qt", "missing_capability", "unsupported"}:
            assert calls == []
    finally:
        remover.close()


def test_actual_adapter_success_requires_real_recoverable_boundary_move(tmp_path, monkeypatch):
    source, trash = tmp_path / "owned.bin", tmp_path / "synthetic-trash.bin"
    source.write_bytes(b"recoverable adapter bytes")

    class QFile:
        @staticmethod
        def supportsMoveToTrash():
            return True

        @staticmethod
        def moveToTrash(path):
            Path(path).rename(trash)
            return True, str(trash)

    monkeypatch.setattr(adapter, "_qfile", lambda: QFile)
    remover = adapter.QtFileRemover()
    try:
        assert remover.move_to_trash(source) is True
        assert not source.exists() and trash.read_bytes() == b"recoverable adapter bytes"
    finally:
        remover.close()


def test_adapter_exception_after_actual_move_is_unknown_not_false_no_effect(tmp_path, monkeypatch):
    source, trash = tmp_path / "owned.bin", tmp_path / "synthetic-trash.bin"
    source.write_bytes(b"uncertain but recoverable")

    class QFile:
        @staticmethod
        def supportsMoveToTrash():
            return True

        @staticmethod
        def moveToTrash(path):
            Path(path).rename(trash)
            raise OSError("PRIVATE_POST_EFFECT_SENTINEL")

    monkeypatch.setattr(adapter, "_qfile", lambda: QFile)
    remover = adapter.QtFileRemover()
    try:
        with pytest.raises(FileRemovalError) as denied:
            remover.move_to_trash(source)
        assert denied.value.outcome == "unknown" and denied.value.code == "TRASH_UNAVAILABLE"
        assert not source.exists() and trash.read_bytes() == b"uncertain but recoverable"
    finally:
        remover.close()
