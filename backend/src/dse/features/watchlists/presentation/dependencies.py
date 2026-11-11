"""Dependency providers for watchlists and saved scans."""

from dataclasses import dataclass

from fastapi import Request

from dse.core.db import Database
from dse.features.watchlists.application.ports import ScanValidator, SymbolDirectory
from dse.features.watchlists.application.use_cases import (
    AddSymbols,
    CreateSavedScan,
    CreateWatchlist,
    DeleteSavedScan,
    DeleteWatchlist,
    GetSavedScan,
    GetWatchlist,
    ListSavedScans,
    ListWatchlists,
    RemoveSymbol,
    RenameWatchlist,
    ReplaceSymbols,
    UpdateSavedScan,
)
from dse.features.watchlists.domain.ports import WatchlistsUnitOfWork
from dse.features.watchlists.infrastructure.repositories import SqlWatchlistsUnitOfWork
from dse.shared_kernel.clock import Clock


@dataclass(frozen=True)
class WatchlistsContainer:
    db: Database
    directory: SymbolDirectory
    validator: ScanValidator
    clock: Clock

    def uow(self) -> WatchlistsUnitOfWork:
        return SqlWatchlistsUnitOfWork(self.db.sessions)

    @property
    def list_watchlists(self) -> ListWatchlists:
        return ListWatchlists(self.uow)

    @property
    def get_watchlist(self) -> GetWatchlist:
        return GetWatchlist(self.uow)

    @property
    def create_watchlist(self) -> CreateWatchlist:
        return CreateWatchlist(self.uow, self.directory, self.clock)

    @property
    def rename_watchlist(self) -> RenameWatchlist:
        return RenameWatchlist(self.uow, self.clock)

    @property
    def replace_symbols(self) -> ReplaceSymbols:
        return ReplaceSymbols(self.uow, self.directory, self.clock)

    @property
    def add_symbols(self) -> AddSymbols:
        return AddSymbols(self.uow, self.directory, self.clock)

    @property
    def remove_symbol(self) -> RemoveSymbol:
        return RemoveSymbol(self.uow, self.clock)

    @property
    def delete_watchlist(self) -> DeleteWatchlist:
        return DeleteWatchlist(self.uow)

    @property
    def list_scans(self) -> ListSavedScans:
        return ListSavedScans(self.uow)

    @property
    def get_scan(self) -> GetSavedScan:
        return GetSavedScan(self.uow)

    @property
    def create_scan(self) -> CreateSavedScan:
        return CreateSavedScan(self.uow, self.validator, self.clock)

    @property
    def update_scan(self) -> UpdateSavedScan:
        return UpdateSavedScan(self.uow, self.validator, self.clock)

    @property
    def delete_scan(self) -> DeleteSavedScan:
        return DeleteSavedScan(self.uow)


def container(request: Request) -> WatchlistsContainer:
    c: WatchlistsContainer = request.app.state.watchlists
    return c
