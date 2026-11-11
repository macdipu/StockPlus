"""Dependency providers.

Build use cases from the process-wide resources the composition root placed on app.state.
"""

from dataclasses import dataclass

from fastapi import Request

from dse.core.db import Database
from dse.features.market_data.application.facade import MarketDataFacade
from dse.features.market_data.application.use_cases import (
    AppendEndOfDay,
    EnsureFresh,
    GetAnnouncements,
    GetCandles,
    GetInstrumentProfile,
    SyncInstrument,
)
from dse.features.market_data.domain.ports import MarketDataSource, MarketDataUnitOfWork
from dse.features.market_data.infrastructure.uow import SqlMarketDataUnitOfWork
from dse.shared_kernel.clock import Clock


@dataclass(frozen=True)
class MarketDataContainer:
    """Explicit DI container for this feature (no service locator, no globals)."""

    db: Database
    source: MarketDataSource
    clock: Clock

    def uow(self) -> MarketDataUnitOfWork:
        return SqlMarketDataUnitOfWork(self.db.sessions)

    @property
    def sync(self) -> SyncInstrument:
        return SyncInstrument(self.uow, self.source)

    @property
    def ensure_fresh(self) -> EnsureFresh:
        return EnsureFresh(self.uow, self.sync, self.clock)

    @property
    def get_profile(self) -> GetInstrumentProfile:
        return GetInstrumentProfile(self.uow, self.ensure_fresh)

    @property
    def get_candles(self) -> GetCandles:
        return GetCandles(self.uow, self.ensure_fresh)

    @property
    def facade(self) -> MarketDataFacade:
        return MarketDataFacade(self.get_candles, self.get_profile, self.get_announcements)

    @property
    def append_end_of_day(self) -> AppendEndOfDay:
        return AppendEndOfDay(self.uow, self.source)

    @property
    def get_announcements(self) -> GetAnnouncements:
        return GetAnnouncements(self.uow, self.ensure_fresh)


def container(request: Request) -> MarketDataContainer:
    c: MarketDataContainer = request.app.state.market_data
    return c
