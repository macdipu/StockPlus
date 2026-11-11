"""Candlestick pattern detection with explicit, tunable thresholds.

Definitions (body = |close-open|, range = high-low, upper/lower = shadows):
  doji            body <= DOJI_BODY * range
  marubozu        body >= MARUBOZU_BODY * range            (bullish if close>open)
  hammer          lower >= LONG_SHADOW * body, upper <= SHORT_SHADOW * range, in a down-trend
  inverted hammer upper >= LONG_SHADOW * body, lower <= SHORT_SHADOW * range, in a down-trend
  shooting star   same shape as inverted hammer, in an up-trend
  engulfing       body of bar 2 fully covers body of bar 1, opposite colours
  morning star    long bearish bar, small-body bar (<= STAR_BODY * bar1 body), bullish bar closing above bar1 midpoint
  evening star    mirror image of morning star
  three soldiers  3 bullish bars, rising closes, each opens inside prior body, each body >= SOLDIER_BODY * range,
                  upper shadow <= SOLDIER_SHADOW * range (three black crows: mirror image)
Trend context = close before the pattern vs close TREND_BARS earlier.
"""
from __future__ import annotations

import pandas as pd

import config as C

T = {
    "DOJI_BODY": 0.10,
    "MARUBOZU_BODY": 0.90,
    "LONG_SHADOW": 2.0,
    "SHORT_SHADOW": 0.10,
    "MIN_BODY": 0.03,         # hammer-family needs at least a sliver of body (else it's a doji)
    "LONG_BODY": 0.60,        # "long" bar for stars: body >= LONG_BODY * range
    "STAR_BODY": 0.30,
    "SOLDIER_BODY": 0.50,
    "SOLDIER_SHADOW": 0.25,
    "TREND_BARS": 5,
}


def _parts(r) -> tuple[float, float, float, float]:
    o, h, l, c = r["open"], r["high"], r["low"], r["close"]
    rng = h - l
    return abs(c - o), rng, h - max(o, c), min(o, c) - l


def _bull(r) -> bool:
    return r["close"] > r["open"]


def _bear(r) -> bool:
    return r["close"] < r["open"]


def _trend(df: pd.DataFrame, i: int) -> str:
    """Trend leading into bar i (uses bars before i)."""
    j = i - 1
    if j - T["TREND_BARS"] < 0:
        return "flat"
    a, b = df["close"].iloc[j - T["TREND_BARS"]], df["close"].iloc[j]
    return "up" if b > a else "down" if b < a else "flat"


def detect_at(df: pd.DataFrame, i: int) -> list[tuple[str, str]]:
    """Patterns completing on bar i -> [(name, bullish|bearish|neutral)]."""
    r = df.iloc[i]
    body, rng, up, lo = _parts(r)
    found: list[tuple[str, str]] = []
    if rng <= 0:
        return found
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

    if i >= 1:
        p = df.iloc[i - 1]
        pb = abs(p["close"] - p["open"])
        if _bear(p) and _bull(r) and r["open"] <= p["close"] and r["close"] >= p["open"] and body > pb:
            found.append(("Bullish Engulfing", "bullish"))
        if _bull(p) and _bear(r) and r["open"] >= p["close"] and r["close"] <= p["open"] and body > pb:
            found.append(("Bearish Engulfing", "bearish"))

    if i >= 2:
        a, b = df.iloc[i - 2], df.iloc[i - 1]
        ab, ar, _, _ = _parts(a)
        bb = abs(b["close"] - b["open"])
        long_a = ar > 0 and ab >= T["LONG_BODY"] * ar
        small_b = bb <= T["STAR_BODY"] * ab
        mid_a = (a["open"] + a["close"]) / 2
        if long_a and small_b and _bear(a) and _bull(r) and r["close"] > mid_a:
            found.append(("Morning Star", "bullish"))
        if long_a and small_b and _bull(a) and _bear(r) and r["close"] < mid_a:
            found.append(("Evening Star", "bearish"))

        bars = [a, b, r]
        def strong(x):
            xb, xr, xu, xl = _parts(x)
            return xr > 0 and xb >= T["SOLDIER_BODY"] * xr, xu, xl, xr
        ok = [strong(x) for x in bars]
        if all(_bull(x) for x in bars) \
                and all(s[0] and s[1] <= T["SOLDIER_SHADOW"] * s[3] for s in ok) \
                and a["close"] < b["close"] < r["close"] \
                and a["open"] <= b["open"] <= a["close"] and b["open"] <= r["open"] <= b["close"]:
            found.append(("Three White Soldiers", "bullish"))
        if all(_bear(x) for x in bars) \
                and all(s[0] and s[2] <= T["SOLDIER_SHADOW"] * s[3] for s in ok) \
                and a["close"] > b["close"] > r["close"] \
                and a["close"] <= b["open"] <= a["open"] and b["close"] <= r["open"] <= b["open"]:
            found.append(("Three Black Crows", "bearish"))
    return found


def scan(df: pd.DataFrame, lookback: int = C.PATTERN_LOOKBACK) -> list[dict]:
    out = []
    for i in range(max(0, len(df) - lookback), len(df)):
        for name, direction in detect_at(df, i):
            out.append({"date": df.index[i].strftime("%Y-%m-%d"), "bars_ago": len(df) - 1 - i,
                        "pattern": name, "direction": direction,
                        "high": float(df["high"].iloc[i]), "low": float(df["low"].iloc[i])})
    return out


def describe_last_candle(df: pd.DataFrame) -> str:
    r = df.iloc[-1]
    body, rng, up, lo = _parts(r)
    if rng <= 0:
        return "Last session had no range (no trades or a locked price)."
    colour = "bullish (green)" if _bull(r) else "bearish (red)" if _bear(r) else "flat"
    return (f"Last candle is {colour}: body {body / rng:.0%} of its range, upper wick {up / rng:.0%}, "
            f"lower wick {lo / rng:.0%}, closing {(r['close'] - r['low']) / rng:.0%} of the way up the range.")
