"""Dependency providers for the analysis feature."""

from dataclasses import dataclass

from fastapi import Request

from dse.features.analysis.application.facade import AnalysisFacade
from dse.features.analysis.application.ports import AnalysisInputs
from dse.features.analysis.application.use_cases import (
    AnalyzeInstrument,
    GetBrief,
    GetTechnicals,
    GetVpa,
    RankSymbols,
)


@dataclass(frozen=True)
class AnalysisContainer:
    inputs: AnalysisInputs

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
    def facade(self) -> AnalysisFacade:
        return AnalysisFacade(self.analyze)


def container(request: Request) -> AnalysisContainer:
    c: AnalysisContainer = request.app.state.analysis
    return c
