"""Watchlist and saved-scan use cases. Every one takes the caller's `owner_id`; another user's resource is
reported as NotFound (never Forbidden), so ids reveal nothing."""

from collections.abc import Callable, Sequence
from typing import Any
from uuid import UUID, uuid4

from dse.features.watchlists.application.dto import SavedScanDto, WatchlistDto
from dse.features.watchlists.application.ports import ScanValidator, SymbolDirectory
from dse.features.watchlists.domain.entities import (
    MAX_SAVED_SCANS,
    MAX_WATCHLISTS,
    SavedScan,
    Watchlist,
    check_definition_size,
    clean_symbols,
    normalise_name,
)
from dse.features.watchlists.domain.ports import WatchlistsUnitOfWork
from dse.shared_kernel.clock import Clock
from dse.shared_kernel.errors import ConflictError, NotFoundError

UowFactory = Callable[[], WatchlistsUnitOfWork]


def watchlist_dto(w: Watchlist) -> WatchlistDto:
    return WatchlistDto(
        id=w.id, name=w.name, symbols=list(w.symbols), created_at=w.created_at, updated_at=w.updated_at
    )


def scan_dto(s: SavedScan) -> SavedScanDto:
    return SavedScanDto(
        id=s.id, name=s.name, definition=s.definition, created_at=s.created_at, updated_at=s.updated_at
    )


# ===================================================================================== watchlists
class ListWatchlists:
    def __init__(self, uow: UowFactory) -> None:
        self._uow = uow

    async def __call__(self, owner: UUID) -> list[WatchlistDto]:
        async with self._uow() as uow:
            return [watchlist_dto(w) for w in await uow.watchlists.list(owner)]


class GetWatchlist:
    def __init__(self, uow: UowFactory) -> None:
        self._uow = uow

    async def __call__(self, owner: UUID, watchlist_id: UUID) -> WatchlistDto:
        async with self._uow() as uow:
            w = await uow.watchlists.get(owner, watchlist_id)
        if w is None:
            raise NotFoundError("Watchlist not found.")
        return watchlist_dto(w)


class CreateWatchlist:
    def __init__(self, uow: UowFactory, directory: SymbolDirectory, clock: Clock) -> None:
        self._uow, self._directory, self._clock = uow, directory, clock

    async def __call__(self, owner: UUID, name: str, symbols: Sequence[str] = ()) -> WatchlistDto:
        display, key = normalise_name(name)
        codes = clean_symbols(list(symbols))
        await self._directory.ensure_known(codes)
        now = self._clock.now()
        w = Watchlist(uuid4(), owner, display, key, (), now, now).with_symbols(codes, now)
        async with self._uow() as uow:
            if await uow.watchlists.count(owner) >= MAX_WATCHLISTS:
                raise ConflictError(f"You can have at most {MAX_WATCHLISTS} watchlists.")
            await uow.watchlists.add(w)
            await uow.commit()
        return watchlist_dto(w)


class _Mutate:
    """Load → change → save one of the caller's watchlists inside a transaction."""

    def __init__(self, uow: UowFactory, clock: Clock) -> None:
        self._uow, self._clock = uow, clock

    async def _apply(
        self, owner: UUID, watchlist_id: UUID, change: Callable[[Watchlist], Watchlist]
    ) -> WatchlistDto:
        async with self._uow() as uow:
            w = await uow.watchlists.get(owner, watchlist_id)
            if w is None:
                raise NotFoundError("Watchlist not found.")
            w = change(w)
            await uow.watchlists.update(w)
            await uow.commit()
        return watchlist_dto(w)


class RenameWatchlist(_Mutate):
    async def __call__(self, owner: UUID, watchlist_id: UUID, name: str) -> WatchlistDto:
        now = self._clock.now()
        return await self._apply(owner, watchlist_id, lambda w: w.renamed(name, now))


