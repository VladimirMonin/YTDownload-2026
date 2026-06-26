"""Root CLI entry point for YTDownload 2026.

This package defines the user-facing command tree and keeps transport wiring
thin: argument parsing, help text, output/exit-code contract, and dispatch into
shared bootstrap helpers.
"""

from .root import main

run_cli = main

__all__ = ["main", "run_cli"]
