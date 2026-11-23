"""Dependency providers for the analysis feature."""

from dataclasses import dataclass

from fastapi import Request

from dse.features.analysis.application.facade import AnalysisFacade
from dse.features.analysis.application.ports import AnalysisInputs, HistorySource
from dse.features.analysis.application.use_cases import (
    AnalyzeInstrument,
    CalculateReturn,
    ComputeCorrelation,
    GetBrief,
    GetChanges,
    GetChartPatterns,
    GetIntraday,
    GetTechnicals,
    GetVpa,
    RankSymbols,
)


@dataclass(frozen=True)
class AnalysisContainer:
    inputs: AnalysisInputs
    history: HistorySource

    @property
    def analyze(self) -> AnalyzeInstrument:
        return AnalyzeInstrument(self.inputs)

    @property
    def brief(self) -> GetBrief:
        return GetBrief(self.analyze)

    @property
    def technicals(self) -> GetTechnicals:
        return GetTechnicals(self.analyze)

    @property
    def vpa(self) -> GetVpa:
        return GetVpa(self.analyze)

    @property
    def rank(self) -> RankSymbols:
        return RankSymbols(self.analyze)

    @property
    def calculate_return(self) -> CalculateReturn:
        return CalculateReturn(self.history)

    @property
    def correlation(self) -> ComputeCorrelation:
        return ComputeCorrelation(self.history)

    @property
    def changes(self) -> GetChanges:
        return GetChanges(self.inputs)

    @property
    def chart_patterns(self) -> GetChartPatterns:
        return GetChartPatterns(self.history)

    @property
    def intraday(self) -> GetIntraday:
        return GetIntraday(self.history)

    @property
    def facade(self) -> AnalysisFacade:
        return AnalysisFacade(self.analyze)


def container(request: Request) -> AnalysisContainer:
    c: AnalysisContainer = request.app.state.analysis
    return c
