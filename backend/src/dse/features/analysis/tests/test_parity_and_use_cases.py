"""The ported pipeline reproduces the LEGACY output on recorded data; use cases run on fake inputs."""

from dataclasses import replace
from datetime import date
from typing import Any

import pandas as pd
import pytest

from dse.features.analysis.application.inputs import AnalysisInput
from dse.features.analysis.application.knowledge import build, clean, technical_bars
from dse.features.analysis.application.use_cases import (
    AnalyzeInstrument,
    GetBrief,
    GetTechnicals,
    GetVpa,
    RankSymbols,
)
from dse.features.analysis.domain.frames import Bar, LiveBar, merge_live, to_frame
from dse.features.analysis.tests.conftest import FakeInputs
from dse.shared_kernel.errors import ValidationFailedError

KEYS = (
    "indicators",
    "candles",
    "levels",
    "trend",
    "valuation",
    "setup",
    "signal",
    "probability",
    "summary",
)


def assert_same(got: Any, want: Any, path: str = "") -> None:
    if isinstance(want, dict):
        assert isinstance(got, dict), path
        assert set(got) == set(want), f"{path}: keys differ {set(got) ^ set(want)}"
        for k in want:
            assert_same(got[k], want[k], f"{path}.{k}")
    elif isinstance(want, list):
        assert isinstance(got, list), path
        assert len(got) == len(want), f"{path}: {len(got)} != {len(want)}"
        for i, (g, w) in enumerate(zip(got, want, strict=True)):
            assert_same(g, w, f"{path}[{i}]")
    elif isinstance(want, float):
        assert got == pytest.approx(want, rel=1e-9, abs=1e-9), path
    else:
        assert got == want, path


def check(k: dict[str, Any], ind: pd.DataFrame, want: dict[str, Any]) -> None:
    got = clean(k)
    for key in KEYS:
        if key == "candles":  # legacy golden pins these two; last_sessions/thresholds are pass-through data
            assert_same({c: got[key][c] for c in ("last_candle", "patterns")}, want[key], key)
        else:
            assert_same(got[key], want[key], key)
    assert len(ind) == want["n_bars"]
    last = ind.iloc[-1]
    assert_same({c: float(last[c]) for c in ("open", "high", "low", "close", "volume")}, want["last_bar"])


def test_stored_bars_match_legacy(orion_input: AnalysisInput, golden: dict[str, Any]) -> None:
    k, ind = build(orion_input)
    check(k, ind, golden["as_stored"])
    assert k["signal"]["action"] == "STRONG SELL"  # pinned: ORIONINFU's recorded history is a downtrend


def test_live_bar_matches_legacy(
    orion_input: AnalysisInput, live_bar: LiveBar, golden: dict[str, Any]
) -> None:
    k, ind = build(replace(orion_input, live=live_bar, market_open=True))
    check(k, ind, golden["with_live_bar"])
    assert k["price"]["live_bar"] is True
    assert k["price"]["last_bar_date"] == golden["live_session_day"]


def test_too_few_bars_is_a_validation_error(orion_input: AnalysisInput) -> None:
    with pytest.raises(ValidationFailedError, match="too few"):
        build(replace(orion_input, bars=orion_input.bars[:30]))
    with pytest.raises(ValidationFailedError):
        build(replace(orion_input, bars=()))


# ---------------------------------------------------------------- frames


def test_merge_live_rules(orion_bars: tuple[Bar, ...], live_bar: LiveBar) -> None:
    df = to_frame(orion_bars)
    assert len(merge_live(df, None)) == len(df)
    assert len(merge_live(df, replace(live_bar, volume=0))) == len(df)  # has not traded
    assert len(merge_live(df, replace(live_bar, ltp=None))) == len(df)
    old = replace(live_bar, session_day=date(2020, 1, 1))
    assert len(merge_live(df, old)) == len(df)  # never rewrite history
    merged = merge_live(df, live_bar)
    assert len(merged) == len(df) + 1
    assert merged["close"].iloc[-1] == (live_bar.close or live_bar.ltp)
    assert merged["volume"].iloc[-1] == live_bar.volume
    same_day = replace(
        live_bar, session_day=df.index[-1].date(), ltp=1.0, close=None, open=None, high=None, low=None
    )
    refreshed = merge_live(df, same_day)
    assert len(refreshed) == len(df)
    assert refreshed["close"].iloc[-1] == 1.0
    assert len(df) == len(orion_bars)  # input frame untouched


