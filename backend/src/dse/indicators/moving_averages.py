# ruff: noqa: E501 — indicator descriptions are one readable sentence each
"""Moving averages. All overlay on the price chart and use the close unless stated otherwise."""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from dse.indicators._params import MOVING_AVERAGES as G
from dse.indicators._params import length, n, number
from dse.indicators.base import Output, indicator
from dse.indicators.maths import (
    ema,
    frame,
    linreg,
    rma,
    safe_div,
    sma,
    typical_price,
    window_dot,
    wma,
)

Params = Mapping[str, float]
VALUE = (Output("value", "Value"),)


@indicator(
    id="sma",
    name="Simple Moving Average",
    group=G,
    placement="overlay",
    params=[length(20)],
    outputs=VALUE,
    description="The plain average of the last N closing prices; price above it suggests an uptrend, below it a downtrend.",
)
def _sma(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=sma(df["close"], n(p)))


@indicator(
    id="ema",
    name="Exponential Moving Average",
    group=G,
    placement="overlay",
    params=[length(20)],
    outputs=VALUE,
    description="An average of recent closes that weights newer prices more, so it reacts faster than a simple average.",
)
def _ema(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=ema(df["close"], n(p)))


@indicator(
    id="wma",
    name="Weighted Moving Average",
    group=G,
    placement="overlay",
    params=[length(20, hi=500)],
    outputs=VALUE,
    description="An average of the last N closes where each newer bar counts proportionally more than the one before.",
)
def _wma(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=wma(df["close"], n(p)))


