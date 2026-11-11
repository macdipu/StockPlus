"""In-memory test doubles that satisfy the scanner ports."""

from collections.abc import Hashable
from dataclasses import replace
from datetime import date, datetime

from dse.core.clock import DHAKA
from dse.features.analysis.application.facade import QuoteInput, UniverseInput
from dse.features.scanner.application.ports import LiveState, StoredUniverse


class FakeClock:
    def now(self) -> datetime:
        return datetime(2026, 11, 11, 12, 0, tzinfo=DHAKA)

    def today(self) -> date:
        return self.now().date()


class FakeSource:
    def __init__(self, items: list[UniverseInput], quotes: dict[str, QuoteInput], day: date) -> None:
        self.items, self.quotes, self.day = items, quotes, day
        self.sig: Hashable = (1,)
        self.load_calls = 0
        self.ready = True

    async def history_signature(self) -> Hashable:
        return self.sig

    async def load_history(self) -> list[UniverseInput]:
        self.load_calls += 1
        return self.items

    async def live_state(self) -> LiveState:
        return LiveState(self.day, "11:40", self.quotes) if self.ready else LiveState(None, None, {})


class MemoryStore:
    def __init__(self) -> None:
        self.saved: StoredUniverse | None = None
        self.seq = 0
        self.loads = 0

    async def version(self) -> int | None:
        return self.saved.version if self.saved else None

    async def load(self) -> StoredUniverse | None:
        self.loads += 1
        return self.saved

    async def save(self, universe: StoredUniverse) -> int:
        self.seq += 1
        self.saved = replace(universe, version=self.seq)
        return self.seq


class Notifier:
    def __init__(self, fail: bool = False) -> None:
        self.events: list[tuple[int, int]] = []
        self.fail = fail

    async def built(self, version: int, rows: int, build_ms: int) -> None:
        if self.fail:
            raise ConnectionError("bus down")
        self.events.append((version, rows))
