"""The indicator catalog. Importing this package registers every indicator module."""

from dse.indicators import (  # noqa: F401 — imported for registration
    bands,
    momentum,
    moving_averages,
    price,
    trend,
    volatility,
    volume,
)
from dse.indicators.base import REGISTRY, Indicator, IndicatorSpec, Output, Param

__all__ = ["REGISTRY", "Indicator", "IndicatorSpec", "Output", "Param"]
