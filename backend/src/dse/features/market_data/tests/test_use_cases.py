from dataclasses import replace
from datetime import timedelta

import pytest

from dse.features.market_data.application.use_cases import (
    AppendEndOfDay,
    BackfillUniverse,
    EnsureFresh,
    GetCandles,
    GetHistorySignature,
    GetInstrumentProfile,
    GetMarketHistory,
    SyncInstrument,
)
from dse.features.market_data.domain.entities import BarSource, CompanyPage, MarketSnapshot
from dse.features.market_data.tests.fakes import NOW, FakeClock, FakeSource, FakeUow, Store
from dse.shared_kernel.errors import NotFoundError
from dse.shared_kernel.symbol import Symbol

ORION = Symbol("ORIONINFU")


def wire(
    store: Store, page: CompanyPage, snapshot: MarketSnapshot | None = None, clock: FakeClock | None = None
) -> tuple[FakeSource, SyncInstrument, EnsureFresh]:
    src = FakeSource({"ORIONINFU": page}, snapshot)
    sync = SyncInstrument(lambda: FakeUow(store), src)
    return src, sync, EnsureFresh(lambda: FakeUow(store), sync, clock or FakeClock())


async def test_sync_persists_everything_atomically(store: Store, page: CompanyPage) -> None:
    _, sync, _ = wire(store, page)
    report = await sync(ORION)
    assert report.bars == 260
    assert len(store.bars) == 260
    assert "ORIONINFU" in store.fundamentals
    assert store.instruments["ORIONINFU"][1] == NOW


async def test_profile_reads_through_once_then_serves_from_store(store: Store, page: CompanyPage) -> None:
    src, _, fresh = wire(store, page)
    get = GetInstrumentProfile(lambda: FakeUow(store), fresh)
    p1 = await get(ORION)
    p2 = await get(ORION)
    assert src.calls == 1
    assert p1 == p2
    assert p1.last_close == float(page.bars[-1].close)
    assert p1.fundamentals.eps_ttm == pytest.approx(1.43)


async def test_stale_instrument_is_resynced_next_day(store: Store, page: CompanyPage) -> None:
    src, _, fresh = wire(store, page)
    await fresh(ORION)
    tomorrow = EnsureFresh(
        lambda: FakeUow(store),
        SyncInstrument(lambda: FakeUow(store), src),
        FakeClock(NOW + timedelta(days=1)),
    )
    await tomorrow(ORION)
    assert src.calls == 2


async def test_unknown_symbol_is_not_found(store: Store, page: CompanyPage) -> None:
    _, _, fresh = wire(store, page)
    with pytest.raises(NotFoundError):
        await GetCandles(lambda: FakeUow(store), fresh)(Symbol("NOPE"), 10)


async def test_backfill_skips_fresh_and_reports_failures(
    store: Store, page: CompanyPage, snapshot: MarketSnapshot
) -> None:
    src, sync, _ = wire(store, page, snapshot)
    report = await BackfillUniverse(lambda: FakeUow(store), src, sync, FakeClock())([ORION, Symbol("NOPE")])
    assert report.synced == 1
    assert list(report.failed) == ["NOPE"]
    again = await BackfillUniverse(lambda: FakeUow(store), src, sync, FakeClock())([ORION])
    assert again.skipped_fresh == 1
    assert again.synced == 0


async def test_end_of_day_never_overwrites_page_bars(
    store: Store, page: CompanyPage, snapshot: MarketSnapshot
) -> None:
    last = page.bars[-1]
    closed = replace(snapshot, is_open=False, trading_day=True, session_date=last.day)
    src, sync, _ = wire(store, page, closed)
    await sync(ORION)
    report = await AppendEndOfDay(lambda: FakeUow(store), src)()
    assert report.bars_written > 300
    assert report.asset_types_updated == 1  # the only instrument we hold a row for learns its type
    assert store.instruments["ORIONINFU"][0].asset_type == "EQ"
    assert store.bars[("ORIONINFU", last.day)].source == BarSource.PAGE  # official bar kept
    other = next(k for k in store.bars if k[0] != "ORIONINFU")
    assert store.bars[other].source == BarSource.SNAPSHOT


async def test_end_of_day_skips_while_open(store: Store, page: CompanyPage, snapshot: MarketSnapshot) -> None:
    src, _, _ = wire(store, page, replace(snapshot, is_open=True))
    report = await AppendEndOfDay(lambda: FakeUow(store), src)()
    assert report.bars_written == 0
    assert report.skipped_reason == "market open"


async def test_market_history_returns_every_instrument_with_its_fundamentals(
    store: Store, page: CompanyPage
) -> None:
    _, sync, _ = wire(store, page)
    await sync(ORION)
    hist = await GetMarketHistory(lambda: FakeUow(store))(bars=50)
    assert [h.symbol for h in hist] == ["ORIONINFU"]
    h = hist[0]
    assert len(h.bars) == 50
    assert h.bars[-1].day == page.bars[-1].day  # the most recent 50, oldest first
    assert h.bars[0].day < h.bars[-1].day
    assert h.name == page.instrument.name
    assert h.fundamentals is not None
    assert h.fundamentals.eps_ttm == pytest.approx(1.43)
    assert h.fundamentals.pe == pytest.approx(h.bars[-1].close / 1.43)  # P/E at the last close


async def test_history_signature_changes_when_history_does(
    store: Store, page: CompanyPage, snapshot: MarketSnapshot
) -> None:
    sig = GetHistorySignature(lambda: FakeUow(store))
    empty = await sig()
    assert (empty.bars, empty.last_bar_day, empty.fundamentals) == (0, None, 0)
    last = page.bars[-1]
    closed = replace(
        snapshot, is_open=False, trading_day=True, session_date=last.day.replace(year=last.day.year + 1)
    )
    src, sync, _ = wire(store, page, closed)
    await sync(ORION)
    first = await sig()
    assert (first.bars, first.last_bar_day, first.fundamentals) == (260, last.day, 1)
    assert await sig() == first  # reading never changes it
    await AppendEndOfDay(lambda: FakeUow(store), src)()
    assert await sig() != first  # the end-of-day bars changed history
