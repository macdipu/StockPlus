import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dse.core.config import Settings
from dse.core.errors import install_error_handlers
from dse.core.http import health_router, request_context
from dse.core.logging import JsonFormatter, request_id_var
from dse.shared_kernel.errors import NotFoundError, UpstreamUnavailableError


def test_settings_from_env_with_nesting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DSE_DATABASE__URL", "postgresql+asyncpg://u:p@h:1/d")
    monkeypatch.setenv("DSE_UPSTREAM__MIN_PAGE_INTERVAL_S", "3")
    s = Settings()
    assert s.database.url.endswith("h:1/d")
    assert s.upstream.min_page_interval_s == 3


def test_production_refuses_default_secret() -> None:
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings(env="production").assert_production_safe()


def test_production_requires_a_long_random_secret() -> None:
    from pydantic import SecretStr

    from dse.core.config import SecuritySettings

    def prod(secret: str) -> Settings:
        return Settings(env="production", security=SecuritySettings(jwt_secret=SecretStr(secret)))

    for weak in ("dev-only-insecure-secret", "short"):
        with pytest.raises(RuntimeError):
            prod(weak).assert_production_safe()
    with pytest.raises(RuntimeError, match="at least 32"):
        prod("x" * 31).assert_production_safe()
    prod("x" * 32).assert_production_safe()  # long enough: fine
    Settings(env="development").assert_production_safe()  # dev keeps its convenient default


def test_the_default_upstream_identity_is_honest() -> None:
    from dse.core.config import DEFAULT_USER_AGENT, UpstreamSettings

    ua = UpstreamSettings().user_agent
    assert ua == DEFAULT_USER_AGENT
    assert ua.startswith("dse-analyzer/")
    assert not any(w in ua.lower() for w in ("mozilla", "chrome", "safari", "applewebkit", "gecko"))
    assert "@" not in ua  # no personal contact baked into a default; the operator may add one


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
        "title": "Not Found",
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


async def test_cancel_and_wait_ends_a_task_that_swallows_the_first_cancel() -> None:
    import asyncio

    from dse.core.tasks import cancel_and_wait

    swallowed = 0

    async def stubborn() -> None:
        nonlocal swallowed
        while True:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                swallowed += 1
                if swallowed >= 2:
                    raise

    task = asyncio.create_task(stubborn())
    await asyncio.sleep(0)
    await asyncio.wait_for(cancel_and_wait(task, retry_s=0.05), 3)
    assert task.cancelled()
    assert swallowed == 2
