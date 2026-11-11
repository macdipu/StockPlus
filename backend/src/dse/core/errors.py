"""Error hierarchy shared by all features, and its single mapping to RFC 7807 responses.

Domain and application code raise these (no HTTP knowledge); presentation maps them once, here.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from dse.core.logging import request_id_var


class AppError(Exception):
    status: int = 500
    title: str = "Internal error"

    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        self.extra = extra


class ValidationFailedError(AppError):
    status, title = 400, "Bad request"


class NotFoundError(AppError):
    status, title = 404, "Not found"


class ConflictError(AppError):
    status, title = 409, "ConflictError"


class UnauthorizedError(AppError):
    status, title = 401, "UnauthorizedError"


class ForbiddenError(AppError):
    status, title = 403, "ForbiddenError"


class UpstreamUnavailableError(AppError):
    status, title = 502, "Upstream unavailable"


class ServiceNotReadyError(AppError):
    status, title = 503, "Service not ready"


def problem(
    request: Request, status: int, title: str, detail: str | None = None, **extra: Any
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
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def install_error_handlers(app: FastAPI) -> None:
    log = logging.getLogger("dse.errors")

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status >= 500:
            log.warning("app error", extra={"error": type(exc).__name__, "detail": exc.detail})
        return problem(request, exc.status, exc.title, exc.detail, **exc.extra)

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
