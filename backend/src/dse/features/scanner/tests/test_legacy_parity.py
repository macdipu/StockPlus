"""The new pipeline reproduces the LEGACY scanner on a fixed 48-instrument universe: the whole universe
frame (live and last-close views), all 41 presets (symbols AND order), two custom scans, sectors and P/E.

Golden = legacy `scanner.build_universe` / `scanner.run` output (see fixtures/). Two deliberate differences,
both legacy bugs, are asserted explicitly below rather than hidden.
"""

import dataclasses
import itertools
from dataclasses import replace
from datetime import date
from typing import Any

import pandas as pd
import pytest

from dse.features.analysis.application.facade import QuoteInput, UniverseInput, build_universe_rows
from dse.features.scanner.domain import analytics
from dse.features.scanner.domain.presets import PRESETS
from dse.features.scanner.domain.rules import Rule, ScanSpec, Sort, UniverseFilter, run_scan
from dse.features.scanner.domain.universe import rows_to_frame

EQ = UniverseFilter(asset_types=("EQ",))


def same(got: Any, want: Any, where: str) -> None:
    if isinstance(want, float):
        assert got == pytest.approx(want, rel=1e-9, abs=1e-9), where
    else:
        assert got == want, where


@pytest.fixture(scope="module")
def views(
    history: list[UniverseInput], quotes: dict[str, QuoteInput], session_day: date
) -> dict[str, pd.DataFrame]:
    live_items = [replace(h, quote=quotes.get(h.symbol)) for h in history]
    live = build_universe_rows(live_items, live=True, session_day=session_day)
    last = build_universe_rows(history, live=False, session_day=session_day)
    assert not live.errors
    assert not last.errors
    return {
        "live": rows_to_frame(live.rows, live.errors),
        "last_close": rows_to_frame(last.rows, last.errors),
    }


@pytest.mark.parametrize("view", ["live", "last_close"])
def test_universe_frame_matches_legacy(
    view: str, views: dict[str, pd.DataFrame], golden: dict[str, Any]
) -> None:
    want_rows = {r["symbol"]: r for r in golden[view]}
    got = views[view]
    assert set(got["symbol"]) == set(want_rows)
    renamed = {"assetType": "asset_type", "value": "value_mn"}
    for sym, want in want_rows.items():
        have = got.loc[sym].to_dict()
        assert set(have) == {renamed.get(k, k) for k in want}, "columns differ"
        for col, w in want.items():
            col = renamed.get(col, col)
            h = have[col]
            h = None if isinstance(h, float) and pd.isna(h) else h
            if col == "asset_type" and w is None:
                continue  # legacy dropped asset_type for quote-less rows; covered by the dedicated test below
            same(h, w, f"{view}/{sym}/{col}")


def test_asset_type_survives_without_a_quote(views: dict[str, pd.DataFrame], golden: dict[str, Any]) -> None:
    """Legacy bug fixed: rows with no live quote (not traded today) and the whole last-close view lost their
    asset type, so the default EQ filter silently dropped them from every scan."""
    legacy_none = [r["symbol"] for r in golden["last_close"] if r["assetType"] is None]
    assert len(legacy_none) == len(golden["last_close"])  # legacy: none of them had an asset type
    assert set(views["last_close"].loc[views["last_close"]["symbol"] != "MFUND", "asset_type"]) == {"EQ"}
    assert views["last_close"].loc["MFUND", "asset_type"] == "MF"
    assert views["live"].loc["NOQUOTE", "asset_type"] == "EQ"


@pytest.mark.parametrize("key", sorted(PRESETS))
def test_every_preset_matches_legacy(
    key: str, views: dict[str, pd.DataFrame], golden: dict[str, Any]
) -> None:
    want = golden["presets"][key]
    preset = PRESETS[key]
    assert preset.premarket == want["premarket"]
    frame = views["last_close" if preset.premarket else "live"]
    hits = run_scan(frame, preset.spec(EQ, 100))
    keys = [None if pd.isna(x) else x for x in hits[preset.sort.field]]
    assert sorted(hits["symbol"]) == sorted(want["symbols"])  # exactly the same instruments
    assert want["symbols"], f"{key}: the fixed universe should exercise every preset"
    for got, w in zip(keys, want["sort_keys"], strict=True):  # and the same ordering key-by-key …
        same(got, w, f"{key} sort key")
    if len(set(want["sort_keys"])) == len(want["sort_keys"]):
        assert list(hits["symbol"]) == want["symbols"]  # … identical order wherever the keys are distinct
    else:  # ties: legacy's quicksort order is unspecified; ours is stable (input order), hence deterministic
        positions = {s: i for i, s in enumerate(frame["symbol"])}
        ranked = list(zip(keys, hits["symbol"], strict=True))
        for (k1, s1), (k2, s2) in itertools.pairwise(ranked):
            if k1 == k2:
                assert positions[s1] < positions[s2], f"{key}: ties must keep universe order"


def test_premarket_presets_were_empty_by_default_in_legacy(golden: dict[str, Any]) -> None:
    """The second deliberate difference: with the legacy default filter (assetTypes=EQ) all pre-market presets
    returned nothing, because the last-close view had no asset type. They work now (test above)."""
    premarket = [k for k, v in golden["presets"].items() if v["premarket"]]
    assert premarket
    assert all(not golden["presets"][k]["legacy_default_eq_symbols"] for k in premarket)


def test_custom_scans_match_legacy(views: dict[str, pd.DataFrame], golden: dict[str, Any]) -> None:
    all_scan = ScanSpec(
        (Rule("rsi14", "between", [40, 80]), Rule("close", ">", field2="ema21")),
        "all",
        UniverseFilter(categories=("A", "B"), min_value_mn=1.0),
        Sort("vol_ratio", True),
        50,
    )
    any_scan = ScanSpec(
        (Rule("category", "==", "Z"), Rule("sector", "in", ["Food"])),
        "any",
        sort=Sort("symbol", False),
        limit=50,
    )
    assert list(run_scan(views["live"], all_scan)["symbol"]) == golden["custom"]["all"]
    assert list(run_scan(views["live"], any_scan)["symbol"]) == golden["custom"]["any"]


def assert_tree_same(got: Any, want: Any, where: str = "") -> None:
    if isinstance(want, dict):
        assert set(got) == set(want), where
        for k, w in want.items():
            assert_tree_same(got[k], w, f"{where}.{k}")
    elif isinstance(want, list):
        assert len(got) == len(want), where
        for i, (g, w) in enumerate(zip(got, want, strict=True)):
            assert_tree_same(g, w, f"{where}[{i}]")
    else:
        same(got, want, where)


def test_market_analytics_match_legacy(views: dict[str, pd.DataFrame], golden: dict[str, Any]) -> None:
    assert_tree_same(analytics.sectors(views["live"]), golden["sectors"], "sectors")
    assert_tree_same(analytics.pe_summary(views["live"]), golden["pe"], "pe")


def test_dataclass_inputs_are_immutable(history: list[UniverseInput]) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        history[0].symbol = "X"  # type: ignore[misc]
