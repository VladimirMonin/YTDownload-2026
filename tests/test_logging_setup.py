"""Real logging sinks and path selection; not a whole-application privacy audit."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from src.core import logging_setup


@pytest.fixture
def isolated_logging(capsys):
    """Do not let force=True close pytest's borrowed handlers."""
    root = logging.getLogger()
    previous_handlers, previous_level = root.handlers[:], root.level
    backend_logger = logging.getLogger("yt_dlp")
    previous_backend_level = backend_logger.level
    root.handlers = []
    try:
        yield root
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            try:
                # pytest may already have closed its phase-local stderr capture.
                # StreamHandler emits flush synchronously; files still need draining.
                if isinstance(handler, RotatingFileHandler):
                    handler.flush()
            finally:
                handler.close()
        root.handlers = previous_handlers
        root.setLevel(previous_level)
        backend_logger.setLevel(previous_backend_level)


@pytest.mark.parametrize("selection", ["environment", "explicit", "default"])
def test_log_directory_selection_and_real_file_stderr_output(
    monkeypatch, tmp_path: Path, capsys, isolated_logging, selection: str
) -> None:
    # Even the pre-fix fallback stays synthetic during the RED run.
    module_root = tmp_path / "module"
    monkeypatch.setattr(
        logging_setup, "__file__", str(module_root / "src" / "core" / "logging_setup.py")
    )
    monkeypatch.setenv("YTDL_LOG_LEVEL", "INFO")
    if selection == "default":
        monkeypatch.delenv("YTDL_LOG_DIR", raising=False)
        expected_dir = module_root / "logs"
    else:
        monkeypatch.setenv("YTDL_LOG_DIR", str(tmp_path / "environment"))
        expected_dir = tmp_path / selection
    explicit = expected_dir if selection == "explicit" else None

    logging_setup.setup_logging(log_dir=explicit, stream=sys.stderr)
    logger = logging.getLogger("s1.logging")
    logger.info("operation.completed id=41 count=0 elapsed_ms=12")
    logger.error("operation.failed id=42 reason_code=SYNTHETIC_FAILURE")
    logger.debug("debug-not-selected")
    for handler in isolated_logging.handlers:
        handler.flush()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "operation.completed id=41 count=0 elapsed_ms=12" in captured.err
    assert "operation.failed id=42 reason_code=SYNTHETIC_FAILURE" in captured.err
    assert "debug-not-selected" not in captured.err
    normal = (expected_dir / "app.log").read_text(encoding="utf-8")
    errors = (expected_dir / "app.error.log").read_text(encoding="utf-8")
    assert "operation.completed id=41 count=0 elapsed_ms=12" in normal
    assert "operation.failed id=42 reason_code=SYNTHETIC_FAILURE" in normal
    assert "operation.failed id=42 reason_code=SYNTHETIC_FAILURE" in errors
    assert "operation.completed" not in errors
    assert "debug-not-selected" not in normal

    files = [h for h in isolated_logging.handlers if isinstance(h, RotatingFileHandler)]
    assert [(Path(h.baseFilename).name, h.maxBytes, h.backupCount, h.level) for h in files] == [
        ("app.log", 10 * 1024 * 1024, 5, logging.NOTSET),
        ("app.error.log", 5 * 1024 * 1024, 3, logging.ERROR),
    ]
    if selection == "explicit":
        assert not (tmp_path / "environment").exists()


def test_reconfiguration_closes_old_files_and_preserves_debug_level(
    monkeypatch, tmp_path: Path, capsys, isolated_logging
) -> None:
    monkeypatch.setenv("YTDL_LOG_LEVEL", "DEBUG")
    first, second = tmp_path / "first", tmp_path / "second"
    logging_setup.setup_logging(log_dir=first, stream=sys.stderr)
    old_files = [h for h in isolated_logging.handlers if isinstance(h, RotatingFileHandler)]
    logging.getLogger("s1.logging").debug("before-reconfigure id=1")

    logging_setup.setup_logging(log_dir=second, stream=sys.stderr)
    logging.getLogger("s1.logging").debug("after-reconfigure id=2")
    for handler in isolated_logging.handlers:
        handler.flush()

    assert all(handler.stream is None for handler in old_files)
    assert "before-reconfigure id=1" in (first / "app.log").read_text(encoding="utf-8")
    assert "after-reconfigure" not in (first / "app.log").read_text(encoding="utf-8")
    assert "after-reconfigure id=2" in (second / "app.log").read_text(encoding="utf-8")
    assert (second / "app.error.log").read_text(encoding="utf-8") == ""
    stderr = capsys.readouterr().err
    assert stderr.count("before-reconfigure id=1") == 1
    assert stderr.count("after-reconfigure id=2") == 1
    assert logging.getLogger("yt_dlp").level == logging.WARNING
