"""The scanner through the real stack: worker-side build → Redis → API replicas (Phase 4 exit criteria).

  * presets give the same results as legacy on the fixed universe, end to end over HTTP
  * scan p95 < 50 ms on a realistic (~430 instrument) universe
  * every replica serves the one published universe

Redis db 15 (isolated from a running dev worker on db 0).
"""

import asyncio
import json
import statistics
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dse.core.cache import create_redis
from dse.core.config import RedisSettings, Settings, get_settings
from dse.features.scanner.application.ports import StoredUniverse
from dse.features.scanner.application.use_cases import MaterialiseUniverse
from dse.features.scanner.infrastructure.redis_store import RedisUniverseStore
from dse.features.scanner.tests.fakes import FakeClock, FakeSource, Notifier
from dse.main import create_app

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parents[2] / "src/dse/features/scanner/tests/fixtures"


def isolated_settings() -> Settings:
    base = get_settings()
    return base.model_copy(update={"redis": RedisSettings(url=base.redis.url.rsplit("/", 1)[0] + "/15")})


async def flush() -> None:
    r = create_redis(isolated_settings().redis)
    await r.flushdb()
    await r.aclose()


async def publish_fixture_universe(history: Any, quotes: Any, day: date) -> int:
    r = create_redis(isolated_settings().redis)
    try:
        report = await MaterialiseUniverse(
            FakeSource(history, quotes, day), RedisUniverseStore(r), Notifier(), FakeClock()
        )()
        return report.version
    finally:
        await r.aclose()


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    return dict(json.loads((FIXTURES / "legacy_golden_universe.json").read_text()))


@pytest.fixture(scope="module")
def published(history: Any, quotes: Any, session_day: date) -> Iterator[int]:
    asyncio.run(flush())
    yield asyncio.run(publish_fixture_universe(history, quotes, session_day))
    asyncio.run(flush())


@pytest.fixture(scope="module")
def client(published: int) -> Iterator[TestClient]:
    with TestClient(create_app(isolated_settings())) as c:
        yield c


def test_status_and_catalogue(client: TestClient, published: int) -> None:
    st = client.get("/api/v1/scanner/universe").json()["data"]
    assert (st["ready"], st["rows"], st["version"]) == (True, 48, published)
    assert st["errors"] == {}
    presets = client.get("/api/v1/scanner/presets").json()
    assert presets["meta"]["count"] == 41
    assert {p["key"] for p in presets["data"]} >= {"golden_cross", "hammer", "short_term_setup"}
    f = client.get("/api/v1/scanner/fields").json()["data"]
    assert "rsi14" in f["fields"]
    assert "between" in f["ops"]


def test_every_preset_over_http_matches_legacy(client: TestClient, golden: dict[str, Any]) -> None:
    for key, want in golden["presets"].items():
        r = client.get(f"/api/v1/scanner/presets/{key}?limit=100")
        assert r.status_code == 200, (key, r.text)
        body = r.json()
        got = [row["symbol"] for row in body["data"]]
        assert sorted(got) == sorted(want["symbols"]), key
        assert body["meta"]["live"] is (not want["premarket"])
        assert body["meta"]["preset"]["key"] == key
        assert body["meta"]["scanned"] == 48


def test_premarket_presets_now_work_with_the_default_filter(client: TestClient) -> None:
    for key in ("nr7", "inside_bar", "bullish_candles", "hammer", "bullish_engulfing", "pre_market_watch"):
        body = client.get(f"/api/v1/scanner/presets/{key}").json()  # default asset_types=EQ
        assert body["meta"]["matched"] > 0, key  # legacy returned nothing for all of these


def test_custom_scan_and_validation(client: TestClient, golden: dict[str, Any]) -> None:
    body = {
        "rules": [
            {"field": "rsi14", "op": "between", "value": [40, 80]},
            {"field": "close", "op": ">", "field2": "ema21"},
        ],
        "universe": {"categories": ["A", "B"], "min_value_mn": 1.0},
        "sort": {"field": "vol_ratio", "desc": True},
        "limit": 50,
    }
    r = client.post("/api/v1/scanner/run", json=body)
    assert r.status_code == 200, r.text
    assert sorted(x["symbol"] for x in r.json()["data"]) == sorted(golden["custom"]["all"])
    assert r.json()["meta"]["universe_version"] > 0

    bad_field = client.post("/api/v1/scanner/run", json={"rules": [{"field": "nope", "op": ">", "value": 1}]})
    assert bad_field.status_code == 400
    assert bad_field.headers["content-type"] == "application/problem+json"
    assert "Unknown field 'nope'" in bad_field.json()["detail"]
    assert (
        client.post(
            "/api/v1/scanner/run", json={"rules": [{"field": "rsi14", "op": "wat", "value": 1}]}
        ).status_code
        == 422
    )
    assert client.post("/api/v1/scanner/run", json={"rules": []}).status_code == 422
    assert (
        client.post("/api/v1/scanner/run", json={"rules": [{"field": "rsi14", "op": "<"}]}).status_code == 400
    )
    assert client.get("/api/v1/scanner/presets/nope").status_code == 404


