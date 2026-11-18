# ruff: noqa: E501 — indicator descriptions are one readable sentence each
"""Volume indicators. All in their own pane."""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from dse.indicators._params import VOLUME as G
from dse.indicators._params import length, n, number
from dse.indicators.base import Output, indicator
from dse.indicators.maths import ema, frame, safe_div, sma, typical_price

Params = Mapping[str, float]
VALUE = (Output("value", "Value"),)


@indicator(
    id="volume",
    name="Volume",
    group=G,
    placement="pane",
    params=[length(20, key="ma_length", label="MA length")],
    outputs=(Output("volume", "Volume", "histogram"), Output("ma", "Volume MA")),
    description="The number of shares traded each bar with its moving average; a price move on high volume is more convincing.",
)
def _volume(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, volume=df["volume"], ma=sma(df["volume"], n(p, "ma_length")))


def _direction(df: pd.DataFrame) -> pd.Series:
    """+1 when the close rose, -1 when it fell, 0 when unchanged; NaN on the first bar."""
    d = df["close"].diff()
    return pd.Series(np.sign(d), index=df.index).where(d.notna())


@indicator(
    id="obv",
    name="On Balance Volume",
    group=G,
    placement="pane",
    outputs=VALUE,
    description="A running total that adds volume on up days and subtracts it on down days; a rising line shows buying pressure.",
)
def _obv(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=(_direction(df) * df["volume"]).cumsum())


def _money_flow_multiplier(df: pd.DataFrame) -> pd.Series:
    """((close - low) - (high - close)) / (high - low); 0 when the bar has no range."""
    rng = df["high"] - df["low"]
    return safe_div((df["close"] - df["low"]) - (df["high"] - df["close"]), rng).fillna(0.0)


@indicator(
    id="ad",
    name="Accumulation/Distribution",
    group=G,
    placement="pane",
    outputs=VALUE,
    description="A running total of volume weighted by where each bar closes in its range; a rising line means accumulation, falling distribution.",
)
def _ad(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=(_money_flow_multiplier(df) * df["volume"]).cumsum())


