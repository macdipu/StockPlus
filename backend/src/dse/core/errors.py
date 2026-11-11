"""The single mapping from domain errors to RFC 7807 problem+json responses."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from dse.core.logging import request_id_var
from dse.shared_kernel.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    ServiceNotReadyError,
    TooManyRequestsError,
    UnauthorizedError,
    UpstreamUnavailableError,
    ValidationFailedError,
)

log = logging.getLogger("dse.errors")

STATUS: dict[type[DomainError], int] = {
    ValidationFailedError: 400,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    UpstreamUnavailableError: 502,
    ServiceNotReadyError: 503,
    TooManyRequestsError: 429,
}


def status_for(exc: DomainError) -> int:
    for cls in type(exc).__mro__:
        if cls in STATUS:
            return STATUS[cls]
    return 500


def problem(
    request: Request,
    status: int,
    title: str,
    detail: str | None = None,
    headers: dict[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    body = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "requestId": request_id_var.get(),
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type="application/problem+json", headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        status = status_for(exc)
        if status >= 500:
            log.warning("domain error", extra={"error": type(exc).__name__, "detail": exc.detail})
        headers: dict[str, str] = {}
        if status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        if isinstance(exc, TooManyRequestsError):
            headers["Retry-After"] = str(exc.retry_after_s)
        return problem(request, status, HTTPStatus(status).phrase, exc.detail, headers or None, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return problem(request, 422, "Validation failed", detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(request, exc.status_code, HTTPStatus(exc.status_code).phrase, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return problem(request, 500, "Internal error", "See server logs with this requestId.")
