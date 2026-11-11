"""Ports of the scanner application. Infrastructure implements them; tests fake them."""

from collections.abc import Hashable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from dse.features.analysis.application.facade import QuoteInput, UniverseInput


@dataclass(frozen=True, slots=True)
class LiveState:
    session_day: date | None
    trade_time: str | None
    quotes: dict[str, QuoteInput] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StoredUniverse:
    """What the worker publishes: raw rows for both views (frames are rebuilt by readers)."""

    built_at_ms: int
    build_ms: int
    session_day: date | None
    trade_time: str | None
    live_rows: list[dict[str, Any]]
    last_close_rows: list[dict[str, Any]]
    errors: dict[str, str]
    version: int = 0  # assigned by the store on save


class UniverseSource(Protocol):
    async def history_signature(self) -> Hashable:
        """Cheap value that changes iff stored history or fundamentals changed."""
        ...

    async def load_history(self) -> list[UniverseInput]:
        """Bars + fundamentals for every instrument (no quotes)."""
        ...

    async def live_state(self) -> LiveState:
        """Current quotes and session; empty when the live feed has nothing yet."""
        ...


class UniverseStore(Protocol):
    async def version(self) -> int | None: ...

    async def load(self) -> StoredUniverse | None: ...

    async def save(self, universe: StoredUniverse) -> int:
        """Atomically replace the published universe; returns its new (increasing) version."""
        ...


class UniverseNotifier(Protocol):
    async def built(self, version: int, rows: int, build_ms: int) -> None: ...
