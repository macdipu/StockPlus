"""Indicator definitions and the registry. Pure: pandas and numpy only, no I/O.

An indicator is a function `(bars, params) -> DataFrame`:
  bars    DataFrame with float columns open, high, low, close, volume and an ascending DatetimeIndex
  params  dict of resolved parameters (defaults filled in, clamped to each Param's range, integers cast)
  result  DataFrame with exactly one column per declared Output, the same index as `bars`, float dtype, NaN
          while the indicator is still warming up. It must be CAUSAL: row t depends only on rows 0..t (unless
          the indicator is declared `repaints=True`, e.g. ZigZag, whose past values can change as new bars
          arrive).

`placement` says where a chart draws it: "overlay" on the price pane (same units as price) or "pane" in its
own sub-chart. `kind` per output is a drawing hint for the chart: line, histogram, area (filled to zero) or
dots.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from dse.shared_kernel.errors import ValidationFailedError

Placement = Literal["overlay", "pane"]
Kind = Literal["line", "histogram", "area", "dots"]
Compute = Callable[[pd.DataFrame, Mapping[str, float]], pd.DataFrame]


@dataclass(frozen=True, slots=True)
class Param:
    key: str
    label: str
    default: float
    min: float = 1
    max: float = 500
    integer: bool = True


@dataclass(frozen=True, slots=True)
class Output:
    key: str
    label: str
    kind: Kind = "line"


@dataclass(frozen=True, slots=True)
class Indicator:
    id: str
    name: str
    group: str  # Moving averages | Bands and channels | Trend | Momentum | Volatility | Volume | Price
    placement: Placement
    params: tuple[Param, ...]
    outputs: tuple[Output, ...]
    description: str
    compute: Compute
    scale: tuple[float, float] | None = None  # fixed range of a pane indicator, e.g. RSI (0, 100)
    levels: tuple[float, ...] = ()  # reference lines in a pane, e.g. RSI 30 and 70
    repaints: bool = False  # past values may change as new bars arrive

    def resolve(self, given: Mapping[str, float] | None = None) -> dict[str, float]:
        """Defaults filled in, each value clamped to its range, integers cast. Unknown keys are an error."""
        given = dict(given or {})
        known = {p.key for p in self.params}
        unknown = sorted(set(given) - known)
        if unknown:
            raise ValidationFailedError(
                f"{self.id}: unknown parameter(s) {', '.join(unknown)}; valid: {sorted(known)}"
            )
        out: dict[str, float] = {}
        for p in self.params:
            v = float(given.get(p.key, p.default))
            v = min(max(v, p.min), p.max)
            out[p.key] = round(v) if p.integer else v
        return out

    def run(self, bars: pd.DataFrame, given: Mapping[str, float] | None = None) -> pd.DataFrame:
        params = self.resolve(given)
        res = self.compute(bars, params)
        want = [o.key for o in self.outputs]
        if list(res.columns) != want:
            raise ValueError(f"{self.id} returned columns {list(res.columns)}, declared {want}")
        return res.reindex(bars.index).astype("float64")


REGISTRY: dict[str, Indicator] = {}


def indicator(
    *,
    id: str,  # noqa: A002 — the public name of the field
    name: str,
    group: str,
    placement: Placement,
    outputs: Sequence[Output],
    description: str,
    params: Sequence[Param] = (),
    scale: tuple[float, float] | None = None,
    levels: Sequence[float] = (),
    repaints: bool = False,
) -> Callable[[Compute], Compute]:
    """Register a compute function as an indicator."""

    def wrap(fn: Compute) -> Compute:
        if id in REGISTRY:
            raise ValueError(f"duplicate indicator id {id!r}")
        REGISTRY[id] = Indicator(
            id=id,
            name=name,
            group=group,
            placement=placement,
            params=tuple(params),
            outputs=tuple(outputs),
            description=description,
            compute=fn,
            scale=scale,
            levels=tuple(levels),
            repaints=repaints,
        )
        return fn

    return wrap


@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    """One requested indicator: its id and any parameter overrides."""

    id: str
    params: tuple[tuple[str, float], ...] = field(default=())
