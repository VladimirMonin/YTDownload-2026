"""Compatible composition wrapper; application APIs live independently of adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.bootstrap import create_runtime


def initialize_app(data_root: Path | None = None, **runtime_options: Any) -> dict[str, Any]:
    """Retain legacy service keys/aliases and expose their explicit owning runtime.

    No singleton, handlers, window or server are created. Entry adapters must
    ultimately close services['runtime']; legacy explicit executor joins also
    notify the same lifecycle owner during the S2-S5 migration.
    """
    runtime = create_runtime(data_root, **runtime_options)
    try:
        return runtime.as_services()
    except BaseException:
        runtime.close(cancel=False, wait=True)
        raise
