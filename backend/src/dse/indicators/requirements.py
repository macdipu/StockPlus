"""Which price columns an indicator reads, found by trying it: change one column, see if any output moves.

Tells a chart which indicators it can compute for a series with only closing values (a stock index has no
open, high, low or volume), without anyone maintaining a list by hand.
"""

from functools import cache

import numpy as np
import pandas as pd

from dse.indicators.base import REGISTRY, Indicator

COLUMNS = ("open", "high", "low", "volume")
# Each column is changed by a different amount on every bar. A single constant factor would go unnoticed by
# indicators that are ratios (VWAP, MFI), which do not change when volume is scaled uniformly.
_AMPLITUDE = {"open": 0.01, "high": 0.04, "low": -0.04, "volume": 0.8}


def _sample(n: int = 320) -> pd.DataFrame:
    rng = np.random.RandomState(11)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    open_ = close + rng.normal(0, 0.4, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.8, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.8, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": rng.uniform(1e3, 5e3, n)},
        index=idx,
    )


@cache
def required_columns(indicator_id: str) -> tuple[str, ...]:
    """Subset of ("open", "high", "low", "volume") whose values change what the indicator outputs."""
    ind: Indicator = REGISTRY[indicator_id]
    base = _sample()
    ref = ind.run(base)
    used = []
    for col in COLUMNS:
        changed = base.copy()
        wave = 0.5 + 0.5 * np.sin(np.arange(len(base)) * 0.9 + len(col))
        changed[col] = changed[col] * (1 + _AMPLITUDE[col] * wave)
        out = ind.run(changed)
        both = np.isfinite(ref.to_numpy()) & np.isfinite(out.to_numpy())
        moved = both.any() and not np.allclose(
            ref.to_numpy()[both], out.to_numpy()[both], rtol=1e-9, atol=1e-9
        )
        if moved or np.isfinite(ref.to_numpy()).sum() != np.isfinite(out.to_numpy()).sum():
            used.append(col)
    return tuple(used)
