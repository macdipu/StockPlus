"""Candlestick pattern detection with explicit, tunable thresholds (ported unchanged from legacy).

Definitions (body = |close-open|, range = high-low, upper/lower = shadows):
  doji            body <= DOJI_BODY * range
  marubozu        body >= MARUBOZU_BODY * range            (bullish if close>open)
  hammer          lower >= LONG_SHADOW * body, upper <= SHORT_SHADOW * range, in a down-trend
  inverted hammer upper >= LONG_SHADOW * body, lower <= SHORT_SHADOW * range, in a down-trend
  shooting star   same shape as inverted hammer, in an up-trend
  engulfing       body of bar 2 fully covers body of bar 1, opposite colours
  morning star    long bearish bar, small-body bar (<= STAR_BODY * bar1 body), bullish bar closing
                  above bar1 midpoint
  evening star    mirror image of morning star
  three soldiers  3 bullish bars, rising closes, each opens inside prior body, each body >=
                  SOLDIER_BODY * range, upper shadow <= SOLDIER_SHADOW * range
                  (three black crows: mirror image)
Trend context = close before the pattern vs close TREND_BARS earlier.

Each detector is a small function (Strategy): `DETECTORS` is the ordered catalogue `detect_at` runs.
"""

from collections.abc import Callable
from typing import Any

import pandas as pd

PATTERN_LOOKBACK = 10

T: dict[str, float] = {
    "DOJI_BODY": 0.10,
    "MARUBOZU_BODY": 0.90,
    "LONG_SHADOW": 2.0,
    "SHORT_SHADOW": 0.10,
    "MIN_BODY": 0.03,  # hammer-family needs at least a sliver of body (else it's a doji)
    "LONG_BODY": 0.60,  # "long" bar for stars: body >= LONG_BODY * range
    "STAR_BODY": 0.30,
    "SOLDIER_BODY": 0.50,
    "SOLDIER_SHADOW": 0.25,
    "TREND_BARS": 5,
}

Found = list[tuple[str, str]]


def _parts(r: Any) -> tuple[float, float, float, float]:
    o, h, lo, c = r["open"], r["high"], r["low"], r["close"]
    rng = h - lo
    return abs(c - o), rng, h - max(o, c), min(o, c) - lo


def _bull(r: Any) -> bool:
    return bool(r["close"] > r["open"])


def _bear(r: Any) -> bool:
    return bool(r["close"] < r["open"])


def _trend(df: pd.DataFrame, i: int) -> str:
    """Trend leading into bar i (uses bars before i)."""
    j = i - 1
    bars = int(T["TREND_BARS"])
    if j - bars < 0:
        return "flat"
    a, b = df["close"].iloc[j - bars], df["close"].iloc[j]
    return "up" if b > a else "down" if b < a else "flat"


# --------------------------------------------------------------------------- single-bar detectors
def _single_bar(df: pd.DataFrame, i: int) -> Found:
    r = df.iloc[i]
    body, rng, up, lo = _parts(r)
    found: Found = []
    trend = _trend(df, i)
    if body <= T["DOJI_BODY"] * rng:
        found.append(("Doji", "neutral"))
    if body >= T["MARUBOZU_BODY"] * rng:
        found.append(("Bullish Marubozu", "bullish") if _bull(r) else ("Bearish Marubozu", "bearish"))
    if body >= T["MIN_BODY"] * rng:
        if lo >= T["LONG_SHADOW"] * body and up <= T["SHORT_SHADOW"] * rng and trend == "down":
            found.append(("Hammer", "bullish"))
        if up >= T["LONG_SHADOW"] * body and lo <= T["SHORT_SHADOW"] * rng:
            if trend == "down":
                found.append(("Inverted Hammer", "bullish"))
            elif trend == "up":
                found.append(("Shooting Star", "bearish"))
    return found


