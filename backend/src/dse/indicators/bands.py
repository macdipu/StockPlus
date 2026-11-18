# ruff: noqa: E501 — indicator descriptions are one readable sentence each
"""Bands and channels. All overlay on the price chart (price units)."""

from collections.abc import Mapping

import pandas as pd

from dse.indicators._params import BANDS as G
from dse.indicators._params import length, n, number
from dse.indicators.base import Output, indicator
from dse.indicators.maths import atr, ema, frame, highest, lowest, sma, stdev

Params = Mapping[str, float]
UPPER_LOWER = (Output("upper", "Upper"), Output("lower", "Lower"))
BASIS = Output("basis", "Basis")


@indicator(
    id="bbands",
    name="Bollinger Bands",
    group=G,
    placement="overlay",
    params=[length(20), number(2.0, "mult", "Standard deviations", 0.1, 10.0)],
    outputs=(BASIS, *UPPER_LOWER),
    description="An average with bands set N standard deviations away; price near the outer bands is stretched, tight bands warn of a squeeze.",
)
def _bbands(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    basis = sma(df["close"], n(p))
    dev = p["mult"] * stdev(df["close"], n(p))
    return frame(df.index, basis=basis, upper=basis + dev, lower=basis - dev)


@indicator(
    id="keltner",
    name="Keltner Channels",
    group=G,
    placement="overlay",
    params=[
        length(20),
        length(10, key="atr_length", label="ATR length"),
        number(2.0, "mult", "ATR multiplier", 0.1, 20.0),
    ],
    outputs=(BASIS, *UPPER_LOWER),
    description="An EMA with bands a multiple of the average true range away; closes outside the channel suggest a strong move.",
)
def _keltner(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    basis = ema(df["close"], n(p))
    rng = p["mult"] * atr(df, n(p, "atr_length"))
    return frame(df.index, basis=basis, upper=basis + rng, lower=basis - rng)


@indicator(
    id="donchian",
    name="Donchian Channels",
    group=G,
    placement="overlay",
    params=[length(20)],
    outputs=(*UPPER_LOWER, BASIS),
    description="The highest high and lowest low of the last N bars with their midpoint; a close above the top is a breakout.",
)
def _donchian(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    up, lo = highest(df["high"], n(p)), lowest(df["low"], n(p))
    return frame(df.index, upper=up, lower=lo, basis=(up + lo) / 2.0)


@indicator(
    id="price_channel",
    name="Price Channel",
    group=G,
    placement="overlay",
    params=[length(20)],
    outputs=UPPER_LOWER,
    description="The highest high and lowest low of the N bars before today; price closing outside it is a breakout.",
)
def _price_channel(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """Like Donchian but built from the previous N bars only, so the current bar can break out of it."""
    return frame(
        df.index,
        upper=highest(df["high"], n(p)).shift(1),
        lower=lowest(df["low"], n(p)).shift(1),
    )


@indicator(
    id="envelopes",
    name="Envelopes",
    group=G,
    placement="overlay",
    params=[length(20), number(10.0, "percent", "Percent", 0.1, 50.0)],
    outputs=(BASIS, *UPPER_LOWER),
    description="A moving average with lines a fixed percentage above and below it; price reaching a line is stretched.",
)
def _envelopes(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    basis = sma(df["close"], n(p))
    k = p["percent"] / 100.0
    return frame(df.index, basis=basis, upper=basis * (1.0 + k), lower=basis * (1.0 - k))


@indicator(
    id="mac",
    name="Moving Average Channel",
    group=G,
    placement="overlay",
    params=[length(20)],
    outputs=(*UPPER_LOWER, BASIS),
    description="A channel made from the average of the highs and the average of the lows; price above it is strong, below weak.",
)
def _mac(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    up, lo = sma(df["high"], n(p)), sma(df["low"], n(p))
    return frame(df.index, upper=up, lower=lo, basis=(up + lo) / 2.0)


@indicator(
    id="chande_kroll",
    name="Chande Kroll Stop",
    group=G,
    placement="overlay",
    params=[
        length(10, key="p", label="ATR period"),
        number(1.0, "x", "ATR multiplier", 0.1, 20.0),
        length(9, key="q", label="Stop period"),
    ],
    outputs=(Output("long_stop", "Long stop"), Output("short_stop", "Short stop")),
    description="Trailing stop levels based on volatility: exit longs below the long stop, shorts above the short stop.",
)
def _chande_kroll(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """Textbook labelling: the long stop sits below price (protects longs), the short stop above price."""
    a = atr(df, n(p, "p"))
    first_high = highest(df["high"], n(p, "p")) - p["x"] * a
    first_low = lowest(df["low"], n(p, "p")) + p["x"] * a
    return frame(
        df.index,
        long_stop=highest(first_high, n(p, "q")),
        short_stop=lowest(first_low, n(p, "q")),
    )


@indicator(
    id="ichimoku",
    name="Ichimoku Cloud",
    group=G,
    placement="overlay",
    params=[
        length(9, key="conversion", label="Conversion length"),
        length(26, key="base", label="Base length"),
        length(52, key="span_b", label="Span B length"),
        length(26, key="displacement", label="Displacement", lo=1, hi=100),
    ],
    outputs=(
        Output("conversion", "Conversion line"),
        Output("base", "Base line"),
        Output("leading_a", "Leading span A"),
        Output("leading_b", "Leading span B"),
    ),
    description=(
        "A cloud of support and resistance: price above the cloud is bullish, below bearish. "
        "The lagging span is omitted because it would need future bars."
    ),
)
def _ichimoku(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """Leading spans are the values computed `displacement` bars ago, shifted forward (causal)."""

    def mid(k: int) -> pd.Series:
        return (highest(df["high"], k) + lowest(df["low"], k)) / 2.0

    conv, base = mid(n(p, "conversion")), mid(n(p, "base"))
    d = n(p, "displacement")
    return frame(
        df.index,
        conversion=conv,
        base=base,
        leading_a=((conv + base) / 2.0).shift(d),
        leading_b=mid(n(p, "span_b")).shift(d),
    )


@indicator(
    id="pivot_points",
    name="Pivot Points Standard",
    group=G,
    placement="overlay",
    outputs=(
        Output("pivot", "Pivot"),
        Output("r1", "R1"),
        Output("r2", "R2"),
        Output("s1", "S1"),
        Output("s2", "S2"),
    ),
    description="Support (S) and resistance (R) levels computed from the previous bar's high, low and close.",
)
def _pivot_points(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    h, lo, c = df["high"].shift(1), df["low"].shift(1), df["close"].shift(1)
    pivot = (h + lo + c) / 3.0
    rng = h - lo
    return frame(
        df.index, pivot=pivot, r1=2.0 * pivot - lo, r2=pivot + rng, s1=2.0 * pivot - h, s2=pivot - rng
    )


@indicator(
    id="week52",
    name="52 Week High/Low",
    group=G,
    placement="overlay",
    params=[length(252, lo=5, hi=1000)],
    outputs=(Output("high", "High"), Output("low", "Low")),
    description="The highest high and lowest low of the last 252 trading days (about a year); shows how close price is to its yearly extremes.",
)
def _week52(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, high=highest(df["high"], n(p)), low=lowest(df["low"], n(p)))


FIB = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
FIB_KEYS = ("l0", "l236", "l382", "l500", "l618", "l786", "l1000")


@indicator(
    id="fib_retracement",
    name="Auto Fibonacci Retracement",
    group=G,
    placement="overlay",
    params=[length(100, lo=2)],
    outputs=[Output(k, f"{lv:g}") for k, lv in zip(FIB_KEYS, FIB, strict=True)],
    description="Fibonacci levels drawn between the highest high and lowest low of the last N bars, often watched as pullback support or resistance.",
)
def _fib(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """Rolling levels: level r = highest high - r * (highest high - lowest low), so 0 is the high and 1 the low."""
    hh, ll = highest(df["high"], n(p)), lowest(df["low"], n(p))
    return frame(df.index, **{k: hh - lv * (hh - ll) for k, lv in zip(FIB_KEYS, FIB, strict=True)})
