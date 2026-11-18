"""Small helpers shared by the indicator modules: parameter shortcuts and group names."""

from collections.abc import Mapping

from dse.indicators.base import Param

MOVING_AVERAGES = "Moving averages"
BANDS = "Bands and channels"
TREND = "Trend"
MOMENTUM = "Momentum"
VOLATILITY = "Volatility"
VOLUME = "Volume"
PRICE = "Price"
GROUPS = (MOVING_AVERAGES, BANDS, TREND, MOMENTUM, VOLATILITY, VOLUME, PRICE)


def length(default: int, key: str = "length", label: str = "Length", lo: int = 1, hi: int = 500) -> Param:
    return Param(key, label, default, lo, hi)


def number(default: float, key: str, label: str, lo: float, hi: float) -> Param:
    return Param(key, label, default, lo, hi, integer=False)


def n(p: Mapping[str, float], key: str = "length") -> int:
    """A resolved integer parameter."""
    return int(p[key])
