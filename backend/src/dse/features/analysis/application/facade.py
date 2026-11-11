"""The ONLY entry point other features may use (import-linter enforces this)."""

from dse.features.analysis.application.dto import AnalysisDto
from dse.features.analysis.application.inputs import QuoteInput, UniverseInput, UniverseRows
from dse.features.analysis.application.universe import build_universe_rows
from dse.features.analysis.application.use_cases import AnalyzeInstrument
from dse.features.analysis.domain.frames import Bar


class AnalysisFacade:
    def __init__(self, analyze: AnalyzeInstrument) -> None:
        self._analyze = analyze

    async def analyze(self, symbol: str) -> AnalysisDto:
        return await self._analyze(symbol)


# Bulk row building for the scanner. Re-exported here so other features import the facade only.
__all__ = [
    "AnalysisFacade",
    "Bar",
    "QuoteInput",
    "UniverseInput",
    "UniverseRows",
    "build_universe_rows",
]
