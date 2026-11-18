"""Price transforms. Overlay on the price chart."""

from collections.abc import Mapping

import pandas as pd

from dse.indicators._params import PRICE as G
from dse.indicators.base import Output, indicator
from dse.indicators.maths import frame, median_price, typical_price

Params = Mapping[str, float]
VALUE = (Output("value", "Value"),)


@indicator(
    id="typical_price",
    name="Typical Price",
    group=G,
    placement="overlay",
    outputs=VALUE,
    description="The average of each bar's high, low and close; a single representative price for the bar.",
)
def _typical(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=typical_price(df))


@indicator(
    id="median_price",
    name="Median Price",
    group=G,
    placement="overlay",
    outputs=VALUE,
    description="The midpoint of each bar's high and low; ignores where the bar opened and closed.",
)
def _median(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=median_price(df))


@indicator(
    id="average_price",
    name="Average Price",
    group=G,
    placement="overlay",
    outputs=VALUE,
    description="The average of open, high, low and close, a smooth line through the middle of each candle.",
)
def _average(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=(df["open"] + df["high"] + df["low"] + df["close"]) / 4.0)


@indicator(
    id="weighted_close",
    name="Weighted Close",
    group=G,
    placement="overlay",
    outputs=VALUE,
    description="The average of high, low and close (counted twice), so the close carries the most weight.",
)
def _weighted(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    return frame(df.index, value=(df["high"] + df["low"] + 2.0 * df["close"]) / 4.0)
