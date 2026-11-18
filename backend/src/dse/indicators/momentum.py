# ruff: noqa: E501 — indicator descriptions are one readable sentence each
"""Momentum oscillators. All in their own pane."""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from dse.indicators._params import MOMENTUM as G
from dse.indicators._params import length, n
from dse.indicators.base import Output, indicator
from dse.indicators.maths import (
    ema,
    frame,
    highest,
    lowest,
    mean_abs_dev,
    median_price,
    percent_rank,
    rsi,
    safe_div,
    sma,
    stdev,
    wma,
)

Params = Mapping[str, float]
VALUE = (Output("value", "Value"),)


@indicator(
    id="rsi",
    name="Relative Strength Index",
    group=G,
    placement="pane",
    params=[length(14)],
    outputs=VALUE,
    description="Compares recent gains with recent losses on a 0-100 scale; above 70 is often called overbought, below 30 oversold.",
    scale=(0, 100),
    levels=(30, 70),
)
def _rsi(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=rsi(df["close"], n(p)))


def _stoch_raw(df: pd.DataFrame, k: int) -> pd.Series:
    ll = lowest(df["low"], k)
    return 100.0 * safe_div(df["close"] - ll, highest(df["high"], k) - ll)


@indicator(
    id="stoch",
    name="Stochastic",
    group=G,
    placement="pane",
    params=[
        length(14, key="k_length", label="%K length"),
        length(1, key="k_smoothing", label="%K smoothing"),
        length(3, key="d_smoothing", label="%D smoothing"),
    ],
    outputs=(Output("k", "%K"), Output("d", "%D")),
    description="Shows where the close sits within the recent high-low range; above 80 is stretched high, below 20 stretched low.",
    scale=(0, 100),
    levels=(20, 80),
)
def _stoch(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    k = sma(_stoch_raw(df, n(p, "k_length")), n(p, "k_smoothing"))
    return frame(df.index, k=k, d=sma(k, n(p, "d_smoothing")))


@indicator(
    id="stochrsi",
    name="Stochastic RSI",
    group=G,
    placement="pane",
    params=[
        length(14, key="rsi_length", label="RSI length"),
        length(14, key="stoch_length", label="Stochastic length"),
        length(3, key="k_smoothing", label="%K smoothing"),
        length(3, key="d_smoothing", label="%D smoothing"),
    ],
    outputs=(Output("k", "%K"), Output("d", "%D")),
    description="A stochastic applied to the RSI instead of price, so it swings faster between overbought (above 80) and oversold (below 20).",
    scale=(0, 100),
    levels=(20, 80),
)
def _stochrsi(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    r = rsi(df["close"], n(p, "rsi_length"))
    ll = lowest(r, n(p, "stoch_length"))
    raw = 100.0 * safe_div(r - ll, highest(r, n(p, "stoch_length")) - ll)
    k = sma(raw, n(p, "k_smoothing"))
    return frame(df.index, k=k, d=sma(k, n(p, "d_smoothing")))


@indicator(
    id="macd",
    name="MACD",
    group=G,
    placement="pane",
    params=[
        length(12, key="fast", label="Fast length"),
        length(26, key="slow", label="Slow length"),
        length(9, key="signal", label="Signal length"),
    ],
    outputs=(Output("macd", "MACD"), Output("signal", "Signal"), Output("hist", "Histogram", "histogram")),
    description="The gap between a fast and a slow EMA with a signal line; the MACD crossing above its signal is bullish, below bearish.",
    levels=(0,),
)
def _macd(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    line = ema(df["close"], n(p, "fast")) - ema(df["close"], n(p, "slow"))
    sig = ema(line, n(p, "signal"))
    return frame(df.index, macd=line, signal=sig, hist=line - sig)


@indicator(
    id="ppo",
    name="Price Oscillator",
    group=G,
    placement="pane",
    params=[
        length(12, key="fast", label="Fast length"),
        length(26, key="slow", label="Slow length"),
        length(9, key="signal", label="Signal length"),
    ],
    outputs=(Output("ppo", "PPO"), Output("signal", "Signal"), Output("hist", "Histogram", "histogram")),
    description="Like MACD but expressed as a percentage of the slow EMA, so values are comparable between shares of different prices.",
    levels=(0,),
)
def _ppo(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    slow = ema(df["close"], n(p, "slow"))
    line = 100.0 * safe_div(ema(df["close"], n(p, "fast")) - slow, slow)
    sig = ema(line, n(p, "signal"))
    return frame(df.index, ppo=line, signal=sig, hist=line - sig)


def _ao(df: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    mp = median_price(df)
    return sma(mp, fast) - sma(mp, slow)


@indicator(
    id="awesome",
    name="Awesome Oscillator",
    group=G,
    placement="pane",
    params=[length(5, key="fast", label="Fast length"), length(34, key="slow", label="Slow length")],
    outputs=(Output("value", "Awesome Oscillator", "histogram"),),
    description="The 5-bar minus 34-bar average of the median price; bars above zero show bullish momentum, below zero bearish.",
    levels=(0,),
)
def _awesome(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=_ao(df, n(p, "fast"), n(p, "slow")))


@indicator(
    id="accelerator",
    name="Accelerator Oscillator",
    group=G,
    placement="pane",
    params=[length(5, key="fast", label="Fast length"), length(34, key="slow", label="Slow length")],
    outputs=(Output("value", "Accelerator Oscillator", "histogram"),),
    description="Shows whether momentum itself is speeding up or slowing down (the Awesome Oscillator minus its 5-bar average).",
    levels=(0,),
)
def _accelerator(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    ao = _ao(df, n(p, "fast"), n(p, "slow"))
    return frame(df.index, value=ao - sma(ao, 5))


@indicator(
    id="cci",
    name="Commodity Channel Index",
    group=G,
    placement="pane",
    params=[length(20)],
    outputs=VALUE,
    description="Measures how far the typical price is from its average; readings beyond +100 or -100 show unusually strong moves.",
    levels=(-100, 100),
)
def _cci(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    return frame(df.index, value=safe_div(tp - sma(tp, n(p)), 0.015 * mean_abs_dev(tp, n(p))))


@indicator(
    id="cmo",
    name="Chande Momentum Oscillator",
    group=G,
    placement="pane",
    params=[length(9)],
    outputs=VALUE,
    description="Compares total up-moves with total down-moves over N bars on a -100 to 100 scale; above 50 is overbought, below -50 oversold.",
    scale=(-100, 100),
    levels=(-50, 50),
)
def _cmo(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    d = df["close"].diff()
    su = d.clip(lower=0.0).where(d.notna()).rolling(n(p), min_periods=n(p)).sum()
    sd = (-d).clip(lower=0.0).where(d.notna()).rolling(n(p), min_periods=n(p)).sum()
    return frame(df.index, value=100.0 * safe_div(su - sd, su + sd))


@indicator(
    id="roc",
    name="Rate Of Change",
    group=G,
    placement="pane",
    params=[length(9)],
    outputs=VALUE,
    description="The percentage change in price over the last N bars; above zero means price is higher than N bars ago.",
    levels=(0,),
)
def _roc(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=100.0 * (safe_div(df["close"], df["close"].shift(n(p))) - 1.0))


@indicator(
    id="momentum",
    name="Momentum",
    group=G,
    placement="pane",
    params=[length(10)],
    outputs=VALUE,
    description="Today's close minus the close N bars ago; positive values mean price is rising, negative falling.",
    levels=(0,),
)
def _momentum(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=df["close"] - df["close"].shift(n(p)))


@indicator(
    id="willr",
    name="Williams %R",
    group=G,
    placement="pane",
    params=[length(14)],
    outputs=VALUE,
    description="Shows where the close is within the recent range from -100 (at the low) to 0 (at the high); above -20 is overbought, below -80 oversold.",
    scale=(-100, 0),
    levels=(-80, -20),
)
def _willr(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    hh = highest(df["high"], n(p))
    return frame(df.index, value=100.0 * safe_div(df["close"] - hh, hh - lowest(df["low"], n(p))))


@indicator(
    id="ultimate",
    name="Ultimate Oscillator",
    group=G,
    placement="pane",
    params=[
        length(7, key="short", label="Short length"),
        length(14, key="mid", label="Middle length"),
        length(28, key="long", label="Long length"),
    ],
    outputs=VALUE,
    description="Blends buying pressure over three time frames into one 0-100 reading; above 70 is overbought, below 30 oversold.",
    scale=(0, 100),
    levels=(30, 70),
)
def _ultimate(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    prev = df["close"].shift(1)
    low_ = pd.concat([df["low"], prev], axis=1).min(axis=1).where(prev.notna())
    high_ = pd.concat([df["high"], prev], axis=1).max(axis=1).where(prev.notna())
    bp, tr = df["close"] - low_, high_ - low_

    def avg(k: int) -> pd.Series:
        return safe_div(bp.rolling(k, min_periods=k).sum(), tr.rolling(k, min_periods=k).sum())

    a, b, c = avg(n(p, "short")), avg(n(p, "mid")), avg(n(p, "long"))
    return frame(df.index, value=100.0 * (4.0 * a + 2.0 * b + c) / 7.0)


def _tsi_ratio(close: pd.Series, long_: int, short: int) -> pd.Series:
    pc = close.diff()
    return safe_div(ema(ema(pc, long_), short), ema(ema(pc.abs(), long_), short))


@indicator(
    id="tsi",
    name="True Strength Index",
    group=G,
    placement="pane",
    params=[
        length(25, key="long", label="Long length"),
        length(13, key="short", label="Short length"),
        length(13, key="signal", label="Signal length"),
    ],
    outputs=(Output("tsi", "TSI"), Output("signal", "Signal")),
    description="A double-smoothed momentum reading; crossing above zero or above its signal line is bullish, below bearish.",
    levels=(0,),
)
def _tsi(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    t = 100.0 * _tsi_ratio(df["close"], n(p, "long"), n(p, "short"))
    return frame(df.index, tsi=t, signal=ema(t, n(p, "signal")))


@indicator(
    id="kst",
    name="Know Sure Thing",
    group=G,
    placement="pane",
    params=[
        length(10, key="roc1", label="ROC 1"),
        length(15, key="roc2", label="ROC 2"),
        length(20, key="roc3", label="ROC 3"),
        length(30, key="roc4", label="ROC 4"),
        length(10, key="sma1", label="SMA 1"),
        length(10, key="sma2", label="SMA 2"),
        length(10, key="sma3", label="SMA 3"),
        length(15, key="sma4", label="SMA 4"),
        length(9, key="signal", label="Signal length"),
    ],
    outputs=(Output("kst", "KST"), Output("signal", "Signal")),
    description="Adds up four smoothed rates of change (short to long term) into one momentum line; crossing its signal line is the usual trigger.",
    levels=(0,),
)
def _kst(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    c = df["close"]
    kst = sum(
        (
            w * sma(100.0 * (safe_div(c, c.shift(n(p, f"roc{i}"))) - 1.0), n(p, f"sma{i}"))
            for i, w in ((1, 1), (2, 2), (3, 3), (4, 4))
        ),
        start=pd.Series(0.0, index=df.index),
    )
    return frame(df.index, kst=kst, signal=sma(kst, n(p, "signal")))


@indicator(
    id="dpo",
    name="Detrended Price Oscillator",
    group=G,
    placement="pane",
    params=[length(21)],
    outputs=VALUE,
    description="Removes the trend to show cycles: today's close minus a moving average from about half a period ago.",
    levels=(0,),
)
def _dpo(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    """Non-centred, causal version: close - SMA(close, n) shifted by n/2 + 1 bars (the classic centred version
    would need future bars)."""
    return frame(df.index, value=df["close"] - sma(df["close"], n(p)).shift(n(p) // 2 + 1))


@indicator(
    id="coppock",
    name="Coppock Curve",
    group=G,
    placement="pane",
    params=[
        length(10, key="wma", label="WMA length"),
        length(14, key="long", label="Long ROC"),
        length(11, key="short", label="Short ROC"),
    ],
    outputs=VALUE,
    description="A weighted average of two rates of change, designed to spot long-term market bottoms when it turns up from below zero.",
    levels=(0,),
)
def _coppock(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    c = df["close"]
    roc = 100.0 * (safe_div(c, c.shift(n(p, "long"))) - 1.0) + 100.0 * (
        safe_div(c, c.shift(n(p, "short"))) - 1.0
    )
    return frame(df.index, value=wma(roc, n(p, "wma")))


@indicator(
    id="fisher",
    name="Fisher Transform",
    group=G,
    placement="pane",
    params=[length(9)],
    outputs=(Output("fisher", "Fisher"), Output("trigger", "Trigger")),
    description="Reshapes prices so turning points show as sharp peaks; the Fisher line crossing its trigger line signals a reversal.",
    levels=(0,),
)
def _fisher(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    hl2 = median_price(df)
    hi, lo = highest(hl2, n(p)).to_numpy(dtype="float64"), lowest(hl2, n(p)).to_numpy(dtype="float64")
    x = hl2.to_numpy(dtype="float64")
    fish = np.full(len(x), np.nan)
    val = fp = 0.0
    for i in np.flatnonzero(~np.isnan(hi)):
        val = 0.66 * ((x[i] - lo[i]) / max(hi[i] - lo[i], 0.001) - 0.5) + 0.67 * val
        val = 0.999 if val > 0.99 else (-0.999 if val < -0.99 else val)
        fp = 0.5 * np.log((1 + val) / (1 - val)) + 0.5 * fp
        fish[i] = fp
    return frame(df.index, fisher=fish, trigger=pd.Series(fish, index=df.index).shift(1))


def _swma(s: pd.Series) -> pd.Series:
    """Symmetrically weighted 4-bar average (1, 2, 2, 1) / 6."""
    return (s + 2.0 * s.shift(1) + 2.0 * s.shift(2) + s.shift(3)) / 6.0


@indicator(
    id="rvi",
    name="Relative Vigor Index",
    group=G,
    placement="pane",
    params=[length(10)],
    outputs=(Output("rvi", "RVI"), Output("signal", "Signal")),
    description="Compares where bars close relative to where they open, on the idea that closes are higher than opens in uptrends.",
    levels=(0,),
)
def _rvi(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    num = sma(_swma(df["close"] - df["open"]), n(p))
    den = sma(_swma(df["high"] - df["low"]), n(p))
    r = safe_div(num, den)
    return frame(df.index, rvi=r, signal=_swma(r))


@indicator(
    id="relative_vol",
    name="Relative Volatility Index",
    group=G,
    placement="pane",
    params=[
        length(10, key="stdev_length", label="Stdev length"),
        length(14, key="ema_length", label="EMA length"),
    ],
    outputs=VALUE,
    description="Like RSI but built from the standard deviation of price instead of price changes; high values mean volatility is rising with price.",
    scale=(0, 100),
    levels=(20, 80),
)
def _relative_vol(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    sd = stdev(df["close"], n(p, "stdev_length"))
    d = df["close"].diff()
    up = ema(sd.where(d > 0, 0.0).where(d.notna() & sd.notna()), n(p, "ema_length"))
    dn = ema(sd.where(d <= 0, 0.0).where(d.notna() & sd.notna()), n(p, "ema_length"))
    return frame(df.index, value=100.0 * safe_div(up, up + dn))


@indicator(
    id="smi_ergodic",
    name="SMI Ergodic Indicator",
    group=G,
    placement="pane",
    params=[
        length(5, key="short", label="Short length"),
        length(20, key="long", label="Long length"),
        length(5, key="signal", label="Signal length"),
    ],
    outputs=(Output("smi", "SMI"), Output("signal", "Signal")),
    description="A smoothed momentum ratio between -1 and 1 (the true strength index) with a signal line; crossings of the signal show momentum shifts.",
    levels=(0,),
)
def _smi_ergodic(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    smi = _tsi_ratio(df["close"], n(p, "long"), n(p, "short"))
    return frame(df.index, smi=smi, signal=ema(smi, n(p, "signal")))


@indicator(
    id="connors_rsi",
    name="Connors RSI",
    group=G,
    placement="pane",
    params=[
        length(3, key="rsi_length", label="RSI length"),
        length(2, key="streak_length", label="Streak RSI length"),
        length(100, key="rank_length", label="Rank length"),
    ],
    outputs=VALUE,
    description="Averages a short RSI, the RSI of the up/down streak length and the percentile rank of today's change; extremes flag short-term reversals.",
    scale=(0, 100),
    levels=(10, 90),
)
def _connors(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    close = df["close"]
    sign = np.sign(close.diff().to_numpy(dtype="float64"))
    sign[0] = 0.0
    pos = np.arange(len(sign))
    run_start = np.maximum.accumulate(np.where(np.r_[True, sign[1:] != sign[:-1]], pos, 0))
    streak = pd.Series(sign * (pos - run_start + 1), index=df.index)
    roc1 = close.pct_change() * 100.0
    value = (
        rsi(close, n(p, "rsi_length"))
        + rsi(streak, n(p, "streak_length"))
        + percent_rank(roc1, n(p, "rank_length"))
    ) / 3.0
    return frame(df.index, value=value)


@indicator(
    id="bop",
    name="Balance of Power",
    group=G,
    placement="pane",
    outputs=VALUE,
    description="Measures who won each bar, buyers or sellers, as (close - open) / (high - low) between -1 and 1; positive means buyers.",
    scale=(-1, 1),
    levels=(0,),
)
def _bop(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=safe_div(df["close"] - df["open"], df["high"] - df["low"]))
