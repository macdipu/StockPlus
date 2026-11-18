# ruff: noqa: E501 — indicator descriptions are one readable sentence each
"""Trend indicators: overlays (Supertrend, SAR, Alligator, Zig Zag) and trend-strength panes (ADX, Aroon...)."""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from dse.indicators._params import TREND as G
from dse.indicators._params import length, n, number
from dse.indicators.base import Output, indicator
from dse.indicators.maths import (
    atr,
    bars_since_extreme,
    ema,
    frame,
    highest,
    lowest,
    median_price,
    rma,
    safe_div,
    true_range,
)

Params = Mapping[str, float]


@indicator(
    id="supertrend",
    name="Supertrend",
    group=G,
    placement="overlay",
    params=[length(10, key="atr_length", label="ATR length"), number(3.0, "factor", "Factor", 0.5, 20.0)],
    outputs=(Output("up", "Uptrend support"), Output("down", "Downtrend resistance")),
    description="A trailing line that sits under price in an uptrend and over price in a downtrend; a flip of colour signals a trend change.",
)
def _supertrend(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    h, lo, c = (df[k].to_numpy(dtype="float64") for k in ("high", "low", "close"))
    a = atr(df, n(p, "atr_length")).to_numpy(dtype="float64")
    ub, lb = (h + lo) / 2.0 + p["factor"] * a, (h + lo) / 2.0 - p["factor"] * a
    size = len(c)
    up, down = np.full(size, np.nan), np.full(size, np.nan)
    valid = np.flatnonzero(~np.isnan(a))
    if len(valid):
        i0 = int(valid[0])
        fub, flb, bull = ub[i0], lb[i0], True
        for i in range(i0, size):
            if i > i0:
                fub = ub[i] if (ub[i] < fub or c[i - 1] > fub) else fub
                flb = lb[i] if (lb[i] > flb or c[i - 1] < flb) else flb
                bull = c[i] >= flb if bull else c[i] > fub
            if bull:
                up[i] = flb
            else:
                down[i] = fub
    return frame(df.index, up=up, down=down)


@indicator(
    id="psar",
    name="Parabolic SAR",
    group=G,
    placement="overlay",
    params=[
        number(0.02, "start", "Start", 0.001, 1.0),
        number(0.02, "increment", "Increment", 0.001, 1.0),
        number(0.2, "maximum", "Maximum", 0.01, 1.0),
    ],
    outputs=(Output("sar", "SAR", "dots"),),
    description="Dots that trail price and accelerate with the trend: dots under price are bullish, above are bearish, and a flip warns of a reversal.",
)
def _psar(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    h, lo, c = (df[k].to_numpy(dtype="float64") for k in ("high", "low", "close"))
    start, inc, top = p["start"], p["increment"], p["maximum"]
    out = np.full(len(c), np.nan)
    if len(c) >= 2:
        rising = c[1] >= c[0]
        sar = lo[0] if rising else h[0]
        ep = h[0] if rising else lo[0]
        af = start
        for i in range(1, len(c)):
            sar = sar + af * (ep - sar)
            back = i - 2 if i >= 2 else i - 1
            if rising:
                sar = min(sar, lo[i - 1], lo[back])
                if lo[i] < sar:
                    rising, sar, ep, af = False, ep, lo[i], start
                elif h[i] > ep:
                    ep, af = h[i], min(af + inc, top)
            else:
                sar = max(sar, h[i - 1], h[back])
                if h[i] > sar:
                    rising, sar, ep, af = True, ep, h[i], start
                elif lo[i] < ep:
                    ep, af = lo[i], min(af + inc, top)
            out[i] = sar
    return frame(df.index, sar=out)


def _directional(df: pd.DataFrame, k: int, smoothing: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Wilder's +DI, -DI and ADX."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0).where(up.notna())
    minus_dm = down.where((down > up) & (down > 0), 0.0).where(down.notna())
    tr = rma(true_range(df), k)
    plus_di = 100.0 * safe_div(rma(plus_dm, k), tr)
    minus_di = 100.0 * safe_div(rma(minus_dm, k), tr)
    adx = 100.0 * rma(safe_div((plus_di - minus_di).abs(), plus_di + minus_di), smoothing)
    return plus_di, minus_di, adx


_DMI_PARAMS = [
    length(14, key="length", label="DI length"),
    length(14, key="smoothing", label="ADX smoothing"),
]


@indicator(
    id="adx",
    name="Average Directional Index",
    group=G,
    placement="pane",
    params=_DMI_PARAMS,
    outputs=(Output("adx", "ADX"), Output("plus_di", "+DI"), Output("minus_di", "-DI")),
    description="ADX measures how strong a trend is (above about 25 is trending, below 20 is weak) without saying which way; +DI and -DI show direction.",
    scale=(0, 100),
    levels=(20, 25),
)
def _adx(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    plus_di, minus_di, adx = _directional(df, n(p), n(p, "smoothing"))
    return frame(df.index, adx=adx, plus_di=plus_di, minus_di=minus_di)


@indicator(
    id="dmi",
    name="Directional Movement",
    group=G,
    placement="pane",
    params=_DMI_PARAMS,
    outputs=(Output("plus_di", "+DI"), Output("minus_di", "-DI"), Output("adx", "ADX")),
    description="+DI above -DI means buyers are in control, -DI above +DI means sellers; ADX adds how strong the trend is.",
    scale=(0, 100),
    levels=(20,),
)
def _dmi(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    plus_di, minus_di, adx = _directional(df, n(p), n(p, "smoothing"))
    return frame(df.index, plus_di=plus_di, minus_di=minus_di, adx=adx)


def _aroon(df: pd.DataFrame, k: int) -> tuple[pd.Series, pd.Series]:
    up = 100.0 * (k - bars_since_extreme(df["high"], k + 1, highest_=True)) / k
    down = 100.0 * (k - bars_since_extreme(df["low"], k + 1, highest_=False)) / k
    return up, down


@indicator(
    id="aroon",
    name="Aroon",
    group=G,
    placement="pane",
    params=[length(14, lo=2)],
    outputs=(Output("up", "Aroon Up"), Output("down", "Aroon Down")),
    description="Measures how recently price made its highest high and lowest low; Aroon Up near 100 means a fresh high, so an uptrend.",
    scale=(0, 100),
    levels=(30, 70),
)
def _aroon_ind(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    up, down = _aroon(df, n(p))
    return frame(df.index, up=up, down=down)


@indicator(
    id="aroon_osc",
    name="Aroon Oscillator",
    group=G,
    placement="pane",
    params=[length(14, lo=2)],
    outputs=(Output("value", "Aroon Oscillator"),),
    description="Aroon Up minus Aroon Down: positive means highs are more recent than lows (uptrend), negative the opposite.",
    scale=(-100, 100),
    levels=(0,),
)
def _aroon_osc(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    up, down = _aroon(df, n(p))
    return frame(df.index, value=up - down)


@indicator(
    id="vortex",
    name="Vortex Indicator",
    group=G,
    placement="pane",
    params=[length(14, lo=2)],
    outputs=(Output("plus", "VI+"), Output("minus", "VI-")),
    description="Two lines that capture upward and downward movement; VI+ crossing above VI- suggests a new uptrend.",
    levels=(1,),
)
def _vortex(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    k = n(p)
    tr = true_range(df).rolling(k, min_periods=k).sum()
    vm_plus = (df["high"] - df["low"].shift(1)).abs().rolling(k, min_periods=k).sum()
    vm_minus = (df["low"] - df["high"].shift(1)).abs().rolling(k, min_periods=k).sum()
    return frame(df.index, plus=safe_div(vm_plus, tr), minus=safe_div(vm_minus, tr))


@indicator(
    id="chop",
    name="Choppiness Index",
    group=G,
    placement="pane",
    params=[length(14, lo=2)],
    outputs=(Output("value", "Choppiness"),),
    description="Tells trending from sideways markets: above 61.8 the market is choppy and range-bound, below 38.2 it is trending.",
    scale=(0, 100),
    levels=(38.2, 61.8),
)
def _chop(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    k = n(p)
    total = true_range(df).rolling(k, min_periods=k).sum()
    span = highest(df["high"], k) - lowest(df["low"], k)
    return frame(df.index, value=100.0 * np.log10(safe_div(total, span)) / np.log10(k))


@indicator(
    id="zigzag",
    name="Zig Zag",
    group=G,
    placement="overlay",
    params=[number(5.0, "deviation", "Deviation %", 0.1, 50.0)],
    outputs=(Output("value", "Zig Zag"),),
    description="Connects the major swing highs and lows, ignoring moves smaller than the deviation percent; the last leg can change as new bars arrive.",
    repaints=True,
)
def _zigzag(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """Swing pivots on high/low, each confirmed by a reversal of `deviation` percent; the last leg ends at the
    current extreme (it repaints). Pivots are joined by straight lines."""
    h, lo = df["high"].to_numpy(dtype="float64"), df["low"].to_numpy(dtype="float64")
    d = p["deviation"] / 100.0
    size = len(h)
    piv_i: list[int] = []
    piv_v: list[float] = []
    if size:
        hi_v, hi_i, lo_v, lo_i = h[0], 0, lo[0], 0
        direction, ext_v, ext_i = 0, 0.0, 0
        for i in range(1, size):
            if direction == 0:
                if h[i] > hi_v:
                    hi_v, hi_i = h[i], i
                if lo[i] < lo_v:
                    lo_v, lo_i = lo[i], i
                if hi_i > lo_i and hi_v >= lo_v * (1 + d):
                    piv_i.append(lo_i)
                    piv_v.append(lo_v)
                    direction, ext_v, ext_i = 1, hi_v, hi_i
                elif lo_i > hi_i and lo_v <= hi_v * (1 - d):
                    piv_i.append(hi_i)
                    piv_v.append(hi_v)
                    direction, ext_v, ext_i = -1, lo_v, lo_i
            elif direction == 1:
                if h[i] > ext_v:
                    ext_v, ext_i = h[i], i
                elif lo[i] <= ext_v * (1 - d):
                    piv_i.append(ext_i)
                    piv_v.append(ext_v)
                    direction, ext_v, ext_i = -1, lo[i], i
            elif lo[i] < ext_v:
                ext_v, ext_i = lo[i], i
            elif h[i] >= ext_v * (1 + d):
                piv_i.append(ext_i)
                piv_v.append(ext_v)
                direction, ext_v, ext_i = 1, h[i], i
        if direction != 0:
            piv_i.append(ext_i)
            piv_v.append(ext_v)
    out = np.full(size, np.nan)
    if len(piv_i) >= 2:
        span = np.arange(piv_i[0], piv_i[-1] + 1)
        out[span] = np.interp(span, piv_i, piv_v)
    return frame(df.index, value=out)


@indicator(
    id="williams_alligator",
    name="Williams Alligator",
    group=G,
    placement="overlay",
    params=[
        length(13, key="jaw", label="Jaw length"),
        length(8, key="teeth", label="Teeth length"),
        length(5, key="lips", label="Lips length"),
        length(8, key="jaw_shift", label="Jaw shift", lo=0, hi=50),
        length(5, key="teeth_shift", label="Teeth shift", lo=0, hi=50),
        length(3, key="lips_shift", label="Lips shift", lo=0, hi=50),
    ],
    outputs=(Output("jaw", "Jaw"), Output("teeth", "Teeth"), Output("lips", "Lips")),
    description="Three smoothed averages (jaw, teeth, lips): when they are tangled the market is asleep, when they fan out a trend is feeding.",
)
def _alligator(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    mp = median_price(df)
    return frame(
        df.index,
        jaw=rma(mp, n(p, "jaw")).shift(n(p, "jaw_shift")),
        teeth=rma(mp, n(p, "teeth")).shift(n(p, "teeth_shift")),
        lips=rma(mp, n(p, "lips")).shift(n(p, "lips_shift")),
    )


@indicator(
    id="mass_index",
    name="Mass Index",
    group=G,
    placement="pane",
    params=[
        length(9, key="ema_length", label="EMA length"),
        length(25, key="sum_length", label="Sum length"),
    ],
    outputs=(Output("value", "Mass Index"),),
    description="Watches the widening and narrowing of the high-low range; a rise above 27 that falls back below 26.5 warns of a reversal.",
    levels=(26.5, 27),
)
def _mass(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    e1 = ema(df["high"] - df["low"], n(p, "ema_length"))
    ratio = safe_div(e1, ema(e1, n(p, "ema_length")))
    return frame(df.index, value=ratio.rolling(n(p, "sum_length"), min_periods=n(p, "sum_length")).sum())


@indicator(
    id="elder_ray",
    name="Elder-Ray Index",
    group=G,
    placement="pane",
    params=[length(13)],
    outputs=(
        Output("bull_power", "Bull power", "histogram"),
        Output("bear_power", "Bear power", "histogram"),
    ),
    description="Bull power is how far the high is above an EMA and bear power how far the low is below it, showing buyer and seller strength.",
    levels=(0,),
)
def _elder(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    e = ema(df["close"], n(p))
    return frame(df.index, bull_power=df["high"] - e, bear_power=df["low"] - e)


@indicator(
    id="trix",
    name="TRIX",
    group=G,
    placement="pane",
    params=[length(15)],
    outputs=(Output("value", "TRIX"),),
    description="The rate of change of a triple-smoothed EMA of price; crossing above zero is bullish and below zero bearish.",
    levels=(0,),
)
def _trix(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    e3 = ema(ema(ema(np.log(df["close"]), n(p)), n(p)), n(p))
    return frame(df.index, value=10000.0 * e3.diff())
