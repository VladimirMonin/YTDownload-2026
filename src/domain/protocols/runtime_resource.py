"""Owned lifecycle resource port; implementation/OS choices stay outside core."""

from typing import Protocol


class RuntimeResource(Protocol):
    def close(self) -> None:
        """Idempotently release this resource after its writers have stopped."""
