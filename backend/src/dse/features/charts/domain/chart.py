"""Run a list of indicators over candles. Pure; one failing indicator never takes the chart down."""

import logging
from dataclasses import dataclass

import pandas as pd

from dse.features.charts.domain.candles import Candles
from dse.features.charts.domain.spec import ResolvedSpec

log = logging.getLogger("dse.charts")


@dataclass(frozen=True, slots=True)
class IndicatorResult:
    spec: ResolvedSpec
    values: pd.DataFrame


def run_indicators(candles: Candles, specs: list[ResolvedSpec]) -> tuple[list[IndicatorResult], list[str]]:
    """(results, warnings). An indicator that raises is skipped and reported."""
    frame = candles.frame()
    results: list[IndicatorResult] = []
    warnings: list[str] = []
    for spec in specs:
        try:
            results.append(IndicatorResult(spec, spec.indicator.run(frame, spec.params)))
        except Exception as e:
            log.warning("indicator failed", extra={"indicator": spec.key, "error": str(e)})
            warnings.append(f"{spec.key} could not be computed on this data")
    return results, warnings