@indicator(
    id="vwma",
    name="Volume Weighted Moving Average",
    group=G,
    placement="overlay",
    params=[length(20)],
    outputs=VALUE,
    description="A moving average that gives more weight to bars with heavy trading volume, so busy days matter more.",
)
def _vwma(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    k = n(p)
    return frame(df.index, value=safe_div(sma(df["close"] * df["volume"], k), sma(df["volume"], k)))


def hull(s: pd.Series, k: int) -> pd.Series:
    half = max(k // 2, 1)
    root = max(round(float(np.sqrt(k))), 1)
    return wma(2.0 * wma(s, half) - wma(s, k), root)


@indicator(
    id="hma",
    name="Hull Moving Average",
    group=G,
    placement="overlay",
    params=[length(21, lo=2)],
    outputs=VALUE,
    description="A fast, smooth moving average that cuts lag; a turn up or down in its slope is read as a trend change.",
)
def _hma(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=hull(df["close"], n(p)))


@indicator(
    id="dema",
    name="Double EMA",
    group=G,
    placement="overlay",
    params=[length(20)],
    outputs=VALUE,
    description="An exponential average with the lag partly removed (2*EMA minus EMA of EMA), so it hugs price more closely.",
)
def _dema(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    e1 = ema(df["close"], n(p))
    return frame(df.index, value=2.0 * e1 - ema(e1, n(p)))


@indicator(
    id="tema",
    name="Triple EMA",
    group=G,
    placement="overlay",
    params=[length(20)],
    outputs=VALUE,
    description="A three-times smoothed exponential average corrected for lag, reacting quickly while staying smooth.",
)
def _tema(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    e1 = ema(df["close"], n(p))
    e2 = ema(e1, n(p))
    return frame(df.index, value=3.0 * e1 - 3.0 * e2 + ema(e2, n(p)))


@indicator(
    id="smma",
    name="Smoothed Moving Average",
    group=G,
    placement="overlay",
    params=[length(20)],
    outputs=VALUE,
    description="A slow, very smooth average (Wilder smoothing) that ignores small wiggles and follows the broad trend.",
)
def _smma(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=rma(df["close"], n(p)))


@indicator(
    id="lsma",
    name="Least Squares Moving Average",
    group=G,
    placement="overlay",
    params=[length(25, lo=2), length(0, key="offset", label="Offset", lo=0, hi=100)],
    outputs=VALUE,
    description="The end of a best-fit straight line through the last N closes; it shows the current linear trend.",
)
def _lsma(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=linreg(df["close"], n(p), n(p, "offset")))


@indicator(
    id="alma",
    name="Arnaud Legoux Moving Average",
    group=G,
    placement="overlay",
    params=[
        length(9, lo=2),
        number(0.85, "offset", "Offset", 0.0, 1.0),
        number(6.0, "sigma", "Sigma", 0.5, 50.0),
    ],
    outputs=VALUE,
    description="A smooth, low-lag average that weights the window with a bell curve placed near the newest bars.",
)
def _alma(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    k = n(p)
    m = np.floor(p["offset"] * (k - 1))
    s = k / p["sigma"]
    i = np.arange(k, dtype="float64")
    w = np.exp(-((i - m) ** 2) / (2.0 * s * s))
    return frame(df.index, value=window_dot(df["close"], w / w.sum()))


@indicator(
    id="mcginley",
    name="McGinley Dynamic",
    group=G,
    placement="overlay",
    params=[length(14)],
    outputs=VALUE,
    description="A self-adjusting average that speeds up when price moves fast and slows down when it is quiet.",
)
def _mcginley(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    k = n(p)
    c = df["close"].to_numpy(dtype="float64")
    seed = ema(df["close"], k).to_numpy(dtype="float64")
    out = np.full(len(c), np.nan)
    valid = np.flatnonzero(~np.isnan(seed))
    if len(valid):
        i0 = int(valid[0])
        md = float(seed[i0])
        out[i0] = md
        for i in range(i0 + 1, len(c)):
            if md != 0.0 and not np.isnan(c[i]):
                md += (c[i] - md) / (k * (c[i] / md) ** 4)
            out[i] = md
    return frame(df.index, value=out)


@indicator(
    id="kama",
    name="Moving Average Adaptive (Kaufman)",
    group=G,
    placement="overlay",
    params=[
        length(10),
        length(2, key="fast", label="Fast length"),
        length(30, key="slow", label="Slow length"),
    ],
    outputs=VALUE,
    description="An average that flattens in choppy, sideways markets and speeds up in clean trends (Kaufman's adaptive MA).",
)
def _kama(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    k = n(p)
    close = df["close"]
    er = safe_div((close - close.shift(k)).abs(), close.diff().abs().rolling(k, min_periods=k).sum()).fillna(
        0.0
    )
    fast, slow = 2.0 / (n(p, "fast") + 1), 2.0 / (n(p, "slow") + 1)
    sc = ((er * (fast - slow) + slow) ** 2).to_numpy(dtype="float64")
    c = close.to_numpy(dtype="float64")
    out = np.full(len(c), np.nan)
    if len(c) > k:
        prev = c[k - 1]
        for i in range(k, len(c)):
            prev = prev + sc[i] * (c[i] - prev)
            out[i] = prev
    return frame(df.index, value=out)


@indicator(
    id="ma_cross",
    name="MA Cross",
    group=G,
    placement="overlay",
    params=[length(9, key="fast", label="Fast length"), length(21, key="slow", label="Slow length")],
    outputs=(Output("fast", "Fast SMA"), Output("slow", "Slow SMA")),
    description="Two simple averages; a buy signal is read when the fast one crosses above the slow one, a sell when below.",
)
def _ma_cross(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, fast=sma(df["close"], n(p, "fast")), slow=sma(df["close"], n(p, "slow")))


@indicator(
    id="ema_cross",
    name="EMA Cross",
    group=G,
    placement="overlay",
    params=[length(9, key="fast", label="Fast length"), length(21, key="slow", label="Slow length")],
    outputs=(Output("fast", "Fast EMA"), Output("slow", "Slow EMA")),
    description="Two exponential averages; the fast one crossing above the slow one is read as bullish, below as bearish.",
)
def _ema_cross(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, fast=ema(df["close"], n(p, "fast")), slow=ema(df["close"], n(p, "slow")))


GUPPY = (3, 5, 8, 10, 12, 15, 30, 35, 40, 45, 50, 60)


@indicator(
    id="guppy",
    name="Guppy Multiple Moving Average",
    group=G,
    placement="overlay",
    outputs=[Output(f"g{i + 1}", f"EMA {k}") for i, k in enumerate(GUPPY)],
    description="Two bundles of EMAs (short-term traders and long-term investors); a wide, fanned-out bundle signals a strong trend.",
)
def _guppy(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, **{f"g{i + 1}": ema(df["close"], k) for i, k in enumerate(GUPPY)})


@indicator(
    id="ma_ribbon",
    name="Moving Average Multiple",
    group=G,
    placement="overlay",
    params=[
        length(20, key="m1", label="Length 1"),
        length(50, key="m2", label="Length 2"),
        length(100, key="m3", label="Length 3"),
        length(200, key="m4", label="Length 4"),
    ],
    outputs=[Output(f"m{i}", f"SMA {i}") for i in range(1, 5)],
    description="Four simple averages of different lengths at once; when they are stacked in order the trend is clear.",
)
def _ma_ribbon(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, **{f"m{i}": sma(df["close"], n(p, f"m{i}")) for i in range(1, 5)})


@indicator(
    id="vwap",
    name="VWAP",
    group=G,
    placement="overlay",
    outputs=VALUE,
    description="The volume-weighted average price since the start of the session (intraday) or month (daily); a fair-price line.",
)
def _vwap(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """Anchored VWAP of the typical price.

    Anchor rule: if the index has more than one bar on some calendar date the data is intraday and the sum resets
    every calendar date; otherwise (one bar per date) it is daily data and the sum resets every calendar month.
    The rule looks at the data it is given, so a very short intraday prefix with one bar per date is treated as daily.
    """
    idx = pd.DatetimeIndex(df.index)
    intraday = bool(idx.normalize().duplicated().any())
    keys = idx.normalize() if intraday else pd.Index(idx.year * 100 + idx.month)  # calendar month, tz-safe
    pv = (typical_price(df) * df["volume"]).groupby(keys).cumsum()
    vol = df["volume"].groupby(keys).cumsum()
    return frame(df.index, value=safe_div(pv, vol))
