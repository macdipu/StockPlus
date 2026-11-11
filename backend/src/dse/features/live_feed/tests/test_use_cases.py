"""Use cases against in-memory fakes: polling semantics, delivery guarantees, loop, EOD trigger, fan-out."""

import asyncio
from dataclasses import replace
from datetime import time

import pytest

from dse.features.live_feed.application.dto import PollOutcome, PublishedEvent
from dse.features.live_feed.application.hub import FeedHub
from dse.features.live_feed.application.use_cases import (
    EndOfDayTrigger,
    GetFeedStatus,
    GetMarket,
    GetQuotes,
    PollSnapshot,
    RunFeed,
)
from dse.features.live_feed.domain.entities import LiveSnapshot, PollPolicy, SessionState
from dse.features.live_feed.domain.ports import FetchResult
from dse.features.live_feed.tests.fakes import (
    FakeClock,
    FakeFeed,
    FakeGuard,
    FakeUow,
    MemoryBus,
    MemoryStore,
    TickLog,
    with_quote,
    with_trade_time,
)
from dse.shared_kernel.errors import ServiceNotReadyError, UpstreamUnavailableError

POLICY = PollPolicy()


def poller(
    feed: FakeFeed, store: MemoryStore, bus: MemoryBus, ticks: TickLog, clock: FakeClock | None = None
) -> PollSnapshot:
    return PollSnapshot(feed, store, bus, lambda: FakeUow(ticks), clock or FakeClock(), POLICY)


async def test_first_poll_stores_everything_and_publishes_nothing(snapshot: LiveSnapshot) -> None:
    store, bus, ticks = MemoryStore(), MemoryBus(), TickLog()
    out = await poller(FakeFeed(FetchResult(snapshot, '"v1"')), store, bus, ticks)()
    assert out.first
    assert out.published == 0
    assert not bus.published
    assert len(store.quote_map) == len(snapshot.quotes) == store.writes[0]
    assert len(ticks.rows) == sum(1 for q in snapshot.quotes.values() if q.volume > 0)
    assert store.counters is not None
    assert store.counters.etag == '"v1"'
    assert store.counters.symbols == 398


async def test_change_publishes_only_the_delta_and_sends_etag(snapshot: LiveSnapshot) -> None:
    store, bus, ticks = MemoryStore(), MemoryBus(), TickLog()
    nxt = with_trade_time(with_quote(snapshot, "GP", ltp=999.0, volume=10**7), "11:41")
    feed = FakeFeed(FetchResult(snapshot, '"v1"'), FetchResult(nxt, '"v2"'), FetchResult(None, '"v2"'))
    poll = poller(feed, store, bus, ticks)
    await poll()
    n_ticks = len(ticks.rows)
    out = await poll()
    assert out.changed == ("GP",)
    assert out.market_changed
    assert [(e.event, e.symbol) for e in bus.published] == [("quote", "GP"), ("market", None)]
    assert bus.published[0].data["ltp"] == 999.0
    assert bus.published[0].data["trade_time"] == "11:41"
    assert store.writes[-1] == 1  # only the delta is rewritten
    assert len(ticks.rows) == n_ticks + 1
    out = await poll()  # 304
    assert out.not_modified
    assert len(bus.published) == 2
    assert feed.etags == [None, '"v1"', '"v2"']
    c = store.counters
    assert c is not None
    assert (c.polls, c.not_modified, c.changes) == (3, 1, 1)


async def test_failed_publish_is_redelivered_next_poll(snapshot: LiveSnapshot) -> None:
    store, bus, ticks = MemoryStore(), MemoryBus(), TickLog()
    nxt = with_quote(snapshot, "GP", ltp=999.0)
    poll = poller(
        FakeFeed(FetchResult(snapshot, "a"), FetchResult(nxt, "b"), FetchResult(nxt, "b")), store, bus, ticks
    )
    await poll()
    bus.fail_next = 1
    with pytest.raises(ConnectionError):
        await poll()
    out = await poll()  # baseline did not advance → same change published again
    assert out.changed == ("GP",)
    assert [e.symbol for e in bus.published] == ["GP"]


async def test_tick_failure_never_blocks_delivery(snapshot: LiveSnapshot) -> None:
    store, bus = MemoryStore(), MemoryBus()
    poll = poller(
        FakeFeed(FetchResult(snapshot, "a"), FetchResult(with_quote(snapshot, "GP", ltp=1.0), "b")),
        store,
        bus,
        TickLog(fail=True),
    )
    await poll()
    out = await poll()
    assert out.published == 1
    assert store.counters is not None
    assert store.counters.last_error is None


async def test_upstream_error_is_recorded_and_raised(snapshot: LiveSnapshot) -> None:
    store = MemoryStore()
    poll = poller(FakeFeed(UpstreamUnavailableError("503")), store, MemoryBus(), TickLog())
    with pytest.raises(UpstreamUnavailableError):
        await poll()
    assert store.counters is not None
    assert "503" in (store.counters.last_error or "")


