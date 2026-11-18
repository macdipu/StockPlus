"""Dependency providers for the company feature."""

from dataclasses import dataclass

from fastapi import Request

from dse.features.company.application.ports import AnalysisLookup, BarSource, CompanySources, PriceLookup
from dse.features.company.application.use_cases import GetBars, GetCompanyDossier, GetWatchlistAlerts
from dse.shared_kernel.clock import Clock


@dataclass(frozen=True)
class CompanyContainer:
    sources: CompanySources
    bar_source: BarSource
    prices: PriceLookup
    clock: Clock
    analysis: AnalysisLookup
    dossier: GetCompanyDossier

    @classmethod
    def build(
        cls,
        sources: CompanySources,
        bar_source: BarSource,
        prices: PriceLookup,
        analysis: AnalysisLookup,
        clock: Clock,
    ) -> "CompanyContainer":
        # one GetCompanyDossier per process, so its single-flight map is shared by every request
        return cls(sources, bar_source, prices, clock, analysis, GetCompanyDossier(sources, prices, clock))

    @property
    def alerts(self) -> GetWatchlistAlerts:
        return GetWatchlistAlerts(self.analysis, self.dossier, self.clock)

    @property
    def bars(self) -> GetBars:
        return GetBars(self.bar_source)


def container(request: Request) -> CompanyContainer:
    c: CompanyContainer = request.app.state.company
    return c
