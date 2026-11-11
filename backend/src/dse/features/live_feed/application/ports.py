"""Application-level ports: the shared live state (CQRS read side) and the event bus between processes.

They live here rather than in `domain` because they carry application DTOs (counters, events).
"""

from collections.abc import AsyncIterator, Callable, Sequence
from typing import Protocol

from dse.features.live_feed.application.dto import FeedCounters, FeedEvent, PublishedEvent
from dse.features.live_feed.domain.entities import LiveQuote, LiveSnapshot, MarketState


class LiveStateStore(Protocol):
    """Latest market state, written by the worker, read by every API replica."""

    async def load_snapshot(self) -> LiveSnapshot | None: ...

    async def save_snapshot(
        self, snapshot: LiveSnapshot, changed: Sequence[LiveQuote], *, full: bool = False
    ) -> None:
        """Persist the market state and the `changed` quotes atomically (only deltas are rewritten).
        `full` replaces every quote, dropping instruments no longer in the snapshot."""
        ...

    async def market(self) -> MarketState | None: ...

    async def quotes(self, symbols: Sequence[str] | None = None) -> list[LiveQuote]:
        """`None` = every instrument, sorted by symbol; unknown symbols are skipped."""
        ...

    async def load_counters(self) -> FeedCounters | None: ...

    async def save_counters(self, counters: FeedCounters) -> None: ...


class EventPublisher(Protocol):
    async def publish(self, events: Sequence[FeedEvent]) -> list[PublishedEvent]:
        """Assign globally increasing ids and broadcast to every API replica."""
        ...


class EventStream(Protocol):
    def listen(self, on_subscribed: Callable[[], None]) -> AsyncIterator[PublishedEvent]:
        """Every event published after `on_subscribed` fires. Raises when the connection drops
        (callers reconnect)."""
        ...


class OnceGuard(Protocol):
    """Cross-process 'do this once per key' (e.g. one end-of-day write per session, even across restarts)."""

    async def claim(self, key: str, ttl_s: int) -> bool: ...

    async def release(self, key: str) -> None: ...
