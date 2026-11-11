"""HTTP API + live stream + web view.

    uvicorn api:app --port 8000          (or: python main.py serve)

Contract
  * Versioned under /api/v1. OpenAPI at /api/v1/openapi.json, docs at /docs.
  * Success: {"data": ..., "meta": {...}}. Errors: RFC 7807 application/problem+json with requestId.
  * Every response carries X-Request-ID (echoed if the client sent one) and Server-Timing.
  * Live data: GET /api/v1/stream (Server-Sent Events): quote / analysis / market / heartbeat events.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from http import HTTPStatus
from contextlib import asynccontextmanager
from typing import Any, Dict, Generic, List, Optional, TypeVar

import plotly as _plotly
from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import config as C
import market_api
import report
import scraper
import service
import store
from live import LiveFeed

VERSION = "1.0.0"
API = "/api/v1"
log = logging.getLogger("dse.api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")

SYMBOL_PATH = Path(..., pattern=scraper.SYMBOL_RE.pattern.replace("A-Z", "A-Za-z"),
                   description="DSE trading code, e.g. ORIONINFU", examples=["ORIONINFU"])


# =========================================================================== models
T = TypeVar("T")


class Meta(BaseModel):
    requestId: str
    source: Optional[str] = None
    asOf: Optional[str] = None
    tradeTime: Optional[str] = Field(None, description="Upstream trade time of the live snapshot used")
    disclaimer: str = report.DISCLAIMER


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: Optional[str] = None
    instance: Optional[str] = None
    requestId: Optional[str] = None


class Quote(BaseModel):
    symbol: str
    ltp: Optional[float] = None
    ycp: Optional[float] = Field(None, description="Yesterday's close")
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = Field(None, description="Official close; null while the session is open")
    change: Optional[float] = None
    percent: Optional[float] = None
    volume: Optional[float] = None
    value: Optional[float] = Field(None, description="Turnover, BDT million")
    trades: Optional[int] = None
    category: Optional[str] = None
    board: Optional[str] = None
    sector: Optional[str] = None
    assetType: Optional[str] = None
    tradeTime: Optional[str] = None


class Candle(BaseModel):
    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    sma20: Optional[float] = None
    sma50: Optional[float] = None
    sma200: Optional[float] = None
    ema9: Optional[float] = None
    ema21: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    vol_avg20: Optional[float] = None


class TradePlan(BaseModel):
    entry: float
    entry_zone: List[float]
    stop: float
    stop_basis: str
    target: float
    target_basis: str
    atr: float
    risk_pct: float
    reward_pct: float
    rr: Optional[float] = None
    rr_ok: bool


class Setup(BaseModel):
    score: int
    max: int
    checks: List[Dict[str, Any]]
    plan: TradePlan
    flags: List[str]


class Signal(BaseModel):
    action: str = Field(..., description="STRONG BUY | BUY | HOLD | SELL | STRONG SELL | AVOID")
    net_votes: int
    bullish_reasons: List[str]
    bearish_reasons: List[str]
    rule: str


class ProbabilityStats(BaseModel):
    n: int
    wins: int
    losses: int
    unresolved: int
    p_target_first: Optional[float] = None
    avg_fwd_return_pct: Optional[float] = None
    pct_positive_fwd: Optional[float] = None
    expectancy_pct: Optional[float] = None


class Probability(BaseModel):
    horizon_sessions: int
    target_pct: float
    stop_pct: float
    similar_setups: ProbabilityStats
    all_days_baseline: ProbabilityStats
    reliable: bool
    warning: Optional[str] = None
    method: str


class Analysis(BaseModel):
    symbol: str
    name: Optional[str] = None
    as_of: Optional[str] = None
    price: Dict[str, Any]
    signal: Signal
    setup: Setup
    probability: Probability
    indicators: Dict[str, Optional[float]]
    candles: Dict[str, Any]
    levels: Dict[str, Any]
    trend: Dict[str, Any]
    valuation: Dict[str, Any]
    fundamentals: Dict[str, Any]
    news: List[Dict[str, Any]]
    summary: List[str]
    source: Optional[str] = None
    disclaimer: str


class ScreenerRow(BaseModel):
    rank: int
    symbol: str
    ltp: Optional[float] = None
    action: str
    score: int
    rr: Optional[float] = None
    p_target_first: Optional[float] = None
    error: Optional[str] = None


# =========================================================================== application state
class State:
    feed: LiveFeed
    universe: "market_api.Universe"
    payloads: Dict[tuple, dict] = {}          # (symbol, day) -> company page payload
    locks: Dict[str, asyncio.Lock] = {}       # single-flight per symbol
    analyses: Dict[tuple, tuple] = {}         # (symbol, day, tradeTime, ltp, volume) -> (knowledge, ind)


S = State()


async def get_payload(symbol: str) -> dict:
    key = (symbol, scraper.today())
    if key in S.payloads:
        return S.payloads[key]
    lock = S.locks.setdefault(symbol, asyncio.Lock())
    async with lock:
        if key not in S.payloads:
            S.payloads[key] = await run_in_threadpool(scraper.fetch_company, symbol)
            for k in [k for k in S.payloads if k[1] != key[1]]:   # drop previous days
                S.payloads.pop(k, None)
    return S.payloads[key]


async def get_analysis(symbol: str):
    payload = await get_payload(symbol)
    q = S.feed.quotes.get(symbol)
    key = (symbol, scraper.today(), S.feed.trade_time, (q or {}).get("ltp"), (q or {}).get("volume"))
    if key not in S.analyses:
        S.analyses[key] = await run_in_threadpool(service.build, payload, q, S.feed.session)
        for k in [k for k in S.analyses if k[0] == symbol and k != key]:
            S.analyses.pop(k, None)
    return S.analyses[key]


def live_view(k: dict, ind) -> dict:
    """Compact analysis pushed on every tick: what the dashboard re-renders."""
    return {"symbol": k["symbol"], "price": k["price"], "signal": k["signal"], "setup": k["setup"],
            "probability": {**k["probability"]}, "indicators": k["indicators"], "levels": k["levels"],
            "trend": k["trend"], "patterns": k["candles"]["patterns"], "lastCandle": k["candles"]["last_candle"],
            "summary": k["summary"], "candles": service.candles(ind, 2)}


async def on_ticks(changed: set) -> None:
    for sym in changed & S.feed.watched_symbols():
        try:
            k, ind = await get_analysis(sym)
            S.feed.publish("analysis", report._clean(live_view(k, ind)), symbol=sym)
        except Exception as e:  # never let one symbol break the feed
            log.warning("analysis recompute failed for %s: %s", sym, e)


async def on_ticks_market(changed: set) -> None:
    """Per upstream change: persist ticks, write the EOD bar after the close, rebuild the universe."""
    feed, sess = S.feed, S.feed.session
    if changed:
        await run_in_threadpool(store.record_ticks, [feed.quotes[s] for s in changed], feed.last_change_ms or 0,
                                feed.trade_time)
    if sess.get("tradingDay") and not sess.get("isOpen"):
        await run_in_threadpool(store.append_eod, {"session": sess, "quotes": feed.quotes})
    await S.universe.refresh()


def on_universe_built(u: market_api.Universe) -> None:
    S.feed.publish("universe", {"version": u.version, "rows": len(u.live), "buildMs": u.build_ms})


async def warm_up() -> None:
    if await S.feed.wait_ready(30):
        sess = S.feed.session
        if sess.get("tradingDay") and not sess.get("isOpen"):
            await run_in_threadpool(store.append_eod, {"session": sess, "quotes": S.feed.quotes})
        await S.universe.refresh()


@asynccontextmanager
async def lifespan(app: FastAPI):
    S.feed = LiveFeed()
    S.universe = market_api.Universe(S.feed)
    S.universe.on_built.append(on_universe_built)
    S.feed.on_change += [on_ticks, on_ticks_market]
    app.state.feed, app.state.universe = S.feed, S.universe
    await S.feed.start()
    warm = asyncio.create_task(warm_up())
    log.info("live feed started (poll %ss open / %ss closed)", C.LIVE_POLL_S, C.LIVE_POLL_CLOSED_S)
    yield
    warm.cancel()
    await S.feed.stop()


app = FastAPI(title="DSE Stock Analyzer API", version=VERSION, lifespan=lifespan,
              openapi_url=f"{API}/openapi.json", docs_url="/docs", redoc_url=None,
              description="Live quotes, candles, technical and fundamental analysis for Dhaka Stock Exchange "
                          "instruments, sourced from www.dse.com.bd. " + report.DISCLAIMER)


app.include_router(market_api.router)


# =========================================================================== middleware & errors
@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.rid = rid
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - t0) * 1000:.1f}"
    return response


def problem(request: Request, status: int, title: str, detail: Optional[str] = None) -> JSONResponse:
    body = Problem(title=title, status=status, detail=detail, instance=str(request.url.path),
                   requestId=getattr(request.state, "rid", None))
    return JSONResponse(body.model_dump(), status_code=status, media_type="application/problem+json")


@app.exception_handler(scraper.SymbolNotFound)
async def _not_found(request: Request, e: Exception):
    return problem(request, 404, "Unknown symbol", str(e))


@app.exception_handler(scraper.ScrapeError)
async def _upstream(request: Request, e: Exception):
    return problem(request, 502, "Upstream (dse.com.bd) error", str(e))


@app.exception_handler(scraper.InvalidInput)
async def _bad_value(request: Request, e: Exception):
    return problem(request, 400, "Bad request", str(e))


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, e: RequestValidationError):
    return problem(request, 422, "Validation failed", "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}"
                                                                for x in e.errors()))


@app.exception_handler(HTTPException)
async def _http(request: Request, e: HTTPException):
    return problem(request, e.status_code, HTTPStatus(e.status_code).phrase, str(e.detail))


@app.exception_handler(Exception)
async def _unhandled(request: Request, e: Exception):
    log.exception("unhandled error [%s]", getattr(request.state, "rid", "-"))
    return problem(request, 500, "Internal error", "See server logs with this requestId.")


def meta(request: Request, **kw) -> Meta:
    return Meta(requestId=request.state.rid, tradeTime=S.feed.trade_time, **kw)


def parse_symbols(raw: Optional[str], limit: Optional[int] = None) -> Optional[List[str]]:
    if not raw:
        return None
    syms = list(dict.fromkeys(scraper.normalize_symbol(s) for s in raw.split(",") if s.strip()))
    if limit and len(syms) > limit:
        raise scraper.InvalidInput(f"At most {limit} symbols per request")
    return syms


# =========================================================================== operational
@app.get(f"{API}/health", tags=["ops"], summary="Liveness")
async def health():
    return {"status": "ok", "version": VERSION}


@app.get(f"{API}/ready", tags=["ops"], summary="Readiness: live feed has data and is not stale")
async def ready():
    st = S.feed.status()
    stale = st["lastSuccessAgeMs"] is None or st["lastSuccessAgeMs"] > 5 * 60_000
    ok = st["ready"] and not stale
    return JSONResponse({"status": "ready" if ok else "degraded", "feed": st}, status_code=200 if ok else 503)


# =========================================================================== market & quotes
@app.get(f"{API}/market", tags=["market"], summary="Session, indices, breadth, totals, top movers")
async def market(request: Request) -> Envelope[Dict[str, Any]]:
    await S.feed.wait_ready()
    return Envelope(data=S.feed.market_summary(), meta=meta(request, source=C.SNAPSHOT_URL))


@app.get(f"{API}/quotes", tags=["market"], summary="Latest quotes (all traded instruments, or a list)")
async def quotes(request: Request,
                 symbols: Optional[str] = Query(None, description="Comma-separated codes; omit for all")
                 ) -> Envelope[List[Quote]]:
    await S.feed.wait_ready()
    wanted = parse_symbols(symbols)
    rows = [S.feed.quotes[s] for s in (wanted or sorted(S.feed.quotes)) if s in S.feed.quotes]
    return Envelope(data=[Quote(**q) for q in rows], meta=meta(request, source=C.SNAPSHOT_URL))


# =========================================================================== instrument resources
@app.get(f"{API}/stocks/{{symbol}}", tags=["stocks"], summary="Profile and fundamentals")
async def stock(request: Request, symbol: str = SYMBOL_PATH) -> Envelope[Dict[str, Any]]:
    sym = scraper.normalize_symbol(symbol)
    payload = await get_payload(sym)
    fund = scraper.fundamentals(payload, S.feed.quotes.get(sym))
    return Envelope(data=report._clean({"symbol": sym, **fund}),
                    meta=meta(request, source=payload["source"], asOf=payload["fetched_at"]))


@app.get(f"{API}/stocks/{{symbol}}/candles", tags=["stocks"],
         summary="Daily OHLCV with moving averages; today's bar is live while the market is open")
async def stock_candles(request: Request, symbol: str = SYMBOL_PATH,
                        limit: int = Query(260, ge=1, le=1000)) -> Envelope[List[Candle]]:
    sym = scraper.normalize_symbol(symbol)
    k, ind = await get_analysis(sym)
    return Envelope(data=[Candle(**c) for c in service.candles(ind, limit)],
                    meta=meta(request, source=k["source"], asOf=k["as_of"]))


@app.get(f"{API}/stocks/{{symbol}}/analysis", tags=["stocks"],
         summary="Full analysis — the single call an AI agent needs",
         description="Price, fundamentals, every indicator, candle patterns, support/resistance, trend, "
                     "valuation (with inputs), setup score, trade plan, signal with reasons, and the historical "
                     "short-term profit probability. Recomputed on every live tick.")
async def stock_analysis(request: Request, symbol: str = SYMBOL_PATH) -> Envelope[Analysis]:
    sym = scraper.normalize_symbol(symbol)
    k, _ = await get_analysis(sym)
    return Envelope(data=Analysis(**report._clean(k)), meta=meta(request, source=k["source"], asOf=k["as_of"]))


@app.get(f"{API}/stocks/{{symbol}}/brief", tags=["stocks"], response_class=PlainTextResponse,
         summary="Markdown brief sized for an LLM context window")
async def stock_brief(symbol: str = SYMBOL_PATH):
    k, _ = await get_analysis(scraper.normalize_symbol(symbol))
    return PlainTextResponse(report.brief(k), media_type="text/markdown; charset=utf-8")


@app.get(f"{API}/stocks/{{symbol}}/announcements", tags=["stocks"], summary="Recent DSE announcements")
async def stock_announcements(request: Request, symbol: str = SYMBOL_PATH,
                              limit: int = Query(20, ge=1, le=100)) -> Envelope[List[Dict[str, Any]]]:
    sym = scraper.normalize_symbol(symbol)
    payload = await get_payload(sym)
    return Envelope(data=scraper.news(payload, limit), meta=meta(request, source=payload["source"]))


@app.get(f"{API}/screener", tags=["stocks"], summary="Rank symbols by setup score, then risk/reward")
async def screener(request: Request, symbols: str = Query(..., description="Comma-separated codes")
                   ) -> Envelope[List[ScreenerRow]]:
    rows = []
    for sym in parse_symbols(symbols, C.SCREENER_MAX_SYMBOLS) or []:   # sequential on purpose: polite upstream
        try:
            k, _ = await get_analysis(sym)
            rows.append({"symbol": sym, "ltp": k["price"]["ltp"], "action": k["signal"]["action"],
                         "score": k["setup"]["score"], "rr": k["setup"]["plan"]["rr"],
                         "p_target_first": k["probability"]["similar_setups"]["p_target_first"]})
        except scraper.ScrapeError as e:
            rows.append({"symbol": sym, "action": "ERROR", "score": -1, "error": str(e)})
    rows.sort(key=lambda r: (r["score"], r.get("rr") or 0), reverse=True)
    return Envelope(data=[ScreenerRow(rank=i, **r) for i, r in enumerate(rows, 1)], meta=meta(request))


# =========================================================================== live stream
@app.get(f"{API}/stream", tags=["live"], summary="Server-Sent Events: live quotes and recomputed analysis",
         description="Events: `snapshot` (on connect), `quote` (a watched symbol's quote changed), `analysis` "
                     "(signal/setup/indicators recomputed for that tick), `market` (indices/breadth), `universe` "
                     "(scanner universe rebuilt — re-run scans), and "
                     "`heartbeat`. Each payload has `_meta.receivedMs` (tick reached this server) and "
                     "`_meta.publishedMs`, so clients can measure delivery latency.")
async def stream(request: Request, symbols: Optional[str] = Query(None, description="Comma-separated codes")):
    wanted = parse_symbols(symbols, 50)
    await S.feed.wait_ready()
    sub = S.feed.subscribe(set(wanted) if wanted else None)

    def sse(event: str, data: Any, eid: Optional[int] = None) -> str:
        head = f"id: {eid}\n" if eid is not None else ""
        return f"{head}event: {event}\ndata: {json.dumps(data, separators=(',', ':'), default=str)}\n\n"

    async def gen():
        try:
            yield "retry: 3000\n\n"
            yield sse("snapshot", {"market": S.feed.market_summary(),
                                   "quotes": {s: S.feed.quotes.get(s) for s in (wanted or [])},
                                   "feed": S.feed.status()})
            for sym in wanted or []:      # first analysis right away, so the page is complete on connect
                try:
                    k, ind = await get_analysis(sym)
                    yield sse("analysis", report._clean(live_view(k, ind)))
                except scraper.ScrapeError as e:
                    yield sse("error", {"symbol": sym, "detail": str(e)})
            while not await request.is_disconnected():
                try:
                    ev = await asyncio.wait_for(sub.queue.get(), timeout=C.SSE_HEARTBEAT_S)
                    yield sse(ev["event"], ev["data"], ev["id"])
                except asyncio.TimeoutError:
                    yield sse("heartbeat", {"serverMs": int(time.time() * 1000), "feed": S.feed.status()})
        finally:
            S.feed.unsubscribe(sub)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


# =========================================================================== web view
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


app.mount("/static", StaticFiles(directory=WEB), name="static")
# plotly.js ships inside the plotly wheel: serve it locally, no CDN dependency
app.mount("/vendor", StaticFiles(directory=os.path.join(os.path.dirname(_plotly.__file__), "package_data")), name="vendor")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(os.path.join(WEB, "index.html"), headers={"Cache-Control": "no-cache"})
