"""The analysis use cases depend on this port; infrastructure fulfils it from other features' facades."""

from typing import Protocol

from dse.features.analysis.application.inputs import AnalysisInput


class AnalysisInputs(Protocol):
    async def load(self, symbol: str) -> AnalysisInput:
        """Raises NotFoundError for an unknown symbol."""
        ...