class ReplaceSymbols(_Mutate):
    """Set the whole ordered list (also how a client reorders)."""

    def __init__(self, uow: UowFactory, directory: SymbolDirectory, clock: Clock) -> None:
        super().__init__(uow, clock)
        self._directory = directory

    async def __call__(self, owner: UUID, watchlist_id: UUID, symbols: Sequence[str]) -> WatchlistDto:
        codes = clean_symbols(list(symbols))
        await self._directory.ensure_known(codes)
        now = self._clock.now()
        return await self._apply(owner, watchlist_id, lambda w: w.with_symbols(codes, now))


class AddSymbols(_Mutate):
    def __init__(self, uow: UowFactory, directory: SymbolDirectory, clock: Clock) -> None:
        super().__init__(uow, clock)
        self._directory = directory

    async def __call__(self, owner: UUID, watchlist_id: UUID, symbols: Sequence[str]) -> WatchlistDto:
        codes = clean_symbols(list(symbols))
        await self._directory.ensure_known(codes)
        now = self._clock.now()
        return await self._apply(owner, watchlist_id, lambda w: w.adding(list(codes), now))


class RemoveSymbol(_Mutate):
    async def __call__(self, owner: UUID, watchlist_id: UUID, symbol: str) -> WatchlistDto:
        now = self._clock.now()
        return await self._apply(owner, watchlist_id, lambda w: w.removing(symbol, now))


class DeleteWatchlist:
    def __init__(self, uow: UowFactory) -> None:
        self._uow = uow

    async def __call__(self, owner: UUID, watchlist_id: UUID) -> None:
        async with self._uow() as uow:
            if not await uow.watchlists.delete(owner, watchlist_id):
                raise NotFoundError("Watchlist not found.")
            await uow.commit()


# ===================================================================================== saved scans
class ListSavedScans:
    def __init__(self, uow: UowFactory) -> None:
        self._uow = uow

    async def __call__(self, owner: UUID) -> list[SavedScanDto]:
        async with self._uow() as uow:
            return [scan_dto(s) for s in await uow.saved_scans.list(owner)]


class GetSavedScan:
    def __init__(self, uow: UowFactory) -> None:
        self._uow = uow

    async def __call__(self, owner: UUID, scan_id: UUID) -> SavedScanDto:
        async with self._uow() as uow:
            s = await uow.saved_scans.get(owner, scan_id)
        if s is None:
            raise NotFoundError("Saved scan not found.")
        return scan_dto(s)


class CreateSavedScan:
    def __init__(self, uow: UowFactory, validator: ScanValidator, clock: Clock) -> None:
        self._uow, self._validator, self._clock = uow, validator, clock

    async def __call__(self, owner: UUID, name: str, definition: dict[str, Any]) -> SavedScanDto:
        display, key = normalise_name(name)
        check_definition_size(definition)
        self._validator.validate(definition)
        now = self._clock.now()
        s = SavedScan(uuid4(), owner, display, key, definition, now, now)
        async with self._uow() as uow:
            if await uow.saved_scans.count(owner) >= MAX_SAVED_SCANS:
                raise ConflictError(f"You can have at most {MAX_SAVED_SCANS} saved scans.")
            await uow.saved_scans.add(s)
            await uow.commit()
        return scan_dto(s)


class UpdateSavedScan:
    def __init__(self, uow: UowFactory, validator: ScanValidator, clock: Clock) -> None:
        self._uow, self._validator, self._clock = uow, validator, clock

    async def __call__(
        self, owner: UUID, scan_id: UUID, name: str | None, definition: dict[str, Any] | None
    ) -> SavedScanDto:
        if definition is not None:
            check_definition_size(definition)
            self._validator.validate(definition)
        async with self._uow() as uow:
            s = await uow.saved_scans.get(owner, scan_id)
            if s is None:
                raise NotFoundError("Saved scan not found.")
            s = s.updated(name, definition, self._clock.now())
            await uow.saved_scans.update(s)
            await uow.commit()
        return scan_dto(s)


class DeleteSavedScan:
    def __init__(self, uow: UowFactory) -> None:
        self._uow = uow

    async def __call__(self, owner: UUID, scan_id: UUID) -> None:
        async with self._uow() as uow:
            if not await uow.saved_scans.delete(owner, scan_id):
                raise NotFoundError("Saved scan not found.")
            await uow.commit()
