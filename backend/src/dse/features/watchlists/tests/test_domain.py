from uuid import uuid4

import pytest

from dse.features.watchlists.domain.entities import (
    MAX_SYMBOLS,
    SavedScan,
    Watchlist,
    check_definition_size,
    clean_symbols,
    normalise_name,
)
from dse.features.watchlists.tests.fakes import NOW
from dse.shared_kernel.errors import ConflictError, ValidationFailedError


def wl(symbols: tuple[str, ...] = ()) -> Watchlist:
    return Watchlist(uuid4(), uuid4(), "Core", "core", symbols, NOW, NOW)


def test_names_are_trimmed_collapsed_and_keyed_case_insensitively() -> None:
    assert normalise_name("  My   Banks \t") == ("My Banks", "my banks")
    assert normalise_name("STRASSE")[1] == normalise_name("strasse")[1]
    for bad in ("", "   ", "x" * 61, "bad\x00name", "tab\x07bell"):
        with pytest.raises(ValidationFailedError):
            normalise_name(bad)
    assert normalise_name("x" * 60)[0] == "x" * 60


def test_symbols_are_validated_uppercased_and_deduplicated_in_order() -> None:
    assert clean_symbols(["gp", " batbc ", "GP", "Squrpharma", "BATBC"]) == ("GP", "BATBC", "SQURPHARMA")
    assert clean_symbols([]) == ()
    for bad in (["GP", "bad symbol"], [""], ["x" * 25], ["<script>"]):
        with pytest.raises(ValidationFailedError):
            clean_symbols(bad)


def test_adding_is_idempotent_and_keeps_existing_order() -> None:
    w = wl(("GP", "BATBC"))
    w2 = w.adding(["batbc", "robi", "gp"], NOW)
    assert w2.symbols == ("GP", "BATBC", "ROBI")
    assert w2.adding(["ROBI"], NOW).symbols == w2.symbols
    assert w.symbols == ("GP", "BATBC")  # entities are immutable


def test_removing_is_idempotent_and_validates_the_code() -> None:
    w = wl(("GP", "BATBC"))
    assert w.removing("gp", NOW).symbols == ("BATBC",)
    assert w.removing("ROBI", NOW).symbols == ("GP", "BATBC")
    with pytest.raises(ValidationFailedError):
        w.removing("not a symbol!", NOW)


def test_a_watchlist_holds_at_most_100_symbols() -> None:
    full = tuple(f"S{i}" for i in range(MAX_SYMBOLS))
    assert wl(full).adding(["S0"], NOW).symbols == full  # duplicates do not count
    with pytest.raises(ConflictError, match="at most 100"):
        wl(full).adding(["EXTRA"], NOW)
    with pytest.raises(ConflictError):
        wl().with_symbols([f"T{i}" for i in range(MAX_SYMBOLS + 1)], NOW)


def test_rename_updates_the_uniqueness_key() -> None:
    w = wl().renamed("  Pharma  Picks ", NOW)
    assert (w.name, w.name_key) == ("Pharma Picks", "pharma picks")


def test_saved_scan_updates_and_size_limit() -> None:
    s = SavedScan(uuid4(), uuid4(), "Oversold", "oversold", {"rules": []}, NOW, NOW)
    s2 = s.updated("New Name", {"rules": [1]}, NOW)
    assert (s2.name, s2.name_key, s2.definition) == ("New Name", "new name", {"rules": [1]})
    assert s.updated(None, None, NOW).name == "Oversold"
    with pytest.raises(ValidationFailedError, match="bytes"):
        check_definition_size({"rules": ["x" * 9000]})
    with pytest.raises(ValidationFailedError):
        s.updated(None, {"rules": ["x" * 9000]}, NOW)