def test_to_frame_dedupes_and_sorts() -> None:
    bars = [Bar(date(2025, 1, 2), 1, 2, 0.5, 1.5, 10), Bar(date(2025, 1, 1), 1, 2, 0.5, 1.2, 10)]
    bars.append(Bar(date(2025, 1, 2), 1, 2, 0.5, 1.9, 11))
    df = to_frame(bars)
    assert [d.day for d in df.index] == [1, 2]
    assert df["close"].iloc[-1] == 1.9


def test_clean_is_json_safe() -> None:
    import numpy as np

    out = clean({"a": float("nan"), "b": np.float64(1.234567), "c": (1, np.int64(2)), "d": np.bool_(True)})
    assert out == {"a": None, "b": 1.2346, "c": [1, 2], "d": True}


# ---------------------------------------------------------------- use cases


async def test_analyze_returns_typed_dto(orion_input: AnalysisInput) -> None:
    a = await AnalyzeInstrument(FakeInputs(orion_input))("ORIONINFU")
    assert a.symbol == "ORIONINFU"
    assert a.signal.action in {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL", "AVOID"}
    assert a.setup.max == 6
    assert a.setup.plan.entry_zone[1] == a.setup.plan.entry
    assert a.indicators["rsi14"] is not None
    assert a.summary
    assert a.disclaimer.startswith("For research only")
    assert a.model_dump(mode="json")["probability"]["similar_setups"]["n"] == 85


async def test_brief_is_markdown(orion_input: AnalysisInput) -> None:
    md = await GetBrief(AnalyzeInstrument(FakeInputs(orion_input)))("ORIONINFU")
    for heading in ("# ORIONINFU", "## Price", "## Signal", "## Indicators", "## Valuation", "## Summary"):
        assert heading in md
    assert "nan" not in md.lower().replace("finance", "")


async def test_technicals_and_vpa(orion_input: AnalysisInput) -> None:
    analyze = AnalyzeInstrument(FakeInputs(orion_input))
    bars = await GetTechnicals(analyze)("ORIONINFU", 30)
    assert len(bars) == 30
    assert bars[-1].sma200 is not None
    assert bars[-1].date > bars[0].date
    v = await GetVpa(analyze)("ORIONINFU", 40)
    assert len(v.rows) == 40
    assert {"Strong buying", "No supply"} <= set(v.legend)
    assert v.thresholds["N"] == 20
    assert all(r.vpa is None or r.vpa in v.legend for r in v.rows)
    assert any(r.vpa for r in (await GetVpa(analyze)("ORIONINFU", 260)).rows)  # labels actually fire


async def test_technicals_helper_limit(orion_input: AnalysisInput) -> None:
    _, ind = build(orion_input)
    assert len(technical_bars(ind)) == len(ind)
    assert len(technical_bars(ind, 5)) == 5


async def test_rank_orders_by_score_and_reports_errors(orion_input: AnalysisInput) -> None:
    z = replace(orion_input, symbol="ZZZ", category="Z")  # not_z fails → lower score, AVOID
    inputs = FakeInputs(orion_input, z)
    rows = await RankSymbols(AnalyzeInstrument(inputs))(["ZZZ", "NOPE", "ORIONINFU"])
    assert [r.symbol for r in rows] == ["ORIONINFU", "ZZZ", "NOPE"]
    assert [r.rank for r in rows] == [1, 2, 3]
    assert rows[1].action == "AVOID"
    assert rows[2].action == "ERROR"
    assert rows[2].error is not None
    assert rows[2].score == -1
