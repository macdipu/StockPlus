"""SQLAlchemy implementations of the live-feed ports, and the Unit of Work exposing them."""

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dse.core.db import SqlAlchemyUnitOfWork
from dse.features.live_feed.domain.entities import Tick
from dse.features.live_feed.infrastructure.orm import TickRow
from dse.shared_kernel.symbol import Symbol

_CHUNK = 1000


def _dec(v: float | None) -> Decimal | None:
    return Decimal(str(v)) if v is not None else None


class SqlTickRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def between(self, symbol: Symbol, start_ms: int, end_ms: int) -> list[Tick]:
        rows = await self._s.scalars(
            select(TickRow)
            .where(
                TickRow.symbol == symbol.value,
                TickRow.ts >= datetime.fromtimestamp(start_ms / 1000, UTC),
                TickRow.ts < datetime.fromtimestamp(end_ms / 1000, UTC),
            )
            .order_by(TickRow.ts)
        )
        return [
            Tick(
                symbol,
                int(r.ts.timestamp() * 1000),
                r.trade_time,
                float(r.ltp) if r.ltp is not None else None,
                float(r.high) if r.high is not None else None,
                float(r.low) if r.low is not None else None,
                int(r.volume),
                float(r.value_mn) if r.value_mn is not None else None,
                r.trades,
            )
            for r in rows
        ]

    async def record(self, ticks: Sequence[Tick]) -> int:
        written = 0
        rows = [
            {
                "symbol": t.symbol.value,
                "ts": datetime.fromtimestamp(t.ts_ms / 1000, UTC),
                "trade_time": t.trade_time,
                "ltp": _dec(t.ltp),
                "high": _dec(t.high),
                "low": _dec(t.low),
                "volume": t.volume,
                "value_mn": _dec(t.value_mn),
                "trades": t.trades,
            }
            for t in ticks
        ]
        for i in range(0, len(rows), _CHUNK):
            stmt = insert(TickRow).values(rows[i : i + _CHUNK]).on_conflict_do_nothing()
            result = await self._s.execute(stmt)
            written += int(getattr(result, "rowcount", 0) or 0)
        return written


class SqlLiveFeedUnitOfWork(SqlAlchemyUnitOfWork):
    ticks: SqlTickRepository

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.ticks = SqlTickRepository(self.session)
        return self
