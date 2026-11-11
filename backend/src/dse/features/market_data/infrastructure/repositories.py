"""SQLAlchemy implementations of the market-data repository ports."""

import dataclasses
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dse.features.market_data.domain.entities import (
    Announcement,
    BarSource,
    DailyBar,
    Dividend,
    EpsReport,
    Fundamentals,
    Instrument,
    ShareholdingPattern,
)
from dse.features.market_data.infrastructure.orm import (
    AnnouncementRow,
    DailyBarRow,
    FundamentalsRow,
    InstrumentRow,
)
from dse.shared_kernel.symbol import Symbol

_CHUNK = 1000


class SqlInstrumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, symbol: Symbol) -> Instrument | None:
        r = await self._s.get(InstrumentRow, symbol.value)
        if r is None:
            return None
        return Instrument(Symbol(r.symbol), r.name, r.sector, r.category, r.board, r.asset_type, r.isin)

    async def upsert(self, instrument: Instrument, synced_at: datetime) -> None:
        values = {
            "symbol": instrument.symbol.value,
            "name": instrument.name,
            "sector": instrument.sector,
            "category": instrument.category,
            "board": instrument.board,
            "isin": instrument.isin,
            "synced_at": synced_at,
        }
        stmt = insert(InstrumentRow).values(**values, asset_type=instrument.asset_type)
        update: dict[str, Any] = {k: stmt.excluded[k] for k in values if k != "symbol"}
        if instrument.asset_type is not None:  # pages don't carry it; never erase what the snapshot told us
            update["asset_type"] = stmt.excluded.asset_type
        update["updated_at"] = func.now()
        await self._s.execute(stmt.on_conflict_do_update(index_elements=["symbol"], set_=update))

    async def synced_at(self, symbol: Symbol) -> datetime | None:
        return await self._s.scalar(
            select(InstrumentRow.synced_at).where(InstrumentRow.symbol == symbol.value)
        )

    async def synced_since(self, since: datetime) -> set[str]:
        rows = await self._s.scalars(select(InstrumentRow.symbol).where(InstrumentRow.synced_at >= since))
        return set(rows)

    async def count(self) -> int:
        return int(await self._s.scalar(select(func.count()).select_from(InstrumentRow)) or 0)


def _fund_to_json(f: Fundamentals) -> dict[str, Any]:
    return dataclasses.asdict(f)


def _fund_from_json(d: dict[str, Any]) -> Fundamentals:
    return Fundamentals(
        **{
            **d,
            "eps": EpsReport(**d["eps"]),
            "shareholding": ShareholdingPattern(**d["shareholding"]),
            "dividends": tuple(Dividend(**x) for x in d["dividends"]),
        }
    )


class SqlFundamentalsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, symbol: Symbol) -> Fundamentals | None:
        r = await self._s.get(FundamentalsRow, symbol.value)
        return _fund_from_json(r.data) if r else None

    async def save(self, symbol: Symbol, fundamentals: Fundamentals, as_of: datetime) -> None:
        stmt = insert(FundamentalsRow).values(
            symbol=symbol.value, as_of=as_of, data=_fund_to_json(fundamentals)
        )
        await self._s.execute(
            stmt.on_conflict_do_update(
                index_elements=["symbol"],
                set_={"as_of": stmt.excluded.as_of, "data": stmt.excluded.data, "updated_at": func.now()},
            )
        )


class SqlBarRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert(self, bars: Sequence[DailyBar]) -> int:
        written = 0
        for i in range(0, len(bars), _CHUNK):
            chunk = bars[i : i + _CHUNK]
            stmt = insert(DailyBarRow).values(
                [
                    {
                        "symbol": b.symbol.value,
                        "day": b.day,
                        "open": b.open,
                        "high": b.high,
                        "low": b.low,
                        "close": b.close,
                        "volume": b.volume,
                        "trades": b.trades,
                        "source": b.source,
                    }
                    for b in chunk
                ]
            )
            cols = ("open", "high", "low", "close", "volume", "trades", "source")
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "day"],
                set_={**{c: stmt.excluded[c] for c in cols}, "updated_at": func.now()},
                # domain rule (BarSource docstring): our snapshot copy never overwrites DSE's official bar
                where=(DailyBarRow.source != BarSource.PAGE) | (stmt.excluded.source == BarSource.PAGE),
            )
            res = await self._s.execute(stmt)
            written += int(getattr(res, "rowcount", 0) or 0)
        return written

    async def latest(self, symbol: Symbol, limit: int) -> list[DailyBar]:
        rows = (
            await self._s.scalars(
                select(DailyBarRow)
                .where(DailyBarRow.symbol == symbol.value)
                .order_by(DailyBarRow.day.desc())
                .limit(limit)
            )
        ).all()
        return [
            DailyBar(symbol, r.day, r.open, r.high, r.low, r.close, r.volume, r.trades, r.source)
            for r in reversed(rows)
        ]

    async def count(self) -> int:
        return int(await self._s.scalar(select(func.count()).select_from(DailyBarRow)) or 0)


class SqlAnnouncementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert(self, items: Sequence[Announcement]) -> None:
        if not items:
            return
        stmt = insert(AnnouncementRow).values(
            [
                {
                    "id": a.id,
                    "symbol": a.symbol.value,
                    "published_on": a.published_on,
                    "kind": a.kind,
                    "title": a.title,
                    "body": a.body,
                }
                for a in items
            ]
        )
        await self._s.execute(stmt.on_conflict_do_nothing(index_elements=["id"]))

    async def latest(self, symbol: Symbol, limit: int) -> list[Announcement]:
        rows = (
            await self._s.scalars(
                select(AnnouncementRow)
                .where(AnnouncementRow.symbol == symbol.value)
                .order_by(AnnouncementRow.published_on.desc().nulls_last(), AnnouncementRow.id.desc())
                .limit(limit)
            )
        ).all()
        return [Announcement(r.id, symbol, r.published_on, r.kind, r.title, r.body) for r in rows]
