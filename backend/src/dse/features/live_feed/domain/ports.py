"""Ports the live-feed domain needs from the outside world. Implemented in infrastructure; faked in tests."""

from collections.abc import Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

from dse.features.live_feed.domain.depth import MarketDepth
from dse.features.live_feed.domain.entities import LiveSnapshot, Tick
from dse.shared_kernel.symbol import Symbol


@dataclass(frozen=True, slots=True)
class FetchResult:
    """`snapshot` is None when upstream answered 304 Not Modified for `etag`."""

    snapshot: LiveSnapshot | None
    etag: str | None


class SnapshotFeed(Protocol):
    async def fetch(self, etag: str | None) -> FetchResult: ...


class DepthFeed(Protocol):
    async def fetch(self, symbol: Symbol) -> MarketDepth:
        """Raises NotFoundError for an unknown code, Upstream* errors when DSE cannot be reached."""
        ...


class TickRepository(Protocol):
    async def between(self, symbol: Symbol, start_ms: int, end_ms: int) -> list[Tick]:
        """Ticks of one instrument with start_ms <= ts < end_ms, oldest first."""
        ...

    async def record(self, ticks: Sequence[Tick]) -> int:
        """Insert; a (symbol, ts) already recorded is ignored. Returns rows written."""
        ...


class LiveFeedUnitOfWork(Protocol):
    @property
    def ticks(self) -> TickRepository: ...

    async def __aenter__(self) -> "LiveFeedUnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...
