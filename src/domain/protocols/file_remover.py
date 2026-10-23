"""Recoverable OS file-effect seam; no Qt or permanent-delete fallback."""

from pathlib import Path
from typing import Protocol

from .runtime_resource import RuntimeResource


class FileRemovalError(RuntimeError):
    """Safe refusal/uncertain effect; never carries raw OS error or paths."""

    def __init__(self, *, outcome: str = "failed") -> None:
        super().__init__("Recoverable move unavailable")
        self.code = "TRASH_UNAVAILABLE"
        self.outcome = outcome


class IFileRemover(RuntimeResource, Protocol):
    def move_to_trash(self, path: Path) -> bool:
        """Report a real recoverable move; never fall back to permanent deletion."""
