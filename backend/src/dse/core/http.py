"""HTTP cross-cutting concerns: request id + timing middleware, response envelope, health router."""

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dse.core.logging import request_id_var

T = TypeVar("T")

DISCLAIMER = "For research only, not investment advice."


class Meta(BaseModel):
    requestId: str | None = None  # noqa: N815 — public JSON contract is camelCase
    disclaimer: str = DISCLAIMER
    model_config = {"extra": "allow"}


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta


def envelope(data: Any, **meta: Any) -> dict[str, Any]:
    return {"data": data, "meta": Meta(requestId=request_id_var.get(), **meta).model_dump()}


async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    token = request_id_var.set(rid)
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = rid
    response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - t0) * 1000:.1f}"
    return response


Check = Callable[[], Awaitable[None]]


def health_router(version: str, checks: dict[str, Check]) -> APIRouter:
    router = APIRouter(tags=["ops"])

    @router.get("/health", summary="Liveness: the process is up")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": version}

    @router.get("/ready", summary="Readiness: every dependency answers")
    async def ready() -> JSONResponse:
        results: dict[str, str] = {}
        for name, check in checks.items():
            try:
                await check()
                results[name] = "ok"
            except Exception as e:
                results[name] = f"error: {type(e).__name__}"
        ok = all(v == "ok" for v in results.values())
        return JSONResponse(
            {"status": "ready" if ok else "degraded", "checks": results}, status_code=200 if ok else 503
        )

    return router
