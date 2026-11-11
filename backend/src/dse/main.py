"""Composition root for the HTTP API. The only module that wires concrete infrastructure together."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dse.core.cache import create_redis
from dse.core.config import Settings, get_settings
from dse.core.db import Database
from dse.core.errors import install_error_handlers
from dse.core.http import health_router, request_context
from dse.core.logging import configure_logging

VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.assert_production_safe()
    configure_logging(settings.log_level)
    db = Database(settings.database)
    redis = create_redis(settings.redis)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.db, app.state.redis = db, redis
        yield
        await redis.aclose()
        await db.dispose()

    async def ping_redis() -> None:
        await redis.ping()

    app = FastAPI(
        title="DSE Live Analyzer API",
        version=VERSION,
        lifespan=lifespan,
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )
    app.middleware("http")(request_context)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    install_error_handlers(app)

    v1 = APIRouter(prefix=settings.api_prefix)
    v1.include_router(health_router(VERSION, {"database": db.ping, "redis": ping_redis}))
    # feature routers are mounted here as each feature migrates (see docs/architecture §8)
    app.include_router(v1)
    return app


app = create_app()
