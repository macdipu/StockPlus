import json
from pathlib import Path
from typing import Any

import pytest

from dse.features.analysis.application.inputs import AnalysisInput
from dse.features.analysis.domain.frames import Bar, LiveBar
from dse.shared_kernel.errors import NotFoundError

FIXTURES = Path(__file__).parent / "fixtures"
MD_FIXTURES = Path(__file__).parents[2] / "market_data" / "tests" / "fixtures"  # data files only, no imports


@pytest.fixture(scope="session")
def golden() -> dict[str, Any]:
    return dict(json.loads((FIXTURES / "legacy_golden_analysis_ORIONINFU.json").read_text()))


@pytest.fixture(scope="session")
def orion_bars() -> tuple[Bar, ...]:
    from datetime import date

    raw = json.loads((MD_FIXTURES / "legacy_golden_ORIONINFU.json").read_text())["bars"]
    return tuple(
        Bar(date.fromisoformat(b["day"]), b["open"], b["high"], b["low"], b["close"], float(b["volume"]))
        for b in raw
    )


@pytest.fixture(scope="session")
def orion_input(golden: dict[str, Any], orion_bars: tuple[Bar, ...]) -> AnalysisInput:
    f = golden["fundamentals_in"]
    return AnalysisInput(
        symbol="ORIONINFU",
        name="Orion Infusion Ltd.",
        category=f["category"],
        fundamentals=f,
        bars=orion_bars,
        live=None,
        market_open=False,
        as_of="2025-10-13",
    )


@pytest.fixture(scope="session")
def live_bar(golden: dict[str, Any]) -> LiveBar:
    from datetime import date

    q = golden["quote_in"]
    return LiveBar(
        date.fromisoformat(golden["live_session_day"]),
        q["ltp"],
        q["open"],
        q["high"],
        q["low"],
        q["close"],
        float(q["volume"]),
        float(q["trades"]),
    )


class FakeInputs:
    def __init__(self, *inputs: AnalysisInput) -> None:
        self.by_symbol = {i.symbol: i for i in inputs}
        self.loads: list[str] = []

    async def load(self, symbol: str) -> AnalysisInput:
        self.loads.append(symbol)
        if symbol not in self.by_symbol:
            raise NotFoundError(f"{symbol} is not a DSE trading code")
        return self.by_symbol[symbol]
