"""SQLAlchemy implementations of the watchlists ports, and the Unit of Work exposing them."""

from typing import Self
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dse.core.db import SqlAlchemyUnitOfWork
from dse.features.watchlists.domain.entities import SavedScan, Watchlist
from dse.features.watchlists.infrastructure.orm import SavedScanRow, WatchlistRow
from dse.shared_kernel.errors import ConflictError


def _watchlist(r: WatchlistRow) -> Watchlist:
    return Watchlist(r.id, r.owner_id, r.name, r.name_key, tuple(r.symbols), r.created_at, r.updated_at)


def _scan(r: SavedScanRow) -> SavedScan:
    return SavedScan(r.id, r.owner_id, r.name, r.name_key, dict(r.definition), r.created_at, r.updated_at)


async def _flush_unique(session: AsyncSession, what: str) -> None:
    """Flush now so a duplicate name surfaces as ConflictError here, not as a 500 at commit."""
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        if "uq_" in str(e.orig):
            raise ConflictError(f"You already have a {what} with this name.") from e
        raise


class SqlWatchlistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list(self, owner_id: UUID) -> list[Watchlist]:
        rows = await self._s.scalars(
            select(WatchlistRow).where(WatchlistRow.owner_id == owner_id).order_by(WatchlistRow.created_at)
        )
        return [_watchlist(r) for r in rows]

    async def get(self, owner_id: UUID, watchlist_id: UUID) -> Watchlist | None:
        r = await self._s.scalar(
            select(WatchlistRow).where(WatchlistRow.id == watchlist_id, WatchlistRow.owner_id == owner_id)
        )
        return _watchlist(r) if r else None

    async def count(self, owner_id: UUID) -> int:
        return int(
            await self._s.scalar(
                select(func.count()).select_from(WatchlistRow).where(WatchlistRow.owner_id == owner_id)
            )
            or 0
        )

    async def add(self, w: Watchlist) -> None:
        self._s.add(
            WatchlistRow(
                id=w.id,
                owner_id=w.owner_id,
                name=w.name,
                name_key=w.name_key,
                symbols=list(w.symbols),
                created_at=w.created_at,
                updated_at=w.updated_at,
            )
        )
        await _flush_unique(self._s, "watchlist")

    async def update(self, w: Watchlist) -> None:
        r = await self._s.scalar(
            select(WatchlistRow).where(WatchlistRow.id == w.id, WatchlistRow.owner_id == w.owner_id)
        )
        if r is None:
            return
        r.name, r.name_key, r.symbols, r.updated_at = w.name, w.name_key, list(w.symbols), w.updated_at
        await _flush_unique(self._s, "watchlist")

    async def delete(self, owner_id: UUID, watchlist_id: UUID) -> bool:
        res = await self._s.execute(
            delete(WatchlistRow).where(WatchlistRow.id == watchlist_id, WatchlistRow.owner_id == owner_id)
        )
        return bool(getattr(res, "rowcount", 0))


class SqlSavedScanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list(self, owner_id: UUID) -> list[SavedScan]:
        rows = await self._s.scalars(
            select(SavedScanRow).where(SavedScanRow.owner_id == owner_id).order_by(SavedScanRow.created_at)
        )
        return [_scan(r) for r in rows]

    async def get(self, owner_id: UUID, scan_id: UUID) -> SavedScan | None:
        r = await self._s.scalar(
            select(SavedScanRow).where(SavedScanRow.id == scan_id, SavedScanRow.owner_id == owner_id)
        )
        return _scan(r) if r else None

    async def count(self, owner_id: UUID) -> int:
        return int(
            await self._s.scalar(
                select(func.count()).select_from(SavedScanRow).where(SavedScanRow.owner_id == owner_id)
            )
            or 0
        )

    async def add(self, s: SavedScan) -> None:
        self._s.add(
            SavedScanRow(
                id=s.id,
                owner_id=s.owner_id,
                name=s.name,
                name_key=s.name_key,
                definition=s.definition,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
        await _flush_unique(self._s, "saved scan")

    async def update(self, s: SavedScan) -> None:
        r = await self._s.scalar(
            select(SavedScanRow).where(SavedScanRow.id == s.id, SavedScanRow.owner_id == s.owner_id)
        )
        if r is None:
            return
        r.name, r.name_key, r.definition, r.updated_at = s.name, s.name_key, s.definition, s.updated_at
        await _flush_unique(self._s, "saved scan")

    async def delete(self, owner_id: UUID, scan_id: UUID) -> bool:
        res = await self._s.execute(
            delete(SavedScanRow).where(SavedScanRow.id == scan_id, SavedScanRow.owner_id == owner_id)
        )
        return bool(getattr(res, "rowcount", 0))


class SqlWatchlistsUnitOfWork(SqlAlchemyUnitOfWork):
    watchlists: SqlWatchlistRepository
    saved_scans: SqlSavedScanRepository

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.watchlists = SqlWatchlistRepository(self.session)
        self.saved_scans = SqlSavedScanRepository(self.session)
        return self
