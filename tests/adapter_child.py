"""Test-only process harness. Replaces only the network backend, then runs the REAL CLI entry.

No production fake flag/alternate business facade. All selectors are supplied by
an owned parent before this module or any product code is imported.
"""

from __future__ import annotations

import ctypes
import json
import runpy
import sys
from ctypes import wintypes
from pathlib import Path
from threading import Event

import src.infrastructure.ytdlp_service as network_edge
from src.domain.models import VideoInfo
from src.domain.models.download_outcome import DownloadOutcome


def main() -> None:
    scenario, location, *arguments = sys.argv[1:]
    root = Path(location).resolve()
    root.mkdir(parents=True, exist_ok=True)
    locked = []

    class Edge:
        def __init__(self, **kwargs):
            self.cancelled = Event()

        def fetch_info(self, url, settings):
            return VideoInfo(title="PRIVATE_TITLE_SENTINEL")

        def cancel(self):
            self.cancelled.set()

        def download(self, task, settings, progress_callback=None):
            (root / "backend-entered.json").write_text(
                json.dumps({"id": task.id}), encoding="utf-8"
            )
            if scenario == "stdio-owned":
                assert self.cancelled.wait(8)  # EOF must request cooperative cancellation.
            else:
                assert sys.stdin.readline().strip() == "release"
            folder = settings.output_dir / f"download-{task.id}"
            folder.mkdir(parents=True, exist_ok=True)
            media = folder / "PRIVATE_PATH_SENTINEL.mp4"
            media.write_bytes(f"owned-cli-media-{task.id}".encode())
            if scenario == "failed":
                raise RuntimeError(
                    "PRIVATE_RAW_ERROR_SENTINEL https://example.invalid/PRIVATE_URL_SENTINEL"
                )
            if scenario in {"cancelled", "stdio-owned"}:
                return DownloadOutcome.from_paths(
                    {"video": media, "scan_root": folder}, status="cancelled"
                )
            if scenario == "persistence":
                # Real Windows refusal at the atomic replace boundary; old JSON remains readable.
                import os

                assert os.name == "nt"
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.CreateFileW.argtypes = [
                    wintypes.LPCWSTR,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.HANDLE,
                ]
                kernel.CreateFileW.restype = wintypes.HANDLE
                path = Path(os.environ["YTDL_DATA_DIR"]) / "data/history.json"
                handle = kernel.CreateFileW(str(path), 0x80000000, 0x1 | 0x2, None, 3, 0, None)
                assert handle not in (None, ctypes.c_void_p(-1).value)
                locked.append((kernel, handle))
            return DownloadOutcome.from_paths({"video": media, "scan_root": folder})

    network_edge.YtDlpService = Edge
    sys.argv = ["ytdl", *arguments]
    try:
        runpy.run_module("src.interfaces.cli", run_name="__main__")
    finally:
        closed = 0
        for kernel, handle in locked:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.restype = wintypes.BOOL
            assert kernel.CloseHandle(handle)
            closed += 1
        (root / "harness-release.json").write_text(
            json.dumps(
                {
                    "native_storage_handles_closed": closed,
                    "scenario": scenario,
                    "entry": "src.interfaces.cli.__main__",
                    "business_facade_replaced": False,
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
