"""SQLAlchemy Unit of Work exposing the market-data repositories on one session/transaction."""

from typing import Self

from dse.core.db import SqlAlchemyUnitOfWork
from dse.features.market_data.infrastructure.repositories import (
    SqlAnnouncementRepository,
    SqlBarRepository,
    SqlFundamentalsRepository,
    SqlInstrumentRepository,
)


class SqlMarketDataUnitOfWork(SqlAlchemyUnitOfWork):
    instruments: SqlInstrumentRepository
    fundamentals: SqlFundamentalsRepository
    bars: SqlBarRepository
    announcements: SqlAnnouncementRepository

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.instruments = SqlInstrumentRepository(self.session)
        self.fundamentals = SqlFundamentalsRepository(self.session)
        self.bars = SqlBarRepository(self.session)
        self.announcements = SqlAnnouncementRepository(self.session)
        return self
