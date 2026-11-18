"""Dependency providers for the company feature."""

from dataclasses import dataclass

from fastapi import Request

from dse.features.company.application.ports import AnalysisLookup, CompanySources, PriceLookup
from dse.features.company.application.use_cases import GetCompanyDossier, GetWatchlistAlerts
from dse.shared_kernel.clock import Clock


@dataclass(frozen=True)
class CompanyContainer:
    sources: CompanySources
    prices: PriceLookup
    clock: Clock
    analysis: AnalysisLookup
    dossier: GetCompanyDossier

    @classmethod
    def build(
        cls,
        sources: CompanySources,
        prices: PriceLookup,
        analysis: AnalysisLookup,
        clock: Clock,
    ) -> "CompanyContainer":
        # one GetCompanyDossier per process, so its single-flight map is shared by every request
        return cls(sources, prices, clock, analysis, GetCompanyDossier(sources, prices, clock))

    @property
    def alerts(self) -> GetWatchlistAlerts:
        return GetWatchlistAlerts(self.analysis, self.dossier, self.clock)


def container(request: Request) -> CompanyContainer:
    c: CompanyContainer = request.app.state.company
    return c
