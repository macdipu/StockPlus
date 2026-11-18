"""Every registered indicator: output contract, finiteness, warm-up and causality."""

import numpy as np
import pandas as pd
import pytest

from dse.indicators.base import REGISTRY, Indicator

ALL = list(REGISTRY.values())
IDS = list(REGISTRY)

# Outputs that are legitimately NaN on some bars (alternating bands, a line that stops at the last pivot).
SPARSE = {"supertrend", "zigzag"}
# Indicators defined from the very first bar (per-bar transforms, running totals): no warm-up rows.
NO_WARMUP = {
    "volume",
    "ad",
    "vwap",
    "bop",
    "typical_price",
    "median_price",
    "average_price",
    "weighted_close",
}


def _run(ind: Indicator, df: pd.DataFrame) -> pd.DataFrame:
    return ind.run(df)


@pytest.mark.parametrize("ind", ALL, ids=IDS)
def test_output_contract(ind: Indicator, bars: pd.DataFrame) -> None:
    res = _run(ind, bars)
    assert list(res.columns) == [o.key for o in ind.outputs]
    assert res.index.equals(bars.index)
    assert all(dt == np.float64 for dt in res.dtypes)
    assert not np.isinf(res.to_numpy()).any()
    for col in res.columns:
        s = res[col]
        assert s.notna().any(), f"{ind.id}.{col} never produces a value"
        if ind.id not in SPARSE:
            assert np.isfinite(s.iloc[-1]), f"{ind.id}.{col} is NaN on the last bar"
        else:
            assert s.notna().sum() > 5


@pytest.mark.parametrize("ind", ALL, ids=IDS)
def test_warmup_is_nan_not_zero(ind: Indicator, daily: pd.DataFrame) -> None:
    res = _run(ind, daily)
    if ind.id in NO_WARMUP:
        return
    # the very first bar cannot be a finished value for anything that looks back (a 0 would be a lie)
    first = res.iloc[0]
    assert first.isna().all(), f"{ind.id} has finite values on bar 0: {first.to_dict()}"
    # a longer lookback pushes the first value further out
    if any(p.key == "length" for p in ind.params) and ind.id not in {"volume", "dpo"}:
        res30 = ind.run(daily, {"length": 30})
        assert res30.iloc[:29].isna().all().all(), f"{ind.id} is not NaN during its 30-bar warm-up"


@pytest.mark.parametrize("ind", [i for i in ALL if not i.repaints], ids=[i.id for i in ALL if not i.repaints])
@pytest.mark.parametrize("k", [150, 250])
def test_causality(ind: Indicator, k: int, bars: pd.DataFrame) -> None:
    full = _run(ind, bars)
    part = _run(ind, bars.iloc[:k])
    for col in full.columns:
        np.testing.assert_allclose(
            part[col].to_numpy(),
            full[col].iloc[:k].to_numpy(),
            rtol=0,
            atol=1e-9,
            equal_nan=True,
            err_msg=f"{ind.id}.{col} is not causal at k={k}",
        )


def test_only_zigzag_repaints() -> None:
    assert {i.id for i in ALL if i.repaints} == {"zigzag"}


def test_zigzag_repaints_for_real(daily: pd.DataFrame) -> None:
    zz = REGISTRY["zigzag"]
    full = zz.run(daily)["value"].to_numpy()
    part = zz.run(daily.iloc[:250])["value"].to_numpy()
    assert not np.allclose(full[:250], part, equal_nan=True)


def test_inputs_are_not_mutated(daily: pd.DataFrame) -> None:
    before = daily.copy()
    for ind in ALL:
        _run(ind, daily)
    pd.testing.assert_frame_equal(daily, before)
