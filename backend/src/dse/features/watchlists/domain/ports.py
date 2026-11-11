"""Repositories for user-owned data. Every lookup is scoped by owner: another user's id is simply absent."""

from types import TracebackType
from typing import Protocol
from uuid import UUID

from dse.features.watchlists.domain.entities import SavedScan, Watchlist


class WatchlistRepository(Protocol):
    async def list(self, owner_id: UUID) -> list[Watchlist]: ...

    async def get(self, owner_id: UUID, watchlist_id: UUID) -> Watchlist | None: ...

    async def count(self, owner_id: UUID) -> int: ...

    async def add(self, watchlist: Watchlist) -> None:
        """Raises ConflictError when the owner already has a list with that name."""
        ...

    async def update(self, watchlist: Watchlist) -> None:
        """Raises ConflictError on a name clash."""
        ...

    async def delete(self, owner_id: UUID, watchlist_id: UUID) -> bool: ...


class SavedScanRepository(Protocol):
    async def list(self, owner_id: UUID) -> list[SavedScan]: ...

    async def get(self, owner_id: UUID, scan_id: UUID) -> SavedScan | None: ...

    async def count(self, owner_id: UUID) -> int: ...

    async def add(self, scan: SavedScan) -> None: ...

    async def update(self, scan: SavedScan) -> None: ...

    async def delete(self, owner_id: UUID, scan_id: UUID) -> bool: ...


class WatchlistsUnitOfWork(Protocol):
    @property
    def watchlists(self) -> WatchlistRepository: ...

    @property
    def saved_scans(self) -> SavedScanRepository: ...

    async def __aenter__(self) -> "WatchlistsUnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...
