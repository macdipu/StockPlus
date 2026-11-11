"""Runs against the real stack: `docker compose up -d db redis` then `pytest -m integration`."""

import pytest
from fastapi.testclient import TestClient

from dse.main import create_app

pytestmark = pytest.mark.integration


def test_ready_with_real_postgres_and_redis() -> None:
    with TestClient(create_app()) as c:
        r = c.get("/api/v1/ready")
        assert r.status_code == 200, r.json()
        assert r.json()["checks"] == {"database": "ok", "redis": "ok"}
        assert c.get("/api/v1/openapi.json").json()["info"]["title"] == "DSE Live Analyzer API"
