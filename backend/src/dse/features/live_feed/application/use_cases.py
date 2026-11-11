"""Live-feed use cases.

Write side (worker): PollSnapshot, RunFeed, EndOfDayTrigger.
Read side (API replicas): GetQuotes, GetMarket, GetFeedStatus — they only read the shared state store.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Any, Literal

from dse.features.live_feed.application.dto import (
    FeedCounters,
    FeedEvent,
    FeedStatusDto,
    MarketDto,
    PollOutcome,
    QuoteDto,
)
from dse.features.live_feed.application.mappers import feed_status_dto, market_dto, quote_dto
from dse.features.live_feed.application.ports import EventPublisher, LiveStateStore, OnceGuard
from dse.features.live_feed.domain.entities import (
    LiveSnapshot,
    MinuteBar,
    PollPolicy,
    Tick,
    minute_bars,
)
from dse.features.live_feed.domain.ports import LiveFeedUnitOfWork, SnapshotFeed
from dse.shared_kernel.clock import Clock
from dse.shared_kernel.errors import ServiceNotReadyError, UpstreamForbiddenError
from dse.shared_kernel.symbol import Symbol

log = logging.getLogger("dse.live_feed")
UowFactory = Callable[[], LiveFeedUnitOfWork]


def epoch_ms(clock: Clock) -> int:
    return int(clock.now().timestamp() * 1000)


class PollSnapshot:
    """One poll: conditional GET → diff against the last state → store → publish deltas → record ticks.

    Delivery is at-least-once: the in-memory baseline only advances after the publish succeeded, so a failed
    publish is retried (and re-diffed) on the next poll. Tick recording is best-effort and never blocks it.
    """

    def __init__(
        self,
        feed: SnapshotFeed,
        store: LiveStateStore,
        publisher: EventPublisher,
        uow: UowFactory,
        clock: Clock,
        policy: PollPolicy,
    ) -> None:
        self._feed, self._store, self._publisher, self._uow = feed, store, publisher, uow
        self._clock, self._policy = clock, policy
        self._previous: LiveSnapshot | None = None
        self._counters = FeedCounters()
        self._loaded = False

    async def _load(self) -> None:
        # Resume after a restart: diff against what replicas already serve, keep counters and the ETag.
        self._previous = await self._store.load_snapshot()
        self._counters = await self._store.load_counters() or FeedCounters()
        self._loaded = True

    async def __call__(self) -> PollOutcome:
        if not self._loaded:
            await self._load()
        c = self._counters
        c.polls += 1
        c.last_poll_ms = epoch_ms(self._clock)
        try:
            result = await self._feed.fetch(c.etag)
        except Exception as e:
            c.last_error = f"{type(e).__name__}: {e}"
            await self._store.save_counters(c)
            raise
        prev_session = self._previous.session if self._previous else None
        if result.snapshot is None:  # 304: upstream has nothing new
            c.not_modified += 1
            c.last_ok_ms, c.last_error = epoch_ms(self._clock), None
            c.poll_interval_s = self._policy.interval(prev_session)
            await self._store.save_counters(c)
            return PollOutcome(not_modified=True, session=prev_session)

        snap = result.snapshot
        received = epoch_ms(self._clock)
        changes = snap.changes_since(self._previous)
        to_store = tuple(snap.quotes.values()) if changes.first else changes.quotes
        await self._store.save_snapshot(snap, to_store, full=changes.first)
        events = self._events(snap, changes.quotes, changes.market_changed, received)
        published = await self._publisher.publish(events) if events else []
        if changes.any:
            c.changes += 1
            c.last_change_ms = received
        await self._record_ticks(snap, to_store, received)

        self._previous = snap
        c.etag = result.etag
        c.last_ok_ms, c.last_error = epoch_ms(self._clock), None
        c.symbols, c.market_open, c.trade_time = len(snap.quotes), snap.session.is_open, snap.trade_time
        c.poll_interval_s = self._policy.interval(snap.session)
        await self._store.save_counters(c)
        return PollOutcome(
            not_modified=False,
            session=snap.session,
            first=changes.first,
            changed=tuple(q.symbol.value for q in changes.quotes),
            market_changed=changes.market_changed,
            published=len(published),
        )

    @staticmethod
    def _events(
        snap: LiveSnapshot, quotes: Sequence[Any], market_changed: bool, received: int
    ) -> list[FeedEvent]:
        events = [
            FeedEvent(
                event="quote",
                symbol=q.symbol.value,
                data=quote_dto(q, snap.trade_time).model_dump(mode="json"),
                received_ms=received,
            )
            for q in quotes
        ]
        if market_changed:
            events.append(
                FeedEvent(
                    event="market",
                    symbol=None,
                    data=market_dto(snap.state).model_dump(mode="json"),
                    received_ms=received,
                )
            )
        return events

    async def _record_ticks(self, snap: LiveSnapshot, quotes: Sequence[Any], ts_ms: int) -> None:
        ticks = [Tick.of(q, ts_ms, snap.trade_time) for q in quotes if q.volume > 0]
        if not ticks:
            return
        try:
            async with self._uow() as uow:
                await uow.ticks.record(ticks)
                await uow.commit()
        except Exception as e:  # ticks feed intraday charts; they must never stall live delivery
            log.warning("tick recording failed", extra={"error": f"{type(e).__name__}: {e}"})
            self._counters.last_error = f"ticks: {type(e).__name__}: {e}"


Hook = Callable[[PollOutcome], Awaitable[None]]
Wait = Callable[[asyncio.Event, float], Awaitable[None]]


async def wait_or_stop(stop: asyncio.Event, delay: float) -> None:
    """Sleep `delay` seconds, returning early when `stop` is set (prompt, clean shutdown)."""
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=delay)


class RunFeed:
    """The poll loop: session-aware interval, exponential backoff on failure, hooks after each poll."""

    def __init__(
        self,
        poll: Callable[[], Awaitable[PollOutcome]],
        policy: PollPolicy,
        hooks: Sequence[Hook] = (),
        wait: Wait = wait_or_stop,
    ) -> None:
        self._poll, self._policy, self._hooks, self._wait = poll, policy, list(hooks), wait

    async def run(self, stop: asyncio.Event) -> None:
        backoff = 0.0
        session = None
        while not stop.is_set():
            try:
                outcome = await self._poll()
                session = outcome.session or session
                backoff = 0.0
                for hook in self._hooks:
                    try:
                        await hook(outcome)
                    except Exception:  # one failing consumer must not stop the feed
                        log.exception(
                            "feed hook failed", extra={"hook": getattr(hook, "__name__", repr(hook))}
                        )
            except UpstreamForbiddenError as e:
                backoff = self._policy.forbidden_s
                log.error("upstream refuses this client", extra={"error": str(e), "retry_in_s": backoff})
            except Exception as e:
                backoff = self._policy.next_backoff(backoff)
                log.warning(
                    "live poll failed", extra={"error": f"{type(e).__name__}: {e}", "backoff_s": backoff}
                )
            await self._wait(stop, self._policy.interval(session) + backoff)


class EndOfDayTrigger:
    """After the close, run `action` (market_data's AppendEndOfDay) exactly once per session date,
    across worker restarts and replicas. A failed action releases the claim so the next poll retries."""

    def __init__(self, action: Callable[[], Awaitable[object]], guard: OnceGuard, clock: Clock) -> None:
        self._action, self._guard, self._clock = action, guard, clock

    async def __call__(self, outcome: PollOutcome) -> None:
        s = outcome.session
        if s is None or s.day is None or not s.is_after_close(self._clock.now()):
            return
        key = f"eod:{s.day.isoformat()}"
        if not await self._guard.claim(key, ttl_s=4 * 86_400):
            return
        try:
            report = await self._action()
        except Exception:
            await self._guard.release(key)
            raise
        log.info("end-of-day bars written", extra={"session": s.day.isoformat(), "report": str(report)})


class GetQuotes:
    def __init__(self, store: LiveStateStore) -> None:
        self._store = store

    async def __call__(self, symbols: Sequence[str] | None = None) -> list[QuoteDto]:
        market = await self._store.market()
        if market is None:
            raise ServiceNotReadyError("The live feed has not received a snapshot yet.")
        return [quote_dto(q, market.trade_time) for q in await self._store.quotes(symbols)]


class GetMarket:
    def __init__(self, store: LiveStateStore) -> None:
        self._store = store

    async def __call__(self) -> MarketDto:
        market = await self._store.market()
        if market is None:
            raise ServiceNotReadyError("The live feed has not received a snapshot yet.")
        return market_dto(market)


class GetFeedStatus:
    def __init__(self, store: LiveStateStore, clock: Clock, stale_after_s: float) -> None:
        self._store, self._clock, self._stale_ms = store, clock, int(stale_after_s * 1000)

    async def __call__(self) -> FeedStatusDto:
        return feed_status_dto(await self._store.load_counters(), epoch_ms(self._clock), self._stale_ms)


MoverKind = Literal["gainers", "losers", "value", "volume", "trades"]
_MOVER_KEY: dict[str, str] = {
    "gainers": "percent",
    "losers": "percent",
    "value": "value_mn",
    "volume": "volume",
    "trades": "trades",
}


class GetMovers:
    """Top gainers / losers / most active among instruments that have traded today."""

    def __init__(self, store: LiveStateStore) -> None:
        self._store = store

    async def __call__(
        self, by: MoverKind = "gainers", limit: int = 20, asset_types: Sequence[str] | None = ("EQ",)
    ) -> list[QuoteDto]:
        market = await self._store.market()
        if market is None:
            raise ServiceNotReadyError("The live feed has not received a snapshot yet.")
        quotes = [
            q
            for q in await self._store.quotes()
            if q.volume > 0 and (asset_types is None or q.asset_type in asset_types)
        ]
        key = _MOVER_KEY[by]
        quotes.sort(key=lambda q: getattr(q, key) or 0, reverse=by != "losers")
        return [quote_dto(q, market.trade_time) for q in quotes[:limit]]


class BroadcastEvent:
    """Let another feature tell SSE clients something happened (e.g. the scanner universe was rebuilt)."""

    def __init__(self, publisher: EventPublisher, clock: Clock) -> None:
        self._publisher, self._clock = publisher, clock

    async def __call__(self, event: str, data: dict[str, Any]) -> None:
        await self._publisher.publish(
            [FeedEvent(event=event, symbol=None, data=data, received_ms=epoch_ms(self._clock))]
        )


class GetMinuteBars:
    """1-minute bars of one instrument for a trading day, built from the ticks the worker recorded."""

    def __init__(self, uow: UowFactory, clock: Clock, tz: tzinfo) -> None:
        self._uow, self._clock, self._tz = uow, clock, tz

    async def __call__(self, symbol: Symbol, day: date | None = None) -> list[MinuteBar]:
        day = day or self._clock.today()
        start = datetime.combine(day, time.min, tzinfo=self._tz)
        async with self._uow() as uow:
            ticks = await uow.ticks.between(
                symbol, int(start.timestamp() * 1000), int((start + timedelta(days=1)).timestamp() * 1000)
            )
        return minute_bars(ticks, self._tz)
