"""Composition root for the HTTP API. The only module that wires concrete infrastructure together."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dse.core.cache import create_redis
from dse.core.clock import DHAKA, SystemClock
from dse.core.config import Settings, get_settings
from dse.core.db import Database
from dse.core.errors import install_error_handlers
from dse.core.http import health_router, request_context
from dse.core.logging import configure_logging
from dse.core.security import Argon2PasswordHasher, JwtCodec
from dse.core.tasks import cancel_and_wait
from dse.features.analysis.infrastructure.gateways import FacadeAnalysisInputs, FacadeHistorySource
from dse.features.analysis.presentation.dependencies import AnalysisContainer
from dse.features.analysis.presentation.router import router as analysis_router
from dse.features.charts.application.sources import RoutedCandles
from dse.features.charts.application.use_cases import GetChart, ListIndicators
from dse.features.charts.infrastructure.cache import RedisChartCache
from dse.features.charts.infrastructure.dse_index import DseIndexCandles
from dse.features.charts.infrastructure.gateways import DseDailyCandles, RecordedTickCandles
from dse.features.charts.presentation.dependencies import ChartsContainer
from dse.features.charts.presentation.router import router as charts_router
from dse.features.company.infrastructure.gateways import CompanySourceSet, FacadeAnalysis, LiveFeedPrices
from dse.features.company.infrastructure.http_sources import HttpCompanySources
from dse.features.company.presentation.dependencies import CompanyContainer
from dse.features.company.presentation.router import alerts_router
from dse.features.company.presentation.router import router as company_router
from dse.features.identity.infrastructure.throttle import RedisLoginThrottle
from dse.features.identity.presentation.dependencies import IdentityContainer
from dse.features.identity.presentation.router import router as identity_router
from dse.features.live_feed.application.hub import FeedHub
from dse.features.live_feed.infrastructure.redis_adapters import RedisEventStream, RedisLiveStateStore
from dse.features.live_feed.presentation.dependencies import LiveFeedContainer
from dse.features.live_feed.presentation.router import router as live_feed_router
from dse.features.market_data.infrastructure.dse_source import DseHttpSource
from dse.features.market_data.presentation.dependencies import MarketDataContainer
from dse.features.market_data.presentation.router import admin_router as admin_router
from dse.features.market_data.presentation.router import data_router as data_router
from dse.features.market_data.presentation.router import router as market_data_router
from dse.features.scanner.application.facade import ScannerFacade
from dse.features.scanner.application.view import UniverseView
from dse.features.scanner.infrastructure.redis_store import RedisUniverseStore
from dse.features.scanner.presentation.dependencies import ScannerContainer
from dse.features.scanner.presentation.router import router as scanner_router
from dse.features.watchlists.infrastructure.gateways import LiveFeedSymbolDirectory, ScannerScanValidator
from dse.features.watchlists.presentation.dependencies import WatchlistsContainer
from dse.features.watchlists.presentation.router import router as watchlists_router

VERSION = "0.8.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.assert_production_safe()
    configure_logging(settings.log_level)
    db = Database(settings.database)
    redis = create_redis(settings.redis)
    clock = SystemClock()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        source = DseHttpSource(
            settings.upstream.base_url,
            clock,
            user_agent=settings.upstream.user_agent,
            timeout_s=settings.upstream.timeout_s,
            min_page_interval_s=settings.upstream.min_page_interval_s,
        )
        app.state.db, app.state.redis = db, redis
        app.state.market_data = MarketDataContainer(db, source, clock)
        hub = FeedHub(RedisEventStream(redis), queue_size=settings.live.subscriber_queue)
        app.state.live_feed = LiveFeedContainer(
            RedisLiveStateStore(redis), hub, clock, settings.live, db, DHAKA
        )
        sec = settings.security
        jwt_codec = JwtCodec(
            sec.jwt_secret.get_secret_value(), sec.issuer, timedelta(minutes=sec.access_token_minutes), clock
        )
        app.state.jwt = jwt_codec
        app.state.identity = IdentityContainer(
            db=db,
            hasher=Argon2PasswordHasher(),
            throttle=RedisLoginThrottle(redis, sec.max_failed_logins, sec.lockout_minutes * 60),
            tokens=jwt_codec,
            clock=clock,
            settings=sec,
            cookie_secure=settings.cookie_secure,
            cookie_path=f"{settings.api_prefix}/auth",
        )
        app.state.watchlists = WatchlistsContainer(
            db=db,
            directory=LiveFeedSymbolDirectory(app.state.live_feed.facade),
            validator=ScannerScanValidator(ScannerFacade()),
            clock=clock,
        )
        app.state.scanner = ScannerContainer(UniverseView(RedisUniverseStore(redis)))
        app.state.analysis = AnalysisContainer(
            FacadeAnalysisInputs(app.state.market_data.facade, app.state.live_feed.facade),
            FacadeHistorySource(app.state.market_data.facade, app.state.live_feed.facade),
        )
        company_sources = HttpCompanySources(
            redis, user_agent=settings.upstream.user_agent, timeout_s=settings.upstream.timeout_s
        )
        app.state.company = CompanyContainer.build(
            CompanySourceSet(app.state.market_data.facade, company_sources),
            LiveFeedPrices(app.state.live_feed.facade),
            FacadeAnalysis(app.state.analysis.facade),
            clock,
        )
        index_candles = DseIndexCandles(
            redis, user_agent=settings.upstream.user_agent, timeout_s=settings.upstream.timeout_s
        )
        catalog = ListIndicators()
        app.state.charts = ChartsContainer(
            chart=GetChart(
                RoutedCandles(
                    DseDailyCandles(app.state.market_data.facade),
                    index_candles,
                    RecordedTickCandles(app.state.live_feed.facade, clock.today),
                ),
                RedisChartCache(redis),
                catalog,
            ),
            indicators=catalog,
        )
        hub_task = asyncio.create_task(hub.run(), name="live-feed-hub")
        yield
        await cancel_and_wait(hub_task)
        await source.aclose()
        await company_sources.aclose()
        await index_candles.aclose()
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
    v1.include_router(identity_router)
    v1.include_router(market_data_router)
    v1.include_router(admin_router)
    v1.include_router(data_router)
    v1.include_router(watchlists_router)
    v1.include_router(live_feed_router)
    v1.include_router(analysis_router)
    v1.include_router(scanner_router)
    v1.include_router(company_router)
    v1.include_router(charts_router)
    v1.include_router(alerts_router)
    app.include_router(v1)
    return app


app = create_app()
