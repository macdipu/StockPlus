"""The ONLY entry point other features may use (import-linter enforces this)."""

from dse.features.analysis.application.dto import AnalysisDto
from dse.features.analysis.application.use_cases import AnalyzeInstrument


class AnalysisFacade:
    def __init__(self, analyze: AnalyzeInstrument) -> None:
        self._analyze = analyze

    async def analyze(self, symbol: str) -> AnalysisDto:
        return await self._analyze(symbol)
