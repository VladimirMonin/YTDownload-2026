"""Run the YTDownload root CLI via `python -m src.interfaces.cli`."""

from __future__ import annotations

from .root import main

if __name__ == "__main__":
    raise SystemExit(main())