def test_market_analytics_endpoints(client: TestClient) -> None:
    sectors = client.get("/api/v1/market/sectors").json()["data"]
    assert sum(s["instruments"] for s in sectors) == 48
    pe = client.get("/api/v1/market/pe").json()["data"]
    assert pe["market"]["instruments"] > 0
    rng = client.get("/api/v1/market/52-week?near=low&limit=5").json()
    assert rng["meta"]["count"] == 5
    positions = [r["range_position_pct"] for r in rng["data"]]
    assert positions == sorted(positions)
    ta = client.get("/api/v1/market/ta-values?sector=Bank&columns=symbol,rsi14,nope").json()["data"]
    assert ta
    assert set(ta[0]) == {"symbol", "rsi14"}
    matrix = client.get("/api/v1/market/data-matrix").json()
    assert matrix["meta"]["count"] == 48
    assert {"pe", "pb", "graham_gap_pct"} <= set(matrix["data"][0])


def test_two_replicas_serve_the_one_published_universe(
    published: int, history: Any, quotes: Any, session_day: date
) -> None:
    with TestClient(create_app(isolated_settings())) as a, TestClient(create_app(isolated_settings())) as b:
        va = a.get("/api/v1/scanner/presets/rsi_oversold").json()["meta"]["universe_version"]
        vb = b.get("/api/v1/scanner/presets/rsi_oversold").json()["meta"]["universe_version"]
        assert va == vb
        v2 = asyncio.run(publish_fixture_universe(history, quotes, session_day))  # the worker publishes again
        assert v2 > va
        for c in (a, b):  # each replica notices the new version on its next request
            assert c.get("/api/v1/scanner/presets/rsi_oversold").json()["meta"]["universe_version"] == v2


def test_not_ready_before_the_worker_publishes() -> None:
    asyncio.run(flush())
    try:
        with TestClient(create_app(isolated_settings())) as c:
            assert c.get("/api/v1/scanner/universe").json()["data"]["ready"] is False
            r = c.get("/api/v1/market/sectors")
            assert r.status_code == 503
            assert r.headers["content-type"] == "application/problem+json"
            assert c.get("/api/v1/scanner/presets/rsi_oversold").status_code == 503
            assert c.get("/api/v1/scanner/presets").status_code == 200  # the catalogue needs no data
    finally:
        asyncio.run(flush())


# ---------------------------------------------------------------------------- performance exit criterion


def publish_realistic_universe(golden: dict[str, Any], copies: int = 9) -> int:
    """~430 instruments by replicating the fixed universe's rows under distinct symbols."""

    def renamed(r: dict[str, Any], i: int) -> dict[str, Any]:
        out = {k: v for k, v in r.items() if k != "assetType"}  # golden rows use the legacy column name
        return {**out, "asset_type": r["assetType"] or "EQ", "symbol": f"{r['symbol']}{i}"}

    def replicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [renamed(r, i) for i in range(copies) for r in rows]

    async def go() -> int:
        r = create_redis(isolated_settings().redis)
        try:
            return await RedisUniverseStore(r).save(
                StoredUniverse(
                    built_at_ms=1,
                    build_ms=1,
                    session_day=date(2026, 11, 11),
                    trade_time="11:40",
                    live_rows=replicate(golden["live"]),
                    last_close_rows=replicate(golden["last_close"]),
                    errors={},
                )
            )
        finally:
            await r.aclose()

    asyncio.run(flush())
    return asyncio.run(go())


def test_scan_p95_is_under_50ms_on_a_realistic_universe(golden: dict[str, Any]) -> None:
    publish_realistic_universe(golden)
    requests: list[tuple[str, str, dict[str, Any] | None]] = [
        ("GET", "/api/v1/scanner/presets/short_term_setup", None),
        ("GET", "/api/v1/scanner/presets/golden_cross", None),
        ("GET", "/api/v1/scanner/presets/volume_spike_up?limit=50", None),
        ("GET", "/api/v1/scanner/presets/hammer", None),
        ("GET", "/api/v1/market/sectors", None),
        (
            "POST",
            "/api/v1/scanner/run",
            {
                "rules": [
                    {"field": "rsi14", "op": "between", "value": [40, 80]},
                    {"field": "close", "op": ">", "field2": "ema21"},
                    {"field": "vol_ratio", "op": ">=", "value": 1.2},
                ],
                "universe": {"asset_types": ["EQ"], "categories": ["A", "B"]},
                "sort": {"field": "vol_ratio", "desc": True},
                "limit": 50,
            },
        ),
    ]
    try:
        with TestClient(create_app(isolated_settings())) as c:
            st = c.get("/api/v1/scanner/universe").json()["data"]
            assert st["rows"] == 48 * 9
            t0 = time.perf_counter()
            c.get("/api/v1/scanner/presets/rsi_oversold")  # first request pays the one-off frame rebuild
            cold_ms = (time.perf_counter() - t0) * 1000
            for _ in range(10):  # warm up
                for m, path, body in requests:
                    c.request(m, path, json=body)
            samples = []
            for _ in range(60):
                for m, path, body in requests:
                    t = time.perf_counter()
                    r = c.request(m, path, json=body)
                    samples.append((time.perf_counter() - t) * 1000)
                    assert r.status_code == 200, (path, r.json()["detail"])
        samples.sort()
        p50, p95, p99 = (
            statistics.median(samples),
            samples[int(len(samples) * 0.95)],
            samples[int(len(samples) * 0.99)],
        )
        print(
            f"\nscan latency, {len(samples)} requests on 432 instruments: p50={p50:.1f} ms "
            f"p95={p95:.1f} ms p99={p99:.1f} ms; "
            f"first request after a publish (frame rebuild) {cold_ms:.0f} ms"
        )
        assert p95 < 50, f"p95 {p95:.1f} ms"
        assert cold_ms < 1000
    finally:
        asyncio.run(flush())
