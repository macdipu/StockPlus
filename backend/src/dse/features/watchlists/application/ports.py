"""Collaborators outside this feature (fulfilled from other features' facades)."""

from collections.abc import Sequence
from typing import Any, Protocol


class SymbolDirectory(Protocol):
    async def ensure_known(self, symbols: Sequence[str]) -> None:
        """Raises ValidationFailedError naming any symbol DSE does not list;
        ServiceNotReadyError when that cannot be checked right now."""
        ...


class ScanValidator(Protocol):
    def validate(self, definition: Any) -> None:
        """Raises a 400-class error when `definition` is not a well-formed scan."""
        ...
