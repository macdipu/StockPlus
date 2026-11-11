import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dse.core.config import Settings
from dse.core.errors import NotFoundError, UpstreamUnavailableError, install_error_handlers
from dse.core.http import health_router, request_context
from dse.core.logging import JsonFormatter, request_id_var


def test_settings_from_env_with_nesting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DSE_DATABASE__URL", "postgresql+asyncpg://u:p@h:1/d")
    monkeypatch.setenv("DSE_UPSTREAM__MIN_PAGE_INTERVAL_S", "3")
    s = Settings()
    assert s.database.url.endswith("h:1/d")
    assert s.upstream.min_page_interval_s == 3


def test_production_refuses_default_secret() -> None:
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings(env="production").assert_production_safe()


def test_json_log_carries_request_id() -> None:
    token = request_id_var.set("rid-1")
    try:
        rec = logging.LogRecord("x", logging.INFO, __file__, 1, "hello %s", ("w",), None)
        rec.symbol = "GP"
        out = json.loads(JsonFormatter().format(rec))
    finally:
        request_id_var.reset(token)
    assert out["msg"] == "hello w"
    assert out["request_id"] == "rid-1"
    assert out["symbol"] == "GP"


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(request_context)
    install_error_handlers(app)

    async def ok() -> None: ...

    async def broken() -> None:
        raise ConnectionError("down")

    app.include_router(health_router("t", {"db": ok, "redis": broken}))

    @app.get("/missing")
    async def missing() -> None:
        raise NotFoundError("no such symbol", symbol="X")

    @app.get("/upstream")
    async def upstream() -> None:
        raise UpstreamUnavailableError("dse.com.bd timed out")

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")

    return app


def test_errors_are_problem_json_with_request_id() -> None:
    c = TestClient(_app(), raise_server_exceptions=False)
    r = c.get("/missing", headers={"X-Request-ID": "abc"})
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json() == {
        "type": "about:blank",
        "title": "Not found",
        "status": 404,
        "detail": "no such symbol",
        "instance": "/missing",
        "requestId": "abc",
        "symbol": "X",
    }
    assert c.get("/upstream").status_code == 502
    boom = c.get("/boom").json()
    assert boom["status"] == 500
    assert "secret" not in boom["detail"]
    assert c.get("/nope").json()["title"] == "Not Found"


def test_health_and_readiness() -> None:
    c = TestClient(_app())
    assert c.get("/health").json() == {"status": "ok", "version": "t"}
    r = c.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"] == {"db": "ok", "redis": "error: ConnectionError"}
    assert "server-timing" in r.headers
    assert r.headers["x-request-id"]
