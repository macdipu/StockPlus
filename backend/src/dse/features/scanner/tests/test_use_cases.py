"""Use cases on fakes: build caching, single-flight refresh, version-gated read cache, preset defaults."""

import asyncio
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import pytest

from dse.features.analysis.application.facade import QuoteInput, UniverseInput
from dse.features.scanner.application.use_cases import (
    GetPe,
    GetRange52w,
    GetSectors,
    GetTable,
    GetUniverseStatus,
    ListFields,
    ListPresets,
    MaterialiseUniverse,
    RunPreset,
    RunScan,
    UniverseRefresher,
)
from dse.features.scanner.application.view import UniverseView
from dse.features.scanner.domain.presets import PRESETS
from dse.features.scanner.domain.rules import Rule, ScanError, ScanSpec, Sort, UniverseFilter
from dse.features.scanner.tests.fakes import FakeClock, FakeSource, MemoryStore, Notifier
from dse.shared_kernel.errors import NotFoundError, ServiceNotReadyError

SUBSET = ["UP1", "UP2", "DOWN1", "HAMMER", "MFUND", "NOQUOTE", "ZCAT", "SHORT"]


@pytest.fixture
def source(history: list[UniverseInput], quotes: dict[str, QuoteInput], session_day: date) -> FakeSource:
    return FakeSource([h for h in history if h.symbol in SUBSET], quotes, session_day)


def materialiser(source: FakeSource, store: MemoryStore, notifier: Notifier) -> MaterialiseUniverse:
    return MaterialiseUniverse(source, store, notifier, FakeClock())


async def test_materialise_builds_both_views_and_publishes(source: FakeSource) -> None:
    store, notifier = MemoryStore(), Notifier()
    report = await materialiser(source, store, notifier)()
    assert (report.version, report.rows, report.errors, report.rebuilt_last_close) == (1, 8, 0, True)
    s = store.saved
    assert s is not None
    assert len(s.live_rows) == len(s.last_close_rows) == 8
    assert s.session_day == source.day
    assert s.trade_time == "11:40"
    live = {r["symbol"]: r for r in s.live_rows}
    last = {r["symbol"]: r for r in s.last_close_rows}
    assert live["UP1"]["ltp"] == source.quotes["UP1"].ltp  # live view merges the quote
    assert last["UP1"]["ltp"] == last["UP1"]["close"]  # last-close view ignores it
    assert notifier.events == [(1, 8)]


async def test_history_and_last_close_are_cached_until_they_could_change(source: FakeSource) -> None:
    m = materialiser(source, MemoryStore(), Notifier())
    assert (await m()).rebuilt_last_close
    again = await m()
    assert not again.rebuilt_last_close
    assert source.load_calls == 1  # same signature: history is not reloaded
    assert again.version == 2

    source.sig = (2,)  # a new bar / fundamentals were stored
    assert (await m()).rebuilt_last_close
    assert source.load_calls == 2

    source.day = source.day + timedelta(days=1)  # a new session day also changes "last completed session"
    assert (await m()).rebuilt_last_close


async def test_forced_rescan_reloads_history_even_when_nothing_changed(source: FakeSource) -> None:
    m = materialiser(source, MemoryStore(), Notifier())
    await m()
    assert (await m()).rebuilt_last_close is False
    report = await m(force=True)
    assert report.rebuilt_last_close
    assert source.load_calls == 2


async def test_notification_failure_does_not_undo_the_build(source: FakeSource) -> None:
    store = MemoryStore()
    report = await materialiser(source, store, Notifier(fail=True))()
    assert report.version == 1
    assert store.saved is not None


async def test_builds_without_quotes_when_the_feed_is_not_ready(source: FakeSource) -> None:
    source.ready = False
    store = MemoryStore()
    report = await materialiser(source, store, Notifier())()
    assert report.rows == 8  # still useful: stored history, no live bar
    assert store.saved is not None
    assert store.saved.session_day is None


