# ruff: noqa: E501 — indicator descriptions are one readable sentence each
"""Volatility indicators. All in their own pane."""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from dse.indicators._params import VOLATILITY as G
from dse.indicators._params import length, n, number
from dse.indicators.base import Output, indicator
from dse.indicators.maths import atr, frame, highest, safe_div, sma, stdev

Params = Mapping[str, float]
VALUE = (Output("value", "Value"),)


@indicator(
    id="atr",
    name="Average True Range",
    group=G,
    placement="pane",
    params=[length(14)],
    outputs=VALUE,
    description="The average size of a bar's full price range, including gaps; higher means a more volatile share, useful for sizing stops.",
)
def _atr(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=atr(df, n(p)))


def _bands(df: pd.DataFrame, p: Params) -> tuple[pd.Series, pd.Series, pd.Series]:
    basis = sma(df["close"], n(p))
    dev = p["mult"] * stdev(df["close"], n(p))
    return basis, basis + dev, basis - dev


_BB_PARAMS = [length(20), number(2.0, "mult", "Standard deviations", 0.1, 10.0)]


@indicator(
    id="bb_width",
    name="Bollinger Bands Width",
    group=G,
    placement="pane",
    params=_BB_PARAMS,
    outputs=VALUE,
    description="How wide the Bollinger Bands are relative to their average; very low values (a squeeze) often come before big moves.",
)
def _bb_width(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    basis, upper, lower = _bands(df, p)
    return frame(df.index, value=safe_div(upper - lower, basis))


@indicator(
    id="bb_percent_b",
    name="Bollinger Bands %B",
    group=G,
    placement="pane",
    params=_BB_PARAMS,
    outputs=VALUE,
    description="Where price sits inside the Bollinger Bands: 1 is at the upper band, 0 at the lower band, beyond that is outside them.",
    levels=(0, 0.5, 1),
)
def _bb_percent_b(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    _, upper, lower = _bands(df, p)
    return frame(df.index, value=safe_div(df["close"] - lower, upper - lower))


def _log_returns(df: pd.DataFrame) -> pd.Series:
    return pd.Series(np.log(df["close"] / df["close"].shift(1)), index=df.index)


@indicator(
    id="hist_vol",
    name="Historical Volatility",
    group=G,
    placement="pane",
    params=[length(10, lo=2), length(252, key="periods", label="Bars per year", lo=1, hi=100000)],
    outputs=VALUE,
    description="The annualised standard deviation of daily price changes, in percent; higher means wilder swings.",
)
def _hist_vol(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=100.0 * stdev(_log_returns(df), n(p)) * np.sqrt(p["periods"]))


@indicator(
    id="close_vol",
    name="Volatility Close-to-Close",
    group=G,
    placement="pane",
    params=[length(20, lo=2), length(252, key="periods", label="Bars per year", lo=1, hi=100000)],
    outputs=VALUE,
    description="The annualised sample standard deviation of close-to-close returns, in percent; a standard measure of how much a share swings.",
)
def _close_vol(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    sd = _log_returns(df).rolling(n(p), min_periods=n(p)).std(ddof=1)
    return frame(df.index, value=100.0 * sd * np.sqrt(p["periods"]))


@indicator(
    id="stdev_ind",
    name="Standard Deviation",
    group=G,
    placement="pane",
    params=[length(20, lo=2)],
    outputs=VALUE,
    description="How far closing prices typically stray from their N-bar average, in price units; larger means more volatile.",
)
def _stdev(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=stdev(df["close"], n(p)))


@indicator(
    id="ulcer",
    name="Ulcer Index",
    group=G,
    placement="pane",
    params=[length(14)],
    outputs=VALUE,
    description="Measures downside risk: how deep and how long price has been below its recent peak; higher means more painful drawdowns.",
)
def _ulcer(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    dd = 100.0 * safe_div(df["close"] - highest(df["close"], n(p)), highest(df["close"], n(p)))
    return frame(df.index, value=np.sqrt(sma(dd**2, n(p))))
