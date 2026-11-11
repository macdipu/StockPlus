import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from dse.features.live_feed.domain.entities import LiveSnapshot
from dse.features.live_feed.infrastructure.dse_snapshot import parse_live_snapshot

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def snapshot_json() -> dict[str, Any]:
    with gzip.open(FIXTURES / "snapshot.json.gz", "rt") as f:
        return dict(json.load(f))


@pytest.fixture(scope="session")
def legacy_golden() -> dict[str, Any]:
    return dict(json.loads((FIXTURES / "legacy_golden_snapshot.json").read_text()))


@pytest.fixture(scope="session")
def snapshot(snapshot_json: dict[str, Any]) -> LiveSnapshot:
    return parse_live_snapshot(snapshot_json)
