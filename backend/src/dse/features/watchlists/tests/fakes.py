"""In-memory doubles satisfying the watchlists ports. They enforce the same ownership and unique-name rules
the database does, so use-case tests cannot pass by accident."""

from collections.abc import Sequence
from datetime import date, datetime
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from dse.core.clock import DHAKA
from dse.features.watchlists.domain.entities import SavedScan, Watchlist
from dse.shared_kernel.errors import ConflictError, ValidationFailedError

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=DHAKA)


class FakeClock:
    def now(self) -> datetime:
        return NOW

    def today(self) -> date:
        return NOW.date()


class FakeDirectory:
    def __init__(self, known: set[str]) -> None:
        self.known, self.calls = known, 0

    async def ensure_known(self, symbols: Sequence[str]) -> None:
        self.calls += 1
        missing = [s for s in symbols if s not in self.known]
        if missing:
            raise ValidationFailedError(f"Not a DSE trading code: {', '.join(missing)}")


class FakeValidator:
    """Rejects any definition that has no rules, like the real parser; records what it saw."""

    def __init__(self) -> None:
        self.seen: list[Any] = []

    def validate(self, definition: Any) -> None:
        self.seen.append(definition)
        if not definition.get("rules"):
            raise ValidationFailedError("'rules' must be a list of 1-20 rules")


class Store:
    def __init__(self) -> None:
        self.watchlists: dict[UUID, Watchlist] = {}
        self.scans: dict[UUID, SavedScan] = {}


def _clash(items: Sequence[Watchlist | SavedScan], new: Watchlist | SavedScan, what: str) -> None:
    if any(i.owner_id == new.owner_id and i.name_key == new.name_key and i.id != new.id for i in items):
        raise ConflictError(f"You already have a {what} with this name.")


class FakeUow:
    def __init__(self, store: Store) -> None:
        class Watchlists:
            async def list(self, owner_id: UUID) -> list[Watchlist]:
                return [w for w in store.watchlists.values() if w.owner_id == owner_id]

            async def get(self, owner_id: UUID, watchlist_id: UUID) -> Watchlist | None:
                w = store.watchlists.get(watchlist_id)
                return w if w and w.owner_id == owner_id else None

            async def count(self, owner_id: UUID) -> int:
                return len(await self.list(owner_id))

            async def add(self, w: Watchlist) -> None:
                _clash(list(store.watchlists.values()), w, "watchlist")
                store.watchlists[w.id] = w

            async def update(self, w: Watchlist) -> None:
                _clash(list(store.watchlists.values()), w, "watchlist")
                if w.id in store.watchlists and store.watchlists[w.id].owner_id == w.owner_id:
                    store.watchlists[w.id] = w

            async def delete(self, owner_id: UUID, watchlist_id: UUID) -> bool:
                if await self.get(owner_id, watchlist_id) is None:
                    return False
                del store.watchlists[watchlist_id]
                return True

        class Scans:
            async def list(self, owner_id: UUID) -> list[SavedScan]:
                return [s for s in store.scans.values() if s.owner_id == owner_id]

            async def get(self, owner_id: UUID, scan_id: UUID) -> SavedScan | None:
                s = store.scans.get(scan_id)
                return s if s and s.owner_id == owner_id else None

            async def count(self, owner_id: UUID) -> int:
                return len(await self.list(owner_id))

            async def add(self, s: SavedScan) -> None:
                _clash(list(store.scans.values()), s, "saved scan")
                store.scans[s.id] = s

            async def update(self, s: SavedScan) -> None:
                _clash(list(store.scans.values()), s, "saved scan")
                if s.id in store.scans and store.scans[s.id].owner_id == s.owner_id:
                    store.scans[s.id] = s

            async def delete(self, owner_id: UUID, scan_id: UUID) -> bool:
                if await self.get(owner_id, scan_id) is None:
                    return False
                del store.scans[scan_id]
                return True

        self.watchlists, self.saved_scans = Watchlists(), Scans()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        return None

    async def commit(self) -> None:
        return None
