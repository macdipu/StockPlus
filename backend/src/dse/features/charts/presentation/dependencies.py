"""Dependency providers for the charts feature."""

from dataclasses import dataclass

from fastapi import Request

from dse.features.charts.application.use_cases import GetChart, ListIndicators


@dataclass(frozen=True)
class ChartsContainer:
    """One per process, so the single-flight map and the concurrency cap are shared by every request."""

    chart: GetChart
    indicators: ListIndicators


def container(request: Request) -> ChartsContainer:
    c: ChartsContainer = request.app.state.charts
    return c