@indicator(
    id="cmf",
    name="Chaikin Money Flow",
    group=G,
    placement="pane",
    params=[length(20)],
    outputs=VALUE,
    description="The share of volume that is buying versus selling over N bars; above zero means buying pressure, below zero selling.",
    scale=(-1, 1),
    levels=(0,),
)
def _cmf(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    flow = (_money_flow_multiplier(df) * df["volume"]).rolling(n(p), min_periods=n(p)).sum()
    return frame(df.index, value=safe_div(flow, df["volume"].rolling(n(p), min_periods=n(p)).sum()))


@indicator(
    id="chaikin_osc",
    name="Chaikin Oscillator",
    group=G,
    placement="pane",
    params=[length(3, key="fast", label="Fast length"), length(10, key="slow", label="Slow length")],
    outputs=VALUE,
    description="The difference between a fast and slow EMA of Accumulation/Distribution; above zero means buying pressure is building.",
    levels=(0,),
)
def _chaikin(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    ad = (_money_flow_multiplier(df) * df["volume"]).cumsum()
    return frame(df.index, value=ema(ad, n(p, "fast")) - ema(ad, n(p, "slow")))


@indicator(
    id="mfi",
    name="Money Flow Index",
    group=G,
    placement="pane",
    params=[length(14)],
    outputs=VALUE,
    description="A volume-weighted RSI on a 0-100 scale; above 80 suggests overbought, below 20 oversold.",
    scale=(0, 100),
    levels=(20, 80),
)
def _mfi(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    tp = typical_price(df)
    raw = tp * df["volume"]
    d = tp.diff()
    pos = raw.where(d > 0, 0.0).where(d.notna()).rolling(n(p), min_periods=n(p)).sum()
    neg = raw.where(d < 0, 0.0).where(d.notna()).rolling(n(p), min_periods=n(p)).sum()
    total = pos + neg
    return frame(
        df.index, value=(100.0 * pos / total.where(total != 0)).where(total != 0, 50.0).where(total.notna())
    )


@indicator(
    id="efi",
    name="Elder's Force Index",
    group=G,
    placement="pane",
    params=[length(13)],
    outputs=VALUE,
    description="Price change times volume, smoothed; positive means buyers are forcing price up, negative means sellers are pushing it down.",
    levels=(0,),
)
def _efi(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=ema(df["close"].diff() * df["volume"], n(p)))


@indicator(
    id="eom",
    name="Ease of Movement",
    group=G,
    placement="pane",
    params=[length(14), number(10000.0, "divisor", "Divisor", 1.0, 1e12)],
    outputs=VALUE,
    description="Shows how easily price moves per unit of volume; positive values mean price rises on light volume.",
    levels=(0,),
)
def _eom(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    mid = (df["high"] + df["low"]) / 2.0
    # distance moved / (volume / range) written without dividing by the range, so flat bars give 0, never inf
    raw = safe_div(mid.diff() * (df["high"] - df["low"]) * p["divisor"], df["volume"])
    return frame(df.index, value=sma(raw, n(p)))


@indicator(
    id="pvt",
    name="Price Volume Trend",
    group=G,
    placement="pane",
    outputs=VALUE,
    description="A running total of volume scaled by the percentage price change; like OBV but it counts how big each move was.",
)
def _pvt(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=(df["close"].pct_change() * df["volume"]).cumsum())


@indicator(
    id="net_volume",
    name="Net Volume",
    group=G,
    placement="pane",
    outputs=(Output("value", "Net Volume", "histogram"),),
    description="Volume counted as positive on up days and negative on down days; shows which side traded more shares each bar.",
    levels=(0,),
)
def _net_volume(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=_direction(df) * df["volume"])


@indicator(
    id="volume_osc",
    name="Volume Oscillator",
    group=G,
    placement="pane",
    params=[length(5, key="fast", label="Fast length"), length(10, key="slow", label="Slow length")],
    outputs=VALUE,
    description="The percentage gap between a fast and slow volume average; rising values mean volume is picking up.",
    levels=(0,),
)
def _volume_osc(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    slow = ema(df["volume"], n(p, "slow"))
    return frame(df.index, value=100.0 * safe_div(ema(df["volume"], n(p, "fast")) - slow, slow))


@indicator(
    id="klinger",
    name="Klinger Oscillator",
    group=G,
    placement="pane",
    params=[
        length(34, key="fast", label="Fast length"),
        length(55, key="slow", label="Slow length"),
        length(13, key="signal", label="Signal length"),
    ],
    outputs=(Output("kvo", "KVO"), Output("signal", "Signal")),
    description="Tracks long-term money flow with short-term sensitivity; the KVO crossing above its signal line is bullish.",
    levels=(0,),
)
def _klinger(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """Charting-platform version: signed volume (+ when the typical price rose, - when it fell) smoothed by two EMAs."""
    d = typical_price(df).diff()
    sv = df["volume"].where(d >= 0, -df["volume"]).where(d.notna())
    kvo = ema(sv, n(p, "fast")) - ema(sv, n(p, "slow"))
    return frame(df.index, kvo=kvo, signal=ema(kvo, n(p, "signal")))


@indicator(
    id="asi",
    name="Accumulative Swing Index",
    group=G,
    placement="pane",
    params=[number(0.5, "limit", "Limit move % of close", 0.01, 50.0)],
    outputs=VALUE,
    description="Wilder's running total of a swing index that judges the real strength of each bar; new highs in it confirm a price breakout.",
    levels=(0,),
)
def _asi(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """Wilder's swing index summed. Simplification: the limit move T is `limit`% of the previous close (stocks
    have no fixed futures limit), instead of a constant in price units."""
    o, h, lo, c = df["open"], df["high"], df["low"], df["close"]
    co, cp, op = c.shift(1), c, o.shift(1)
    a, b, rng = (h - co).abs(), (lo - co).abs(), h - lo
    carry = 0.25 * (co - op).abs()
    r = pd.Series(
        np.where(
            (a >= b) & (a >= rng),
            a - 0.5 * b + carry,
            np.where((b >= a) & (b >= rng), b - 0.5 * a + carry, rng + carry),
        ),
        index=df.index,
    )
    k = pd.concat([a, b], axis=1).max(axis=1)
    t = co * p["limit"] / 100.0
    si = (
        50.0 * ((cp - co) + 0.5 * (c - o) + 0.25 * (co - op)) / r.where(r != 0) * (k / t.where(t != 0))
    ).where(r != 0, 0.0)
    return frame(df.index, value=si.where(co.notna() & op.notna()).cumsum())