async def test_restarted_worker_resumes_from_shared_state(snapshot: LiveSnapshot) -> None:
    store, bus, ticks = MemoryStore(), MemoryBus(), TickLog()
    await poller(FakeFeed(FetchResult(snapshot, "a")), store, bus, ticks)()
    feed = FakeFeed(FetchResult(with_quote(snapshot, "GP", ltp=1.0), "b"))
    out = await poller(feed, store, bus, ticks)()  # a NEW instance, as after a restart
    assert not out.first
    assert out.changed == ("GP",)
    assert feed.etags == ["a"]  # resumed the ETag too
    assert store.counters is not None
    assert store.counters.polls == 2


async def test_read_side_queries(snapshot: LiveSnapshot) -> None:
    store, clock = MemoryStore(), FakeClock()
    with pytest.raises(ServiceNotReadyError):
        await GetQuotes(store)(["GP"])
    status = await GetFeedStatus(store, clock, 300)()
    assert not status.ready
    assert status.stale
    await poller(FakeFeed(FetchResult(snapshot, "a")), store, MemoryBus(), TickLog(), clock)()
    quotes = await GetQuotes(store)(["GP", "NOPE", "BATBC"])
    assert [q.symbol for q in quotes] == ["GP", "BATBC"]
    assert len(await GetQuotes(store)()) == 398
    assert (await GetMarket(store)()).session.is_open
    clock.advance(301)
    status = await GetFeedStatus(store, clock, 300)()
    assert status.ready
    assert status.stale
    assert status.last_success_age_ms == 301_000


# ---------------------------------------------------------------- loop


async def test_run_feed_backs_off_and_runs_hooks() -> None:
    results: list[PollOutcome | Exception] = [
        UpstreamUnavailableError("x"),
        UpstreamUnavailableError("x"),
        PollOutcome(not_modified=True, session=SessionState(None, False, True)),
    ]
    delays: list[float] = []
    stop = asyncio.Event()
    seen: list[PollOutcome] = []

    async def poll() -> PollOutcome:
        item = results.pop(0)
        if not results:
            stop.set()
        if isinstance(item, Exception):
            raise item
        return item

    async def hook(o: PollOutcome) -> None:
        seen.append(o)
        raise RuntimeError("a broken hook must not kill the loop")

    async def wait(_: asyncio.Event, delay: float) -> None:
        delays.append(delay)

    await RunFeed(poll, PollPolicy(open_s=10, closed_s=60, floor_s=0), hooks=[hook], wait=wait).run(stop)
    assert delays == [10 + 5, 10 + 10, 60]  # backoff on open interval, then closed interval after success
    assert len(seen) == 1


# ---------------------------------------------------------------- end of day


def closed_outcome(day_closing: time = time(14)) -> PollOutcome:
    clock = FakeClock()
    return PollOutcome(
        not_modified=True, session=SessionState(clock.today(), False, True, "closed", time(10), day_closing)
    )


async def test_end_of_day_runs_once_after_close_and_retries_failures() -> None:
    clock, guard, calls = FakeClock(), FakeGuard(), []

    async def action() -> str:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("upstream hiccup")
        return "ok"

    trigger = EndOfDayTrigger(action, guard, clock)
    await trigger(closed_outcome())  # 11:40 < 14:00 → not yet
    assert calls == []
    clock.advance(3 * 3600)  # 14:40
    with pytest.raises(RuntimeError):
        await trigger(closed_outcome())
    assert guard.claimed == set()  # released for a retry
    await trigger(closed_outcome())
    await trigger(closed_outcome())
    assert len(calls) == 2
    assert guard.claimed == {f"eod:{clock.today().isoformat()}"}
    open_ = replace(closed_outcome(), session=SessionState(clock.today(), True, True))
    await trigger(open_)
    assert len(calls) == 2


# ---------------------------------------------------------------- per-replica fan-out


def event(i: int, symbol: str | None, kind: str = "quote") -> PublishedEvent:
    return PublishedEvent(event=kind, symbol=symbol, data={"i": i}, received_ms=0, id=i, published_ms=0)


async def test_hub_filters_and_drops_oldest_for_slow_clients() -> None:
    hub = FeedHub(MemoryBus(), queue_size=2)
    gp, everyone = hub.subscribe({"GP"}), hub.subscribe()
    for i, sym in enumerate(["GP", "BATBC", None, "GP"], start=1):
        hub.dispatch(event(i, sym, "market" if sym is None else "quote"))
    assert [gp.queue.get_nowait().id for _ in range(2)] == [3, 4]  # GP + market; oldest GP dropped
    assert gp.dropped == 1
    assert everyone.dropped == 2
    hub.unsubscribe(gp)
    assert hub.subscribers == 1
    assert hub.last_event_id == 4


async def test_hub_reconnects_after_bus_failure() -> None:
    bus = MemoryBus()
    hub = FeedHub(bus, retry_max_s=0.05)
    sub = hub.subscribe()
    task = asyncio.create_task(hub.run())
    try:
        for _ in range(100):
            await asyncio.sleep(0.01)
            if hub.connected:
                break
        await bus.publish([event(0, "GP")])  # ids re-assigned by the bus
        assert (await asyncio.wait_for(sub.queue.get(), 1)).id == 1
        bus.drop_connections()
        await asyncio.sleep(0)  # let the hub see the drop
        assert not hub.connected
        for _ in range(200):
            await asyncio.sleep(0.01)
            if hub.connected:
                break
        await bus.publish([event(0, "GP")])
        assert (await asyncio.wait_for(sub.queue.get(), 2)).id == 2
        assert hub.connected
    finally:
        task.cancel()
