"""Offline CLI help smoke for the unified ytdl command tree.

This smoke stays entirely local: it runs the checked-in CLI entry point with
`--help` at a few important nodes and verifies that the expected command groups
and safety notes are present. It does not start servers or touch YouTube.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from scripts.smoke_support import isolated_smoke

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CASES: tuple[tuple[list[str], tuple[str, ...]], ...] = (
    (
        ["--help"],
        (
            "queue",
            "history",
            "server",
            "smoke_cli_help.py",
            "smoke_mcp_stdio.py",
        ),
    ),
    (
        ["queue", "--help"],
        (
            "Queue commands are transport-thin wrappers over the shared application API.",
            "queue add https://youtu.be/dQw4w9WgXcQ --quality 720p",
            "queue cancel 42 --confirm",
        ),
    ),
    (
        ["history", "--help"],
        (
            "History commands are transport-thin wrappers over the shared application API.",
            "history search python --with-description --format json",
            "history delete 42 --confirm",
        ),
    ),
    (
        ["server", "--help"],
        (
            "Server commands reuse the shared MCP bootstrap for both HTTP and stdio transports.",
            "server stdio",
            "Real download/cancel/sidecar validation remains a separate opt-in gate.",
        ),
    ),
    (
        ["server", "stdio", "--help"],
        (
            "Start the MCP server over stdio for native MCP clients.",
        ),
    ),
)


def _run_cases() -> None:
    for argv, expected_fragments in CASES:
        result = subprocess.run(
            [sys.executable, "-m", "src.interfaces.cli", *argv],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            raise SystemExit(
                f"cli-help-smoke failed argv={argv!r} exit={result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        combined = result.stdout + result.stderr
        missing = [fragment for fragment in expected_fragments if fragment not in combined]
        if missing:
            raise SystemExit(
                f"cli-help-smoke missing argv={argv!r} fragments={missing!r}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

    print(f"cli-help-smoke ok cases={len(CASES)}")


def main() -> None:
    with isolated_smoke():
        _run_cases()


if __name__ == "__main__":
    main()
