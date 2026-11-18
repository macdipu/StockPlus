from typing import Any

import pandas as pd

from dse.features.scanner.domain import picks
from dse.features.scanner.domain.picks import PickFilter
from dse.features.scanner.domain.rules import UniverseFilter, parse_scan_definition
from dse.features.scanner.domain.universe import rows_to_frame


def row(sym: str, sector: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "symbol": sym,
        "name": sym,
        "sector": sector,
        "category": "A",
        "asset_type": "EQ",
        "ltp": 100.0,
        "close": 100.0,
        "change_pct": 0.5,
        "pe": 6.0,
        "pb": 0.8,
        "dividend_yield_pct": 7.0,
        "graham_gap_pct": 40.0,
        "sponsor_pct": 50.0,
        "rsi14": 45.0,
        "sma200": 90.0,
        "sma50": 98.0,
        "sma20": 99.0,
        "low_52w": 85.0,
        "high_52w": 130.0,
        "macd": 1.0,
        "macd_signal": 0.5,
        "macd_hist": 0.5,
        "macd_hist_prev": 0.3,
        "bullish_pattern": True,
        "bearish_pattern": False,
        "patterns": ["Hammer"],
        "vpa": "No supply",
        "vpa_bias": "bullish",
        "setup_score": 5,
        "value_mn": 10.0,
    }
    base.update(kw)
    return base


def frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return rows_to_frame(rows)


def test_buckets_and_order() -> None:
    u = frame(
        [
            row("CHEAPGOOD", "Pharma"),
            row("HOT", "Pharma", rsi14=78.0, sma20=85.0),
            row("LOSS", "Textile", pe=None),
            row(
                "MEH",
                "Textile",
                pe=25.0,
                pb=4.5,
                dividend_yield_pct=0.0,
                graham_gap_pct=-20.0,
                sponsor_pct=10.0,
            ),
        ]
    )
    out = picks.rank(u, PickFilter(UniverseFilter()))
    by = {r["symbol"]: r for r in out}
    assert by["CHEAPGOOD"]["bucket"] == "buy_zone"
    assert by["HOT"]["bucket"] == "wait_pullback"
    assert by["LOSS"]["bucket"] == "avoid"
    assert by["MEH"]["bucket"] == "watch"
    assert next(r["symbol"] for r in out) == "CHEAPGOOD"
    assert by["CHEAPGOOD"]["reasons"]
    assert by["HOT"]["warnings"]
    assert 0 <= by["CHEAPGOOD"]["value_score"] <= 100
    assert 0 <= by["CHEAPGOOD"]["entry_score"] <= 100


def test_exclude_sectors_and_bucket_filter() -> None:
    u = frame([row("BANK1", "Bank"), row("INS1", "Insurance"), row("PHARMA1", "Pharma")])
    flt = PickFilter(UniverseFilter(exclude_sectors=("Bank", "Insurance")))
    assert [r["symbol"] for r in picks.rank(u, flt)] == ["PHARMA1"]
    only_avoid = PickFilter(UniverseFilter(), buckets=("avoid",))
    assert picks.rank(u, only_avoid) == []
    assert picks.sector_names(u) == ["Bank", "Insurance", "Pharma"]


def test_saved_scans_accept_exclude_sectors() -> None:
    spec = parse_scan_definition(
        {"rules": [{"field": "rsi14", "op": "<", "value": 30}], "universe": {"exclude_sectors": ["Bank"]}}
    )
    assert spec.universe.exclude_sectors == ("Bank",)
