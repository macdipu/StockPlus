"""Deterministic synthetic OHLCV series shared by the indicator tests."""

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest


def make_bars(index: pd.DatetimeIndex, seed: int = 7) -> pd.DataFrame:
    """A random walk with realistic bars: high >= max(open, close), low <= min(open, close), volume > 0."""
    rs = np.random.RandomState(seed)
    n = len(index)
    close = 100.0 * np.exp(np.cumsum(rs.normal(0.0002, 0.015, n)))
    open_ = np.r_[close[0], close[:-1]] * np.exp(rs.normal(0.0, 0.004, n))
    high = np.maximum(open_, close) * (1.0 + np.abs(rs.normal(0.0, 0.006, n)))
    low = np.minimum(open_, close) * (1.0 - np.abs(rs.normal(0.0, 0.006, n)))
    volume = rs.randint(1_000, 100_000, n).astype("float64")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=index
    )


@pytest.fixture(scope="session")
def daily() -> pd.DataFrame:
    return make_bars(pd.bdate_range("2023-01-02", periods=400))


@pytest.fixture(scope="session")
def intraday() -> pd.DataFrame:
    days = ["2024-01-02", "2024-01-03", "2024-01-04"]
    parts = [pd.date_range(f"{d} 10:00", periods=134, freq="2min") for d in days]
    return make_bars(pd.DatetimeIndex(parts[0].append(parts[1]).append(parts[2])), seed=11)


@pytest.fixture(params=["daily", "intraday"])
def bars(request: pytest.FixtureRequest) -> pd.DataFrame:
    frame: pd.DataFrame = request.getfixturevalue(request.param)
    return frame


def tiny(**cols: Sequence[float]) -> pd.DataFrame:
    """A small hand-written frame; unspecified columns default to the close (or 1.0 volume)."""
    n = len(next(iter(cols.values())))
    base = cols.get("close", cols.get("high", next(iter(cols.values()))))
    data = {k: cols.get(k, base) for k in ("open", "high", "low", "close")}
    data["volume"] = cols.get("volume", [1.0] * n)
    return pd.DataFrame(data, index=pd.bdate_range("2024-01-01", periods=n), dtype="float64")
