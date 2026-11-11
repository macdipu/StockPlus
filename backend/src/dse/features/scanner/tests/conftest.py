import gzip
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from dse.features.analysis.application.facade import Bar, QuoteInput, UniverseInput

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def golden() -> dict[str, Any]:
    return dict(json.loads((FIXTURES / "legacy_golden_universe.json").read_text()))


@pytest.fixture(scope="session")
def raw_inputs() -> dict[str, Any]:
    with gzip.open(FIXTURES / "universe_inputs.json.gz", "rt") as f:
        return dict(json.load(f))


@pytest.fixture(scope="session")
def session_day(raw_inputs: dict[str, Any]) -> date:
    return date.fromisoformat(raw_inputs["session"]["date"])


@pytest.fixture(scope="session")
def history(raw_inputs: dict[str, Any]) -> list[UniverseInput]:
    """History + fundamentals only (no quotes). The instrument record supplies asset_type (new design)."""
    out = []
    for sym, rows in raw_inputs["bars"].items():
        bars = tuple(Bar(date.fromisoformat(d), o, h, lo, c, v, t) for d, o, h, lo, c, v, t in rows)
        out.append(UniverseInput(sym, bars, raw_inputs["fundamentals"][sym]))
    return out


@pytest.fixture(scope="session")
def quotes(raw_inputs: dict[str, Any]) -> dict[str, QuoteInput]:
    return {
        s: QuoteInput(
            ltp=q["ltp"],
            ycp=q["ycp"],
            open=q["open"],
            high=q["high"],
            low=q["low"],
            close=q["close"],
            volume=float(q["volume"]),
            value_mn=q["value"],
            trades=q["trades"],
            percent=q["percent"],
            sector=q["sector"],
            category=q["category"],
            asset_type=q["assetType"],
        )
        for s, q in raw_inputs["quotes"].items()
    }
