"""In-memory test doubles that satisfy the market-data ports."""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date, datetime
from types import TracebackType
from typing import Any, Self

from dse.core.clock import DHAKA
from dse.features.market_data.domain.entities import (
    Announcement,
    BarSource,
    CompanyPage,
    DailyBar,
    Fundamentals,
    Instrument,
    MarketSnapshot,
)
from dse.shared_kernel.errors import NotFoundError
from dse.shared_kernel.symbol import Symbol

NOW = datetime(2026, 11, 11, 11, 40, tzinfo=DHAKA)


class FakeClock:
    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()


class FakeSource:
    def __init__(self, pages: dict[str, CompanyPage], snapshot: MarketSnapshot | None = None) -> None:
        self.pages, self.snapshot, self.calls = pages, snapshot, 0

    async def company_page(self, symbol: Symbol) -> CompanyPage:
        self.calls += 1
        if symbol.value not in self.pages:
            raise NotFoundError(f"{symbol} is not a DSE trading code")
        return self.pages[symbol.value]

    async def market_snapshot(self) -> MarketSnapshot:
        assert self.snapshot is not None
        return self.snapshot


class Store:
    def __init__(self) -> None:
        self.instruments: dict[str, tuple[Instrument, datetime]] = {}
        self.fundamentals: dict[str, Fundamentals] = {}
        self.bars: dict[tuple[str, date], DailyBar] = {}
        self.news: dict[str, Announcement] = {}


class FakeUow:
    """Same contract as SqlMarketDataUnitOfWork, backed by dicts; changes visible only after commit."""

    def __init__(self, store: Store) -> None:
        self._store, self.committed = store, False
        outer = self

        class Instruments:
            async def get(self, s: Symbol) -> Instrument | None:
                hit = store.instruments.get(s.value)
                return hit[0] if hit else None

            async def upsert(self, i: Instrument, at: datetime) -> None:
                outer._pending.append(lambda: store.instruments.__setitem__(i.symbol.value, (i, at)))

            async def synced_at(self, s: Symbol) -> datetime | None:
                hit = store.instruments.get(s.value)
                return hit[1] if hit else None

            async def synced_since(self, since: datetime) -> set[str]:
                return {k for k, (_, at) in store.instruments.items() if at >= since}

            async def count(self) -> int:
                return len(store.instruments)

            async def set_asset_types(self, types: Mapping[str, str]) -> int:
                hits = {
                    s: t
                    for s, t in types.items()
                    if s in store.instruments and store.instruments[s][0].asset_type != t
                }

                def apply() -> None:
                    for s, t in hits.items():
                        inst, at = store.instruments[s]
                        store.instruments[s] = (replace(inst, asset_type=t), at)

                outer._pending.append(apply)
                return len(hits)

        class Funds:
            async def get(self, s: Symbol) -> Fundamentals | None:
                return store.fundamentals.get(s.value)

            async def save(self, s: Symbol, f: Fundamentals, at: datetime) -> None:
                outer._pending.append(lambda: store.fundamentals.__setitem__(s.value, f))

        class Bars:
            async def upsert(self, bars: Sequence[DailyBar]) -> int:
                def apply() -> None:
                    for b in bars:
                        key = (b.symbol.value, b.day)
                        cur = store.bars.get(key)
                        if cur is None or cur.source != BarSource.PAGE or b.source == BarSource.PAGE:
                            store.bars[key] = b

                outer._pending.append(apply)
                return len(bars)

            async def latest(self, s: Symbol, limit: int) -> list[DailyBar]:
                return sorted((b for (k, _), b in store.bars.items() if k == s.value), key=lambda b: b.day)[
                    -limit:
                ]

            async def count(self) -> int:
                return len(store.bars)

        class News:
            async def upsert(self, items: Sequence[Announcement]) -> None:
                outer._pending.append(lambda: store.news.update({a.id: a for a in items}))

            async def latest(self, s: Symbol, limit: int) -> list[Announcement]:
                return [a for a in store.news.values() if a.symbol == s][:limit]

        self.instruments, self.fundamentals, self.bars, self.announcements = (
            Instruments(),
            Funds(),
            Bars(),
            News(),
        )
        self._pending: list[Any] = []

    async def __aenter__(self) -> Self:
        self._pending = []
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._pending = []

    async def commit(self) -> None:
        for fn in self._pending:
            fn()
        self._pending, self.committed = [], True
