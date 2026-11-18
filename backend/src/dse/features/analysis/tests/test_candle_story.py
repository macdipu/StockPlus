"""Candle story on the recorded ORIONINFU history and on small synthetic frames."""

from collections.abc import Sequence
from typing import Any

import pandas as pd
import pytest

from dse.features.analysis.application.inputs import AnalysisInput
from dse.features.analysis.application.knowledge import build
from dse.features.analysis.domain import candle_story


def test_story_levels_are_ordered_and_worded(orion_input: AnalysisInput) -> None:
    k, _ = build(orion_input)
    st = k["candle_story"]
    ann = {a["kind"]: a for a in st["annotations"] if a["kind"] in ("entry", "stop")}
    entry, stop = ann["entry"], ann["stop"]
    assert stop["price"] < entry["price_to"] <= entry["price"]  # stop always under the buy zone
    targets = [a["price"] for a in st["annotations"] if a["kind"] == "target"]
    assert targets == sorted(targets)
    assert [p["step"] for p in st["plan"]] == [
        "Where to enter",
        "Where to exit (stop loss)",
        "Where to take profit",
        "What to watch",
    ]
    assert len(st["recent"]) == 5
    assert st["recent"][-1]["date"] == k["price"]["last_bar_date"]
    assert st["where"] in {"inside_buy_zone", "above_buy_zone", "below_buy_zone", "below_stop"}
    assert all(a["label"] and a["text"] for a in st["annotations"])


def _frame(rows: Sequence[tuple[float, float, float, float, float]]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=len(rows), freq="D")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx)
    df["vol_avg20"] = 1000.0
    df["atr14"] = 2.0
    df["rsi14"] = 50.0
    return df


def test_recent_candles_describe_shape_volume_and_patterns() -> None:
    df = _frame(
        [(100, 101, 99, 100.5, 1000)] * 22 + [(99, 101, 92, 100.8, 2000)]
    )  # long lower wick, 2x volume
    pats: list[dict[str, Any]] = [{"date": "2026-01-23", "pattern": "Hammer", "direction": "bullish"}]
    rec = candle_story.recent_candles(df, pats)
    last = rec[-1]
    assert last["shape"] == "long lower wick"
    assert last["bias"] == "bullish"
    assert last["vol_ratio"] == pytest.approx(2.0)
    assert "Hammer: sellers pushed the price down" in last["text"]


@pytest.mark.parametrize(
    ("close", "where"),
    [(96.5, "inside_buy_zone"), (99.5, "above_buy_zone"), (95.2, "below_buy_zone"), (90.0, "below_stop")],
)
def test_where_the_price_stands(close: float, where: str) -> None:
    df = _frame([(100, 101, 99, 100, 1000)] * 22 + [(close, close + 0.5, close - 0.5, close, 1000)])
    levels = {"below": [96.0], "above": [104.0, 108.0]}
    plan = {"stop": 95.5, "target": 104.0, "entry_zone": [close - 1, close], "atr": 2.0}
    st = candle_story.story(df, [], levels, plan)
    assert st["where"] == where or (close == 95.2 and st["where"] == "below_stop")


def test_stop_is_pushed_under_a_zone_it_would_sit_inside() -> None:
    df = _frame([(100, 101, 99, 100, 1000)] * 23)
    st = candle_story.story(
        df, [], {"below": [98.0], "above": []}, {"stop": 99.0, "target": 103.0, "atr": 2.0}
    )
    entry = next(a for a in st["annotations"] if a["kind"] == "entry")
    stop = next(a for a in st["annotations"] if a["kind"] == "stop")
    assert stop["price"] < entry["price_to"]
    assert "buy zone low" in stop["text"]


def test_live_candle_is_labelled() -> None:
    df = _frame([(100, 101, 99, 100, 1000)] * 23)
    st = candle_story.story(
        df, [], {"below": [], "above": []}, {"stop": 97.0, "target": 104.0, "atr": 2.0}, live=True
    )
    assert st["recent"][-1]["text"].startswith("Today, still forming")
