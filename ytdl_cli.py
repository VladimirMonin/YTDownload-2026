"""Standalone console entry; all commands belong to the canonical CLI adapter."""

from src.interfaces.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
