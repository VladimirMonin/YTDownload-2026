"""OS file-effect seam. The safe delete policy/adapter are introduced in S4."""

from pathlib import Path
from typing import Protocol

from .runtime_resource import RuntimeResource


class IFileRemover(RuntimeResource, Protocol):
    def move_to_trash(self, path: Path) -> bool:
        """Report a real recoverable move; never fall back to permanent deletion."""
