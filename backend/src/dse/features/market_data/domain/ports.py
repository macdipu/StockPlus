"""Ports the market-data application needs. Implemented in infrastructure; faked in tests."""

from collections.abc import Sequence
from datetime import datetime
from types import TracebackType
from typing import Protocol

from dse.features.market_data.domain.entities import (
    Announcement,
    CompanyPage,
    DailyBar,
    Fundamentals,
    Instrument,
    MarketSnapshot,
)
from dse.shared_kernel.symbol import Symbol


class MarketDataSource(Protocol):
    async def company_page(self, symbol: Symbol) -> CompanyPage: ...

    async def market_snapshot(self) -> MarketSnapshot: ...


class InstrumentRepository(Protocol):
    async def get(self, symbol: Symbol) -> Instrument | None: ...

    async def upsert(self, instrument: Instrument, synced_at: datetime) -> None: ...

    async def synced_at(self, symbol: Symbol) -> datetime | None: ...

    async def synced_since(self, since: datetime) -> set[str]: ...

    async def count(self) -> int: ...


class FundamentalsRepository(Protocol):
    async def get(self, symbol: Symbol) -> Fundamentals | None: ...

    async def save(self, symbol: Symbol, fundamentals: Fundamentals, as_of: datetime) -> None: ...


class BarRepository(Protocol):
    async def upsert(self, bars: Sequence[DailyBar]) -> int:
        """Insert or update; a SNAPSHOT bar never overwrites a PAGE bar. Returns rows written."""
        ...

    async def latest(self, symbol: Symbol, limit: int) -> list[DailyBar]:
        """Most recent `limit` bars in ascending date order."""
        ...

    async def count(self) -> int: ...


class AnnouncementRepository(Protocol):
    async def upsert(self, items: Sequence[Announcement]) -> None: ...

    async def latest(self, symbol: Symbol, limit: int) -> list[Announcement]: ...


class MarketDataUnitOfWork(Protocol):
    """Read-only members, so implementations may expose concrete repository subtypes (covariance)."""

    @property
    def instruments(self) -> InstrumentRepository: ...

    @property
    def fundamentals(self) -> FundamentalsRepository: ...

    @property
    def bars(self) -> BarRepository: ...

    @property
    def announcements(self) -> AnnouncementRepository: ...

    async def __aenter__(self) -> "MarketDataUnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...
