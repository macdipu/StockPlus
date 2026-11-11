"""In-memory test doubles that satisfy the live-feed ports."""

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import replace
from datetime import date, datetime, timedelta
from types import TracebackType
from typing import Self

from dse.core.clock import DHAKA
from dse.features.live_feed.application.dto import FeedCounters, FeedEvent, PublishedEvent
from dse.features.live_feed.domain.entities import LiveQuote, LiveSnapshot, MarketState, Tick
from dse.features.live_feed.domain.ports import FetchResult
from dse.shared_kernel.symbol import Symbol

NOW = datetime(2026, 11, 11, 11, 40, tzinfo=DHAKA)


class FakeClock:
    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


class FakeFeed:
    """Serves a script of results; an Exception in the script is raised. Records the ETags it was sent."""

    def __init__(self, *script: FetchResult | Exception) -> None:
        self.script, self.etags = list(script), []  # type: list[FetchResult | Exception], list[str | None]

    def push(self, item: FetchResult | Exception) -> None:
        self.script.append(item)

    async def fetch(self, etag: str | None) -> FetchResult:
        self.etags.append(etag)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class MemoryStore:
    def __init__(self) -> None:
        self.state: MarketState | None = None
        self.quote_map: dict[str, LiveQuote] = {}
        self.counters: FeedCounters | None = None
        self.writes: list[int] = []  # how many quotes each save rewrote

    async def load_snapshot(self) -> LiveSnapshot | None:
        return LiveSnapshot(self.state, dict(self.quote_map)) if self.state else None

    async def save_snapshot(
        self, snapshot: LiveSnapshot, changed: Sequence[LiveQuote], *, full: bool = False
    ) -> None:
        if full:
            self.quote_map.clear()
        self.quote_map.update({q.symbol.value: q for q in changed})
        self.state = snapshot.state
        self.writes.append(len(changed))

    async def market(self) -> MarketState | None:
        return self.state

    async def quotes(self, symbols: Sequence[str] | None = None) -> list[LiveQuote]:
        keys = sorted(self.quote_map) if symbols is None else [s for s in symbols if s in self.quote_map]
        return [self.quote_map[k] for k in keys]

    async def load_counters(self) -> FeedCounters | None:
        return replace(self.counters) if self.counters else None

    async def save_counters(self, counters: FeedCounters) -> None:
        self.counters = replace(counters)


class MemoryBus:
    """Publisher + stream in one: what Redis pub/sub does across processes, in-process."""

    def __init__(self, fail_next: int = 0) -> None:
        self.seq, self.published, self.fail_next = 0, [], fail_next  # type: int, list[PublishedEvent], int
        self._listeners: list[asyncio.Queue[PublishedEvent | Exception]] = []

    async def publish(self, events: Sequence[FeedEvent]) -> list[PublishedEvent]:
        if self.fail_next:
            self.fail_next -= 1
            raise ConnectionError("bus down")
        out = []
        for e in events:
            self.seq += 1
            out.append(
                PublishedEvent(
                    **e.model_dump(include=set(FeedEvent.model_fields)),
                    id=self.seq,
                    published_ms=e.received_ms + 1,
                )
            )
        self.published += out
        for q in self._listeners:
            for p in out:
                q.put_nowait(p)
        return out

    def drop_connections(self) -> None:
        for q in self._listeners:
            q.put_nowait(ConnectionError("connection reset"))

    async def listen(self, on_subscribed: Callable[[], None]) -> AsyncIterator[PublishedEvent]:
        q: asyncio.Queue[PublishedEvent | Exception] = asyncio.Queue()
        self._listeners.append(q)
        on_subscribed()
        try:
            while True:
                item = await q.get()
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            self._listeners.remove(q)


class TickLog:
    def __init__(self, fail: bool = False) -> None:
        self.rows: list[Tick] = []
        self.fail = fail


class FakeUow:
    def __init__(self, log: TickLog) -> None:
        self._log, self._pending = log, []  # type: TickLog, list[Tick]
        outer = self

        class Ticks:
            async def between(self, symbol: Symbol, start_ms: int, end_ms: int) -> list[Tick]:
                return sorted(
                    (t for t in log.rows if t.symbol == symbol and start_ms <= t.ts_ms < end_ms),
                    key=lambda t: t.ts_ms,
                )

            async def record(self, ticks: Sequence[Tick]) -> int:
                if log.fail:
                    raise RuntimeError("db down")
                outer._pending += ticks
                return len(ticks)

        self.ticks = Ticks()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self._pending.clear()

    async def commit(self) -> None:
        self._log.rows += self._pending
        self._pending.clear()


class FakeGuard:
    def __init__(self) -> None:
        self.claimed: set[str] = set()

    async def claim(self, key: str, ttl_s: int) -> bool:
        if key in self.claimed:
            return False
        self.claimed.add(key)
        return True

    async def release(self, key: str) -> None:
        self.claimed.discard(key)


def with_quote(snap: LiveSnapshot, symbol: str, **changes: object) -> LiveSnapshot:
    quotes = dict(snap.quotes)
    quotes[symbol] = replace(quotes[symbol], **changes)  # type: ignore[arg-type]
    return replace(snap, quotes=quotes)


def with_trade_time(snap: LiveSnapshot, trade_time: str) -> LiveSnapshot:
    return replace(snap, state=replace(snap.state, trade_time=trade_time))