# --------------------------------------------------------------------------- two-bar detectors
def _engulfing(df: pd.DataFrame, i: int) -> Found:
    if i < 1:
        return []
    r, p = df.iloc[i], df.iloc[i - 1]
    body, pb = abs(r["close"] - r["open"]), abs(p["close"] - p["open"])
    found: Found = []
    if _bear(p) and _bull(r) and r["open"] <= p["close"] and r["close"] >= p["open"] and body > pb:
        found.append(("Bullish Engulfing", "bullish"))
    if _bull(p) and _bear(r) and r["open"] >= p["close"] and r["close"] <= p["open"] and body > pb:
        found.append(("Bearish Engulfing", "bearish"))
    return found


# --------------------------------------------------------------------------- three-bar detectors
def _stars(df: pd.DataFrame, i: int) -> Found:
    if i < 2:
        return []
    a, b, r = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
    ab, ar, _, _ = _parts(a)
    bb = abs(b["close"] - b["open"])
    long_a = ar > 0 and ab >= T["LONG_BODY"] * ar
    small_b = bb <= T["STAR_BODY"] * ab
    mid_a = (a["open"] + a["close"]) / 2
    found: Found = []
    if long_a and small_b and _bear(a) and _bull(r) and r["close"] > mid_a:
        found.append(("Morning Star", "bullish"))
    if long_a and small_b and _bull(a) and _bear(r) and r["close"] < mid_a:
        found.append(("Evening Star", "bearish"))
    return found


def _soldiers_and_crows(df: pd.DataFrame, i: int) -> Found:
    if i < 2:
        return []
    a, b, r = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
    bars = [a, b, r]

    def strong(x: Any) -> tuple[bool, float, float, float]:
        xb, xr, xu, xl = _parts(x)
        return xr > 0 and xb >= T["SOLDIER_BODY"] * xr, xu, xl, xr

    ok = [strong(x) for x in bars]
    found: Found = []
    if (
        all(_bull(x) for x in bars)
        and all(s[0] and s[1] <= T["SOLDIER_SHADOW"] * s[3] for s in ok)
        and a["close"] < b["close"] < r["close"]
        and a["open"] <= b["open"] <= a["close"]
        and b["open"] <= r["open"] <= b["close"]
    ):
        found.append(("Three White Soldiers", "bullish"))
    if (
        all(_bear(x) for x in bars)
        and all(s[0] and s[2] <= T["SOLDIER_SHADOW"] * s[3] for s in ok)
        and a["close"] > b["close"] > r["close"]
        and a["close"] <= b["open"] <= a["open"]
        and b["close"] <= r["open"] <= b["open"]
    ):
        found.append(("Three Black Crows", "bearish"))
    return found


Detector = Callable[[pd.DataFrame, int], Found]
DETECTORS: tuple[Detector, ...] = (_single_bar, _engulfing, _stars, _soldiers_and_crows)


def detect_at(df: pd.DataFrame, i: int) -> Found:
    """Patterns completing on bar i -> [(name, bullish|bearish|neutral)]."""
    _, rng, _, _ = _parts(df.iloc[i])
    if rng <= 0:
        return []
    return [hit for detector in DETECTORS for hit in detector(df, i)]


def scan(df: pd.DataFrame, lookback: int = PATTERN_LOOKBACK) -> list[dict[str, Any]]:
    out = []
    for i in range(max(0, len(df) - lookback), len(df)):
        for name, direction in detect_at(df, i):
            out.append(
                {
                    "date": df.index[i].strftime("%Y-%m-%d"),
                    "bars_ago": len(df) - 1 - i,
                    "pattern": name,
                    "direction": direction,
                    "high": float(df["high"].iloc[i]),
                    "low": float(df["low"].iloc[i]),
                }
            )
    return out


def describe_last_candle(df: pd.DataFrame) -> str:
    r = df.iloc[-1]
    body, rng, up, lo = _parts(r)
    if rng <= 0:
        return "Last session had no range (no trades or a locked price)."
    colour = "bullish (green)" if _bull(r) else "bearish (red)" if _bear(r) else "flat"
    return (
        f"Last candle is {colour}: body {body / rng:.0%} of its range, upper wick {up / rng:.0%}, "
        f"lower wick {lo / rng:.0%}, closing {(r['close'] - r['low']) / rng:.0%} of the way up the range."
    )