async def test_one_bad_series_is_reported_not_fatal(source: FakeSource) -> None:
    broken = replace(source.items[0], fundamentals={"eps_ttm": "not a number", "nav": 5})
    source.items = [broken, *source.items[1:]]
    store = MemoryStore()
    report = await materialiser(source, store, Notifier())()
    assert report.errors == 1
    assert store.saved is not None
    assert broken.symbol in store.saved.errors
    assert report.rows == 7


# ---------------------------------------------------------------- single-flight refresher


async def test_refresher_collapses_triggers_into_one_extra_build() -> None:
    gate, calls = asyncio.Event(), []

    class SlowBuild:
        async def __call__(self, force: bool = False) -> None:
            calls.append(1)
            await gate.wait()

    r = UniverseRefresher(SlowBuild())  # type: ignore[arg-type]
    for _ in range(5):
        r.trigger()  # never blocks, never stacks
        await asyncio.sleep(0)
    assert len(calls) == 1
    gate.set()
    await r.join()
    assert len(calls) == 2  # one build + exactly one collapsed rebuild
    assert r.built_once
    r.trigger()
    await r.join()
    assert len(calls) == 3


async def test_refresher_survives_a_failing_build_and_closes_cleanly() -> None:
    n = 0

    class Flaky:
        async def __call__(self, force: bool = False) -> None:
            nonlocal n
            n += 1
            if n == 1:
                raise RuntimeError("db down")

    r = UniverseRefresher(Flaky())  # type: ignore[arg-type]
    r.trigger()
    await r.join()
    assert not r.built_once  # the failure was logged, not raised
    r.trigger()
    await r.join()
    assert r.built_once

    block = asyncio.Event()

    class Hang:
        async def __call__(self, force: bool = False) -> None:
            await block.wait()

    h = UniverseRefresher(Hang())
    h.trigger()
    await asyncio.sleep(0)
    await h.aclose()  # cancels a running build without raising


# ---------------------------------------------------------------- read side


@pytest.fixture
async def published(source: FakeSource) -> tuple[MemoryStore, UniverseView]:
    store = MemoryStore()
    await materialiser(source, store, Notifier())()
    return store, UniverseView(store)


async def test_view_reloads_only_when_the_version_changes(
    source: FakeSource, published: tuple[MemoryStore, UniverseView]
) -> None:
    store, view = published
    first = await view.current()
    assert (await view.current()) is first
    assert (await view.current()) is first
    assert store.loads == 1
    await materialiser(source, store, Notifier())()  # worker publishes version 2
    second = await view.current()
    assert second.version == 2
    assert second is not first
    assert store.loads == 2


async def test_view_concurrent_requests_share_one_reload(source: FakeSource) -> None:
    store = MemoryStore()
    await materialiser(source, store, Notifier())()
    view = UniverseView(store)
    results = await asyncio.gather(*[view.current() for _ in range(8)])
    assert store.loads == 1
    assert all(r is results[0] for r in results)


async def test_view_before_anything_is_published() -> None:
    view = UniverseView(MemoryStore())
    with pytest.raises(ServiceNotReadyError):
        await view.current()
    assert await view.peek() is None
    status = await GetUniverseStatus(view)()
    assert (status.ready, status.version, status.rows) == (False, None, 0)


async def test_status_after_publish(published: tuple[MemoryStore, UniverseView]) -> None:
    _, view = published
    st = await GetUniverseStatus(view)()
    assert (st.ready, st.version, st.rows, st.trade_time) == (True, 1, 8, "11:40")


async def test_run_scan_and_columns(published: tuple[MemoryStore, UniverseView]) -> None:
    _, view = published
    spec = ScanSpec((Rule("rsi14", "<", 100),), sort=Sort("symbol", False), limit=3)
    r = await RunScan(view)(spec, ["symbol", "ltp", "nope"], True)
    assert [x["symbol"] for x in r.rows] == ["DOWN1", "HAMMER", "MFUND"]
    assert set(r.rows[0]) == {"symbol", "ltp"}  # unknown columns are ignored
    assert (r.scanned, r.live, r.universe_version) == (8, True, 1)
    assert r.matched == 3
    with pytest.raises(ScanError):
        await RunScan(view)(ScanSpec((Rule("nope", ">", 1),)))


