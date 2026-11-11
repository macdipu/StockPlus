"""Market-data use cases. Orchestration only: rules live in the domain, I/O behind ports."""

import logging
from collections.abc import Callable, Iterable
from datetime import timedelta

from dse.features.market_data.application.dto import (
    AnnouncementDto,
    BackfillReport,
    BarDto,
    EndOfDayReport,
    ProfileDto,
    SyncReport,
)
from dse.features.market_data.application.mappers import announcement_dto, bar_dto, fundamentals_dto
from dse.features.market_data.domain.ports import MarketDataSource, MarketDataUnitOfWork
from dse.shared_kernel.clock import Clock
from dse.shared_kernel.errors import DomainError, NotFoundError
from dse.shared_kernel.symbol import Symbol

log = logging.getLogger("dse.market_data")
UowFactory = Callable[[], MarketDataUnitOfWork]
TRADABLE_ASSET_TYPES = frozenset({"EQ", "MF"})


class SyncInstrument:
    """Fetch one company page and persist instrument, fundamentals, bars and announcements atomically."""

    def __init__(self, uow: UowFactory, source: MarketDataSource) -> None:
        self._uow, self._source = uow, source

    async def __call__(self, symbol: Symbol) -> SyncReport:
        page = await self._source.company_page(symbol)
        async with self._uow() as uow:
            await uow.instruments.upsert(page.instrument, page.fetched_at)
            await uow.fundamentals.save(symbol, page.fundamentals, page.fetched_at)
            written = await uow.bars.upsert(page.bars)
            await uow.announcements.upsert(page.announcements)
            await uow.commit()
        log.info("synced instrument", extra={"symbol": str(symbol), "bars": written})
        return SyncReport(symbol=str(symbol), bars=written, announcements=len(page.announcements))


class EnsureFresh:
    """Read-through: sync an instrument we have never seen, or whose page we last loaded before today."""

    def __init__(self, uow: UowFactory, sync: SyncInstrument, clock: Clock) -> None:
        self._uow, self._sync, self._clock = uow, sync, clock

    async def __call__(self, symbol: Symbol) -> None:
        async with self._uow() as uow:
            synced = await uow.instruments.synced_at(symbol)
        if synced is None or synced.date() < self._clock.today():
            await self._sync(symbol)


class GetInstrumentProfile:
    def __init__(self, uow: UowFactory, ensure_fresh: EnsureFresh) -> None:
        self._uow, self._fresh = uow, ensure_fresh

    async def __call__(self, symbol: Symbol) -> ProfileDto:
        await self._fresh(symbol)
        async with self._uow() as uow:
            inst = await uow.instruments.get(symbol)
            fund = await uow.fundamentals.get(symbol)
            last = await uow.bars.latest(symbol, 1)
            synced = await uow.instruments.synced_at(symbol)
        if inst is None or fund is None:
            raise NotFoundError(f"{symbol} is not a DSE trading code", symbol=str(symbol))
        price = float(last[-1].close) if last else None
        return ProfileDto(
            symbol=str(inst.symbol),
            name=inst.name,
            sector=inst.sector,
            category=inst.category,
            board=inst.board,
            asset_type=inst.asset_type,
            isin=inst.isin,
            last_close=price,
            last_bar_day=last[-1].day if last else None,
            synced_at=synced,
            fundamentals=fundamentals_dto(fund, price),
        )


class GetCandles:
    def __init__(self, uow: UowFactory, ensure_fresh: EnsureFresh) -> None:
        self._uow, self._fresh = uow, ensure_fresh

    async def __call__(self, symbol: Symbol, limit: int) -> list[BarDto]:
        await self._fresh(symbol)
        async with self._uow() as uow:
            bars = await uow.bars.latest(symbol, limit)
        return [bar_dto(b) for b in bars]


class GetAnnouncements:
    def __init__(self, uow: UowFactory, ensure_fresh: EnsureFresh) -> None:
        self._uow, self._fresh = uow, ensure_fresh

    async def __call__(self, symbol: Symbol, limit: int) -> list[AnnouncementDto]:
        await self._fresh(symbol)
        async with self._uow() as uow:
            items = await uow.announcements.latest(symbol, limit)
        return [announcement_dto(a) for a in items]


class BackfillUniverse:
    """Sync every tradable instrument, skipping those synced within `max_age`. Sequential by design:
    the source adapter spaces page loads, so this is polite to the exchange and resumable."""

    def __init__(
        self,
        uow: UowFactory,
        source: MarketDataSource,
        sync: SyncInstrument,
        clock: Clock,
        max_age: timedelta = timedelta(days=7),
    ) -> None:
        self._uow, self._source, self._sync, self._clock, self._max_age = uow, source, sync, clock, max_age

    async def __call__(
        self,
        symbols: Iterable[Symbol] | None = None,
        force: bool = False,
        progress: Callable[[int, int], None] | None = None,
    ) -> BackfillReport:
        if symbols is None:
            snap = await self._source.market_snapshot()
            wanted = sorted(
                (q.symbol for q in snap.quotes.values() if q.asset_type in TRADABLE_ASSET_TYPES), key=str
            )
        else:
            wanted = list(symbols)
        fresh: set[str] = set()
        if not force:
            async with self._uow() as uow:
                fresh = await uow.instruments.synced_since(self._clock.now() - self._max_age)
        todo = [s for s in wanted if str(s) not in fresh]
        failed: dict[str, str] = {}
        for i, sym in enumerate(todo, 1):
            try:
                await self._sync(sym)
            except DomainError as e:
                failed[str(sym)] = e.detail or type(e).__name__
            if progress:
                progress(i, len(todo))
        return BackfillReport(
            requested=len(wanted),
            skipped_fresh=len(wanted) - len(todo),
            synced=len(todo) - len(failed),
            failed=failed,
        )


class AppendEndOfDay:
    """After the close, write today's bar for every traded instrument from ONE snapshot request."""

    def __init__(self, uow: UowFactory, source: MarketDataSource) -> None:
        self._uow, self._source = uow, source

    async def __call__(self) -> EndOfDayReport:
        snap = await self._source.market_snapshot()
        bars = snap.end_of_day_bars()
        types = {s: q.asset_type for s, q in snap.quotes.items() if q.asset_type}
        async with self._uow() as uow:
            typed = await uow.instruments.set_asset_types(types)
            n = await uow.bars.upsert(bars) if bars else 0
            await uow.commit()
        if not bars:
            reason = "market open" if snap.is_open else "not a trading day or nothing traded"
            return EndOfDayReport(
                session_date=snap.session_date,
                bars_written=0,
                skipped_reason=reason,
                asset_types_updated=typed,
            )
        return EndOfDayReport(session_date=snap.session_date, bars_written=n, asset_types_updated=typed)
