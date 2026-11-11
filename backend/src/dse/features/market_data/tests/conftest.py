import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from dse.features.market_data.domain.entities import CompanyPage, MarketSnapshot
from dse.features.market_data.infrastructure.dse_parser import parse_company_page, parse_snapshot
from dse.features.market_data.tests.fakes import NOW, Store
from dse.shared_kernel.symbol import Symbol

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def company_html() -> str:
    with gzip.open(FIXTURES / "company_ORIONINFU.html.gz", "rt") as f:
        return f.read()


@pytest.fixture(scope="session")
def snapshot_json() -> dict[str, Any]:
    with gzip.open(FIXTURES / "snapshot.json.gz", "rt") as f:
        return dict(json.load(f))


@pytest.fixture(scope="session")
def golden() -> dict[str, Any]:
    return dict(json.loads((FIXTURES / "legacy_golden_ORIONINFU.json").read_text()))


@pytest.fixture(scope="session")
def page(company_html: str) -> CompanyPage:
    return parse_company_page(company_html, Symbol("ORIONINFU"), NOW)


@pytest.fixture(scope="session")
def snapshot(snapshot_json: dict[str, Any]) -> MarketSnapshot:
    return parse_snapshot(snapshot_json)


@pytest.fixture
def store() -> Store:
    return Store()
