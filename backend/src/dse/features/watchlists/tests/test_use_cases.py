"""Watchlist and saved-scan use cases on fakes: limits, duplicates, validation, and above all ownership."""

from uuid import uuid4

import pytest

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
from dse.features.watchlists.tests.fakes import FakeClock, FakeDirectory, FakeUow, FakeValidator, Store
from dse.shared_kernel.errors import ConflictError, NotFoundError, ValidationFailedError

KNOWN = {"GP", "BATBC", "ROBI", "SQURPHARMA"}
ALICE, BOB = uuid4(), uuid4()
RULES = {"rules": [{"field": "rsi14", "op": "<", "value": 30}]}


class World:
    def __init__(self) -> None:
        self.store, self.clock = Store(), FakeClock()
        self.directory, self.validator = FakeDirectory(set(KNOWN)), FakeValidator()
        uow = lambda: FakeUow(self.store)  # noqa: E731
        d, c, v = self.directory, self.clock, self.validator
        self.create, self.list, self.get = CreateWatchlist(uow, d, c), ListWatchlists(uow), GetWatchlist(uow)
        self.rename, self.replace = RenameWatchlist(uow, c), ReplaceSymbols(uow, d, c)
        self.add, self.remove, self.delete = AddSymbols(uow, d, c), RemoveSymbol(uow, c), DeleteWatchlist(uow)
        self.scan_create, self.scan_update = CreateSavedScan(uow, v, c), UpdateSavedScan(uow, v, c)
        self.scan_list, self.scan_get, self.scan_delete = (
            ListSavedScans(uow),
            GetSavedScan(uow),
            DeleteSavedScan(uow),
        )


@pytest.fixture
def w() -> World:
    return World()


async def test_create_normalises_and_validates_symbols(w: World) -> None:
    out = await w.create(ALICE, "  My   Banks ", ["gp", "BATBC", "GP"])
    assert (out.name, out.symbols) == ("My Banks", ["GP", "BATBC"])
    assert [x.id for x in await w.list(ALICE)] == [out.id]
    assert await w.list(BOB) == []


async def test_unknown_symbols_are_rejected_and_nothing_is_saved(w: World) -> None:
    with pytest.raises(ValidationFailedError, match="NOPE"):
        await w.create(ALICE, "Bad", ["GP", "NOPE"])
    assert w.store.watchlists == {}
    ok = await w.create(ALICE, "Good", ["GP"])
    with pytest.raises(ValidationFailedError):
        await w.add(ALICE, ok.id, ["NOPE"])
    with pytest.raises(ValidationFailedError):
        await w.replace(ALICE, ok.id, ["NOPE"])
    assert (await w.get(ALICE, ok.id)).symbols == ["GP"]


async def test_names_are_unique_per_user_ignoring_case_but_not_across_users(w: World) -> None:
    a = await w.create(ALICE, "Core")
    with pytest.raises(ConflictError):
        await w.create(ALICE, "  core ")
    await w.create(BOB, "Core")  # a different user may reuse it
    other = await w.create(ALICE, "Other")
    with pytest.raises(ConflictError):
        await w.rename(ALICE, other.id, "CORE")
    assert (await w.rename(ALICE, a.id, "Core Renamed")).name == "Core Renamed"


async def test_at_most_20_watchlists_per_user(w: World) -> None:
    for i in range(20):
        await w.create(ALICE, f"List {i}")
    with pytest.raises(ConflictError, match="at most 20"):
        await w.create(ALICE, "One too many")
    await w.create(BOB, "Bob is unaffected")


async def test_add_remove_replace(w: World) -> None:
    a = await w.create(ALICE, "Core", ["GP"])
    assert (await w.add(ALICE, a.id, ["robi", "GP"])).symbols == ["GP", "ROBI"]
    assert (await w.remove(ALICE, a.id, "gp")).symbols == ["ROBI"]
    assert (await w.remove(ALICE, a.id, "BATBC")).symbols == ["ROBI"]  # idempotent
    assert (await w.replace(ALICE, a.id, ["SQURPHARMA", "GP", "ROBI"])).symbols == [
        "SQURPHARMA",
        "GP",
        "ROBI",
    ]
    assert (await w.replace(ALICE, a.id, [])).symbols == []


async def test_another_users_watchlist_does_not_exist_for_you(w: World) -> None:
    mine = await w.create(ALICE, "Private", ["GP"])
    calls = [
        w.get(BOB, mine.id),
        w.rename(BOB, mine.id, "Hijacked"),
        w.add(BOB, mine.id, ["ROBI"]),
        w.remove(BOB, mine.id, "GP"),
        w.replace(BOB, mine.id, []),
        w.delete(BOB, mine.id),
    ]
    for call in calls:
        with pytest.raises(NotFoundError):  # 404, never 403: the id's existence is not revealed
            await call
    unchanged = await w.get(ALICE, mine.id)
    assert (unchanged.name, unchanged.symbols) == ("Private", ["GP"])


async def test_delete(w: World) -> None:
    a = await w.create(ALICE, "Temp")
    await w.delete(ALICE, a.id)
    with pytest.raises(NotFoundError):
        await w.get(ALICE, a.id)
    with pytest.raises(NotFoundError):
        await w.delete(ALICE, a.id)


# ----------------------------------------------------------------------------------------- saved scans
async def test_saved_scan_lifecycle(w: World) -> None:
    s = await w.scan_create(ALICE, " Oversold  RSI ", RULES)
    assert s.name == "Oversold RSI"
    assert w.validator.seen == [RULES]
    assert [x.id for x in await w.scan_list(ALICE)] == [s.id]
    assert (await w.scan_get(ALICE, s.id)).definition == RULES
    new_rules = {"rules": [{"field": "rsi14", "op": "<", "value": 20}]}
    updated = await w.scan_update(ALICE, s.id, "Very oversold", new_rules)
    assert (updated.name, updated.definition) == ("Very oversold", new_rules)
    renamed_only = await w.scan_update(ALICE, s.id, "Renamed", None)
    assert renamed_only.definition == new_rules
    await w.scan_delete(ALICE, s.id)
    assert await w.scan_list(ALICE) == []


async def test_invalid_scan_definitions_are_rejected_before_saving(w: World) -> None:
    with pytest.raises(ValidationFailedError):
        await w.scan_create(ALICE, "Empty", {"rules": []})
    with pytest.raises(ValidationFailedError, match="bytes"):
        await w.scan_create(ALICE, "Huge", {"rules": ["x" * 9000]})
    s = await w.scan_create(ALICE, "Fine", RULES)
    with pytest.raises(ValidationFailedError):
        await w.scan_update(ALICE, s.id, None, {"rules": []})
    assert (await w.scan_get(ALICE, s.id)).definition == RULES
    assert w.store.scans.keys() == {s.id}


async def test_saved_scan_names_limits_and_isolation(w: World) -> None:
    s = await w.scan_create(ALICE, "Mine", RULES)
    with pytest.raises(ConflictError):
        await w.scan_create(ALICE, "mine", RULES)
    await w.scan_create(BOB, "Mine", RULES)
    for call in (
        w.scan_get(BOB, s.id),
        w.scan_update(BOB, s.id, "x", None),
        w.scan_delete(BOB, s.id),
    ):
        with pytest.raises(NotFoundError):
            await call
    for i in range(49):
        await w.scan_create(ALICE, f"Scan {i}", RULES)
    with pytest.raises(ConflictError, match="at most 50"):
        await w.scan_create(ALICE, "Too many", RULES)
