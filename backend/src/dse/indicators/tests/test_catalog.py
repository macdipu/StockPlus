"""Catalog-level rules: ids, descriptions, groups, metadata consistency and parameter resolution."""

import pandas as pd
import pytest

import dse.indicators as engine
from dse.indicators._params import GROUPS
from dse.indicators.base import REGISTRY
from dse.shared_kernel.errors import ValidationFailedError

EXPECTED_IDS = """
sma ema wma vwma hma dema tema smma lsma alma mcginley kama ma_cross ema_cross guppy ma_ribbon vwap
bbands keltner donchian price_channel envelopes mac chande_kroll ichimoku pivot_points week52 fib_retracement
supertrend psar adx dmi aroon aroon_osc vortex chop zigzag williams_alligator mass_index elder_ray trix
rsi stoch stochrsi macd ppo awesome accelerator cci cmo roc momentum willr ultimate tsi kst dpo coppock fisher
rvi relative_vol smi_ergodic connors_rsi bop
atr bb_width bb_percent_b hist_vol close_vol stdev_ind ulcer
volume obv ad cmf chaikin_osc mfi efi eom pvt net_volume volume_osc klinger asi
typical_price median_price average_price weighted_close
""".split()  # noqa: SIM905 — a compact, readable id list


def test_catalog_is_large_and_complete() -> None:
    assert len(REGISTRY) >= 80
    assert set(EXPECTED_IDS) <= set(REGISTRY)
    assert len(set(EXPECTED_IDS)) == len(EXPECTED_IDS)
    assert engine.REGISTRY is REGISTRY


def test_ids_and_names_are_unique() -> None:
    assert all(k == ind.id for k, ind in REGISTRY.items())
    names = [ind.name for ind in REGISTRY.values()]
    assert len(set(names)) == len(names)


@pytest.mark.parametrize("ind", REGISTRY.values(), ids=list(REGISTRY))
def test_metadata(ind: engine.Indicator) -> None:
    assert len(ind.description.strip()) >= 25
    assert ind.group in GROUPS
    assert ind.placement in ("overlay", "pane")
    keys = [o.key for o in ind.outputs]
    assert keys
    assert len(set(keys)) == len(keys)
    assert all(o.kind in ("line", "histogram", "area", "dots") for o in ind.outputs)
    pkeys = [p.key for p in ind.params]
    assert len(set(pkeys)) == len(pkeys)
    for p in ind.params:
        assert p.min <= p.default <= p.max
    if ind.placement == "overlay":
        assert ind.scale is None
        assert ind.levels == ()
    if ind.scale is not None:
        lo, hi = ind.scale
        assert lo < hi
        assert all(lo <= lv <= hi for lv in ind.levels)


def test_groups_follow_modules() -> None:
    by_group: dict[str, int] = {}
    for ind in REGISTRY.values():
        by_group[ind.group] = by_group.get(ind.group, 0) + 1
    assert set(by_group) == set(GROUPS)


def test_resolve_fills_defaults_clamps_and_casts() -> None:
    rsi = REGISTRY["rsi"]
    assert rsi.resolve() == {"length": 14}
    assert rsi.resolve({"length": 0}) == {"length": 1}
    assert rsi.resolve({"length": 99999}) == {"length": 500}
    resolved = rsi.resolve({"length": 14.6})
    assert resolved == {"length": 15}
    assert isinstance(resolved["length"], int)

    bb = REGISTRY["bbands"]
    out = bb.resolve({"mult": 2.5})
    assert out == {"length": 20, "mult": 2.5}
    assert isinstance(out["mult"], float)
    assert bb.resolve({"mult": 1000.0})["mult"] == 10.0
    assert bb.resolve({"mult": -3.0})["mult"] == 0.1


def test_resolve_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationFailedError, match="bogus"):
        REGISTRY["rsi"].resolve({"bogus": 1})
    with pytest.raises(ValidationFailedError):
        REGISTRY["typical_price"].resolve({"x": 1})


def test_run_applies_resolution(daily: pd.DataFrame) -> None:
    short = REGISTRY["sma"].run(daily, {"length": 3})
    assert short["value"].notna().sum() == len(daily) - 2
    clamped = REGISTRY["sma"].run(daily, {"length": 0})  # clamped to 1: equals close
    assert clamped["value"].equals(daily["close"].astype("float64").rename("value"))