async def test_preset_defaults_follow_premarket_flag(published: tuple[MemoryStore, UniverseView]) -> None:
    _, view = published
    run = RunPreset(view)
    eq = UniverseFilter(asset_types=("EQ",))
    live_result, p = await run("rsi_oversold", eq)
    assert (live_result.live, p.premarket) == (True, False)
    pre_result, p = await run("nr7", eq)
    assert (pre_result.live, p.premarket) == (False, True)
    overridden, _ = await run("nr7", eq, live=True)
    assert overridden.live is True
    with pytest.raises(NotFoundError):
        await run("nope", eq)


async def test_catalogue_queries() -> None:
    presets = ListPresets()()
    assert len(presets) == len(PRESETS) == 41
    assert {p.group for p in presets} >= {
        "Trend",
        "Momentum",
        "Volatility",
        "Breakout",
        "Candles",
        "Fundamental",
    }
    f = ListFields()()
    assert "rsi14" in f.fields
    assert "crosses_above" in f.ops
    assert "symbol" in f.default_columns


async def test_market_analytics_over_the_published_universe(
    published: tuple[MemoryStore, UniverseView],
) -> None:
    _, view = published
    sectors: list[dict[str, Any]] = await GetSectors(view)()
    assert sum(s["instruments"] for s in sectors) == 8
    pe = await GetPe(view)()
    assert pe["market"]["instruments"] >= 1
    rng = await GetRange52w(view)("high", 3)
    assert len(rng) <= 3
    assert all(r["symbol"] != "MFUND" for r in rng)  # equities only
    table = await GetTable(view)(["symbol", "sector", "pe"], None)
    assert [t["symbol"] for t in table] == sorted(t["symbol"] for t in table)
    banks = await GetTable(view)(["symbol", "sector"], "Bank")
    assert banks
    assert {b["sector"] for b in banks} == {"Bank"}


async def test_on_poll_rebuilds_only_when_something_happened() -> None:
    builds = 0

    class Count:
        async def __call__(self, force: bool = False) -> None:
            nonlocal builds
            builds += 1

        async def history_changed(self) -> bool:
            return False

    r = UniverseRefresher(Count())  # type: ignore[arg-type]
    await r.on_poll(first=False, changed=False, market_changed=False)  # nothing built yet → build anyway
    await r.join()
    assert (builds, r.built_once) == (1, True)
    await r.on_poll(first=False, changed=False, market_changed=False)  # quiet tick
    await r.join()
    assert builds == 1
    for kwargs in ({"first": True}, {"changed": True}, {"market_changed": True}):
        await r.on_poll(**{"first": False, "changed": False, "market_changed": False, **kwargs})
        await r.join()
    assert builds == 4


async def test_history_changes_rebuild_even_when_the_market_is_quiet(source: FakeSource) -> None:
    """After hours there are no ticks, but a backfill/sync must still reach the scanners."""
    m = materialiser(source, MemoryStore(), Notifier())
    clock = [0.0]
    r = UniverseRefresher(m, check_every_s=30, monotonic=lambda: clock[0])
    quiet = {"first": False, "changed": False, "market_changed": False}
    await r.on_poll(**quiet)  # first build
    await r.join()
    assert source.load_calls == 1

    source.sig = (2,)  # a backfill stored more history …
    await r.on_poll(**quiet)  # … but the check is throttled
    await r.join()
    assert source.load_calls == 1
    clock[0] = 31.0
    await r.on_poll(**quiet)  # throttle elapsed → noticed → rebuilt with fresh history
    await r.join()
    assert source.load_calls == 2
    clock[0] = 62.0
    await r.on_poll(**quiet)  # unchanged since → nothing to do
    await r.join()
    assert source.load_calls == 2
