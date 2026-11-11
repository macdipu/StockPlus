"""Market-wide endpoints: scanners, sectors, movers, P/E, 52-week, TA values, depth, VPA, intraday, tools, data.

The universe (one analysed row per instrument) is materialised by a single background worker, rebuilt once per
upstream tick (about once a minute while the market is open). Scans read the latest build, so they answer in
milliseconds and every caller sees the same, versioned picture.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import time
from typing import Any, Dict, List, Literal, Optional

import httpx
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import config as C
import scanner
import scraper
import store
import vpa

log = logging.getLogger("dse.market")
router = APIRouter(prefix="/api/v1")
DEPTH_URL = C.BASE_URL + "/api/live/depth?code={symbol}"
DEPTH_TTL_S = 5


# =========================================================================== universe worker
class Universe:
    def __init__(self, feed) -> None:
        self.feed = feed
        self.live: pd.DataFrame = pd.DataFrame()
        self.last_close: pd.DataFrame = pd.DataFrame()
        self.version = 0
        self.built_at_ms: Optional[int] = None
        self.build_ms: Optional[int] = None
        self.errors: dict = {}
        self._bars: dict = {}
        self._bars_sig: Optional[tuple] = None
        self._fund: dict = {}
        self._last_close_key: Optional[tuple] = None
        self._last_close_cache: pd.DataFrame = pd.DataFrame()
        self._lock = asyncio.Lock()
        self._pending = False
        self.on_built: list = []

    def _load_store(self) -> None:
        st = store.status()
        sig = (st["bars"], st["last_bar_date"], st["fundamentals"])
        if sig != self._bars_sig:
            self._bars, self._fund, self._bars_sig = store.all_bars(), store.all_fundamentals(), sig

    def _build(self) -> tuple:
        self._load_store()
        q, s = dict(self.feed.quotes), dict(self.feed.session)
        live = scanner.build_universe(self._bars, self._fund, q, s, live=True)
        # the last-completed-session universe only changes when stored history does: rebuild on that, not per tick
        key = (self._bars_sig, s.get("date"))
        if key != self._last_close_key:
            self._last_close_cache = scanner.build_universe(self._bars, self._fund, q, s, live=False)
            self._last_close_key = key
        return live, self._last_close_cache

    async def refresh(self) -> None:
        """Single-flight: concurrent triggers collapse into one extra rebuild."""
        if self._lock.locked():
            self._pending = True
            return
        async with self._lock:
            while True:
                self._pending = False
                t0 = time.perf_counter()
                live, last = await run_in_threadpool(self._build)
                self.live, self.last_close = live, last
                self.errors = {**live.attrs.get("errors", {})}
                self.version += 1
                self.built_at_ms, self.build_ms = int(time.time() * 1000), int((time.perf_counter() - t0) * 1000)
                log.info("universe v%d: %d rows in %d ms", self.version, len(live), self.build_ms)
                for hook in self.on_built:
                    hook(self)
                if not self._pending:
                    break

    def frame(self, live: bool = True) -> pd.DataFrame:
        u = self.live if live else self.last_close
        if u.empty:
            raise HTTPException(503, "Universe not built yet — run `python main.py sync` to backfill history")
        return u

    def status(self) -> dict:
        return {"version": self.version, "rows": len(self.live), "builtAtMs": self.built_at_ms,
                "buildMs": self.build_ms, "errors": len(self.errors), "store": store.status()}


def U(request: Request) -> Universe:
    return request.app.state.universe


def meta(request: Request, **kw) -> dict:
    u = U(request)
    return {"requestId": request.state.rid, "tradeTime": request.app.state.feed.trade_time,
            "universeVersion": u.version, "universeBuiltAtMs": u.built_at_ms, **kw}


def _csv_list(raw: Optional[str]) -> Optional[list]:
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else None


# =========================================================================== scanner
class Rule(BaseModel):
    field: str
    op: Literal["<", "<=", ">", ">=", "==", "!=", "between", "in", "not_in", "is_true", "is_false", "contains",
                "crosses_above", "crosses_below"]
    value: Any = None
    field2: Optional[str] = None


class UniverseFilter(BaseModel):
    sectors: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    assetTypes: Optional[List[str]] = Field(None, examples=[["EQ"]])
    min_value_mn: Optional[float] = Field(None, description="Minimum turnover today, BDT mn (liquidity filter)")


class Sort(BaseModel):
    field: str = "value_mn"
    desc: bool = True


class ScanRequest(BaseModel):
    rules: List[Rule] = Field(..., min_length=1, max_length=20)
    match: Literal["all", "any"] = "all"
    universe: Optional[UniverseFilter] = None
    sort: Optional[Sort] = None
    limit: int = Field(100, ge=1, le=500)
    columns: Optional[List[str]] = None
    live: bool = Field(True, description="false = evaluate the last completed session (pre-market scan)")

    model_config = {"json_schema_extra": {"examples": [{
        "rules": [{"field": "rsi14", "op": "between", "value": [50, 70]},
                  {"field": "close", "op": ">", "field2": "ema21"},
                  {"field": "vol_ratio", "op": ">=", "value": 1.5}],
        "match": "all", "universe": {"assetTypes": ["EQ"], "categories": ["A", "B"]},
        "sort": {"field": "vol_ratio", "desc": True}, "limit": 50}]}}


def _scan(request: Request, rules: list, match: str, universe: Optional[dict], sort: Optional[dict], limit: int,
          columns: Optional[list], live: bool) -> dict:
    u = U(request).frame(live)
    try:
        hits = scanner.run(u, rules, match, universe, sort, limit)
    except (scanner.ScanError, KeyError) as e:
        raise HTTPException(400, f"Invalid scan: {e}")
    return {"data": scanner.to_records(hits, columns), "meta": meta(request, matched=len(hits), scanned=len(u),
                                                                     live=live)}


@router.get("/scanner/presets", tags=["scanner"], summary="All preset scanners, grouped")
async def scanner_presets():
    return {"data": [{"key": k, **{x: v[x] for x in ("name", "group", "description", "premarket", "rules", "sort")}}
                     for k, v in scanner.PRESETS.items()]}


@router.get("/scanner/fields", tags=["scanner"], summary="Fields a custom scan can use")
async def scanner_fields():
    return {"data": scanner.FIELD_DOCS, "ops": sorted(Rule.model_fields["op"].annotation.__args__)}


@router.get("/scanner/presets/{key}", tags=["scanner"], summary="Run a preset scanner")
async def run_preset(request: Request, key: str, limit: int = Query(100, ge=1, le=500),
                     sectors: Optional[str] = None, categories: Optional[str] = None,
                     asset_types: Optional[str] = Query("EQ", alias="assetTypes"),
                     min_value_mn: Optional[float] = None, live: Optional[bool] = None, columns: Optional[str] = None):
    p = scanner.PRESETS.get(key)
    if not p:
        raise HTTPException(404, f"No preset '{key}'. See /api/v1/scanner/presets")
    uf = {"sectors": _csv_list(sectors), "categories": _csv_list(categories), "assetTypes": _csv_list(asset_types),
          "min_value_mn": min_value_mn}
    is_live = (not p["premarket"]) if live is None else live
    out = _scan(request, p["rules"], p["match"], uf, p["sort"], limit, _csv_list(columns), is_live)
    out["meta"]["preset"] = {"key": key, "name": p["name"], "description": p["description"]}
    return out


@router.post("/scanner/run", tags=["scanner"], summary="Run a custom scan (rule builder)")
async def run_custom(request: Request, body: ScanRequest):
    return _scan(request, [r.model_dump(exclude_none=True) for r in body.rules], body.match,
                 body.universe.model_dump() if body.universe else None,
                 body.sort.model_dump() if body.sort else None, body.limit, body.columns, body.live)


# =========================================================================== market analytics
@router.get("/market/sectors", tags=["market"], summary="Sector performance, breadth, turnover share, median P/E")
async def market_sectors(request: Request):
    return {"data": scanner.sectors(U(request).frame()), "meta": meta(request)}


@router.get("/market/movers", tags=["market"], summary="Top gainers / losers / most active (live)")
async def market_movers(request: Request, by: Literal["gainers", "losers", "value", "volume", "trades"] = "gainers",
                        limit: int = Query(20, ge=1, le=100), asset_types: str = Query("EQ", alias="assetTypes")):
    quotes = [q for q in request.app.state.feed.quotes.values()
              if q.get("assetType") in _csv_list(asset_types) and (q.get("volume") or 0) > 0]
    key = {"gainers": "percent", "losers": "percent", "value": "value", "volume": "volume", "trades": "trades"}[by]
    rows = sorted(quotes, key=lambda q: q.get(key) or 0, reverse=by != "losers")[:limit]
    return {"data": rows, "meta": meta(request, by=by)}


@router.get("/market/pe", tags=["market"], summary="Market, sector and category P/E (median and cap-weighted)")
async def market_pe(request: Request):
    return {"data": scanner.pe_summary(U(request).frame()), "meta": meta(request)}


@router.get("/market/52-week", tags=["market"], summary="Where every instrument sits in its 52-week range")
async def market_52w(request: Request, sort: Literal["near_high", "near_low"] = "near_high",
                     limit: int = Query(100, ge=1, le=500)):
    u = U(request).frame()
    u = u[u["assetType"] == "EQ"].copy()
    u["range_position_pct"] = (u["ltp"] - u["low_52w"]) / (u["high_52w"] - u["low_52w"]) * 100
    u = u.sort_values("range_position_pct", ascending=sort == "near_low").head(limit)
    return {"data": scanner.to_records(u, ["symbol", "sector", "ltp", "low_52w", "high_52w", "range_position_pct",
                                           "pct_from_52w_high", "pct_from_52w_low"]), "meta": meta(request)}


@router.get("/market/ta-values", tags=["market"], summary="Technical indicator values for every instrument")
async def ta_values(request: Request, sector: Optional[str] = None,
                    columns: str = "symbol,sector,ltp,change_pct,rsi14,macd,macd_signal,macd_hist,sma20,sma50,"
                                   "sma200,ema9,ema21,atr_pct,bb_width_pctile,vol_ratio,setup_score,vpa"):
    u = U(request).frame()
    if sector:
        u = u[u["sector"] == sector]
    return {"data": scanner.to_records(u.sort_values("symbol"), _csv_list(columns)), "meta": meta(request)}


@router.get("/market/data-matrix", tags=["market"], summary="Fundamentals + valuation table for every instrument")
async def data_matrix(request: Request, sector: Optional[str] = None):
    u = U(request).frame()
    if sector:
        u = u[u["sector"] == sector]
    cols = ["symbol", "name", "sector", "category", "ltp", "change_pct", "eps_ttm", "pe", "nav", "pb",
            "dividend_yield_pct", "sponsor_pct", "free_float_pct", "market_cap", "graham", "graham_gap_pct",
            "ret_1m", "ret_3m", "ret_1y"]
    return {"data": scanner.to_records(u.sort_values("symbol"), cols), "meta": meta(request)}


# =========================================================================== per-instrument extras
_depth_cache: Dict[str, tuple] = {}


@router.get("/stocks/{symbol}/depth", tags=["stocks"], summary="Top-10 bid/ask order book with spread & imbalance")
async def depth(request: Request, symbol: str):
    sym = scraper.normalize_symbol(symbol)
    hit = _depth_cache.get(sym)
    if not hit or time.monotonic() - hit[0] > DEPTH_TTL_S:
        async with httpx.AsyncClient(timeout=C.HTTP_TIMEOUT_S, headers={"User-Agent": C.USER_AGENT}) as cli:
            r = await cli.get(DEPTH_URL.format(symbol=sym))
        if r.status_code != 200:
            raise scraper.ScrapeError(f"depth answered {r.status_code}")
        hit = (time.monotonic(), r.json())
        _depth_cache[sym] = hit
    d = hit[1]
    bids, asks = d.get("bids") or [], d.get("asks") or []
    bq, aq = sum(b["quantity"] for b in bids), sum(a["quantity"] for a in asks)
    best_bid, best_ask = (bids[0]["price"] if bids else None), (asks[0]["price"] if asks else None)
    stats = {"bestBid": best_bid, "bestAsk": best_ask,
             "spread": round(best_ask - best_bid, 4) if best_bid and best_ask else None,
             "spreadPct": (best_ask / best_bid - 1) * 100 if best_bid and best_ask else None,
             "bidQty": bq, "askQty": aq, "imbalance": (bq - aq) / (bq + aq) if bq + aq else None}
    return {"data": {"symbol": sym, "bids": bids, "asks": asks, "stats": stats},
            "meta": {"requestId": request.state.rid, "source": DEPTH_URL.format(symbol=sym), "cacheTtlS": DEPTH_TTL_S}}


@router.get("/stocks/{symbol}/vpa", tags=["stocks"], summary="Daily volume-price analysis labels")
async def stock_vpa(request: Request, symbol: str, days: int = Query(60, ge=5, le=400)):
    sym = scraper.normalize_symbol(symbol)
    df = store.bars(sym)
    if df.empty:
        raise HTTPException(404, f"No stored bars for {sym} — run `python main.py sync`")
    df = scraper.merge_live(df, request.app.state.feed.quotes.get(sym), request.app.state.feed.session)
    v = vpa.classify(df).join(df[["open", "high", "low", "close", "volume"]]).iloc[-days:]
    rows = [{"date": i.strftime("%Y-%m-%d"), **{k: (None if pd.isna(x) else (round(x, 4) if isinstance(x, float) else x))
                                                for k, x in r.items()}} for i, r in v.iterrows()]
    return {"data": rows, "legend": {k: {"bias": b, "meaning": m} for k, (b, m) in vpa.LABELS.items()},
            "thresholds": vpa.VT, "meta": meta(request)}


@router.get("/stocks/{symbol}/intraday", tags=["stocks"], summary="1-minute bars + VPA from recorded live ticks")
async def stock_intraday(request: Request, symbol: str, day: Optional[str] = None):
    sym = scraper.normalize_symbol(symbol)
    m = await run_in_threadpool(store.minute_bars, sym, day)
    if m.empty:
        return {"data": [], "meta": meta(request, note="No ticks recorded for this day yet. Ticks are recorded "
                                                       "while the server runs; DSE publishes about once a minute.")}
    v = vpa.classify(m)
    rows = [{"time": i.strftime("%H:%M"), "open": r.open, "high": r.high, "low": r.low, "close": r.close,
             "volume": r.volume, "vpa": v.loc[i, "vpa"]} for i, r in m.iterrows()]
    return {"data": rows, "meta": meta(request)}


# =========================================================================== tools & data
@router.get("/tools/correlation", tags=["tools"], summary="Correlation of daily returns")
async def tool_correlation(request: Request, symbols: str, days: int = Query(120, ge=20, le=400)):
    syms = [scraper.normalize_symbol(s) for s in _csv_list(symbols) or []][:20]
    U(request)._load_store()
    return {"data": scanner.correlation(U(request)._bars, syms, days), "meta": meta(request)}


@router.get("/tools/return", tags=["tools"], summary="Price return between two dates")
async def tool_return(request: Request, symbol: str, buy_date: str, sell_date: Optional[str] = None,
                      quantity: float = Query(100, gt=0), fee_pct: float = Query(0.4, ge=0, le=5)):
    sym = scraper.normalize_symbol(symbol)
    df = scraper.merge_live(store.bars(sym, 2000), request.app.state.feed.quotes.get(sym),
                            request.app.state.feed.session)
    if df.empty:
        raise HTTPException(404, f"No stored bars for {sym}")
    b = df[df.index >= pd.Timestamp(buy_date)]
    s = df[df.index <= pd.Timestamp(sell_date)] if sell_date else df
    if b.empty or s.empty or s.index[-1] < b.index[0]:
        raise HTTPException(400, f"No bars between {buy_date} and {sell_date or 'today'} "
                                 f"(history {df.index[0]:%Y-%m-%d}…{df.index[-1]:%Y-%m-%d})")
    bp, sp = float(b["close"].iloc[0]), float(s["close"].iloc[-1])
    cost, proceeds = bp * quantity * (1 + fee_pct / 100), sp * quantity * (1 - fee_pct / 100)
    days = (s.index[-1] - b.index[0]).days
    return {"data": {"symbol": sym, "buyDate": f"{b.index[0]:%Y-%m-%d}", "buyPrice": bp,
                     "sellDate": f"{s.index[-1]:%Y-%m-%d}", "sellPrice": sp, "quantity": quantity, "feePct": fee_pct,
                     "cost": cost, "proceeds": proceeds, "profit": proceeds - cost,
                     "returnPct": (proceeds / cost - 1) * 100, "days": days,
                     "annualisedPct": ((proceeds / cost) ** (365 / days) - 1) * 100 if days > 0 else None,
                     "note": "Price return after round-trip fees; dividends not included."}, "meta": meta(request)}


@router.get("/data/{symbol}.csv", tags=["data"], summary="Download daily OHLCV as CSV")
async def data_csv(symbol: str):
    sym = scraper.normalize_symbol(symbol)
    df = store.bars(sym, 5000)
    if df.empty:
        raise HTTPException(404, f"No stored bars for {sym}")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "open", "high", "low", "close", "volume", "trades"])
    for i, r in df.iterrows():
        w.writerow([f"{i:%Y-%m-%d}", r.open, r.high, r.low, r.close, int(r.volume), int(r.trades or 0)])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{sym}.csv"'})


@router.get("/universe/status", tags=["ops"], summary="Universe build + store status")
async def universe_status(request: Request):
    return {"data": U(request).status()}
