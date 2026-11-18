"""HTTP adapters for the company sources and intraday bars.

Politeness is enforced here, once: one request at a time per host, spaced `min_interval_s` apart, an honest
User-Agent, and every raw response cached in Redis (dossier sources for hours, bars for a minute), so a busy
page never turns into a burst against someone else's site. Check each site's terms before relying on it.
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote

import httpx
from redis.asyncio import Redis

from dse.features.company.domain.entities import AmarStockPart, StockNowPart, TopStockPart
from dse.features.company.infrastructure.parsers import (
    STOCKNOW_KEYS,
    flight_objects,
    parse_amarstock,
    parse_stocknow,
    parse_topstock,
)
from dse.shared_kernel.errors import NotFoundError, UpstreamForbiddenError, UpstreamUnavailableError

STOCKNOW = "https://stocknow.com.bd"
AMARSTOCK = "https://www.amarstock.com"
TOPSTOCK = "https://www.topstockbd.com"
TOPSTOCK_KEYS = ("extFinancials", "financials", "rating", "declaration")
SOURCE_TTL_S = 6 * 3600
BARS_TTL_S = {"1": 60, "5": 120, "30": 300, "60": 300, "D": 600}
STOCKNOW_RES = {"1": "1", "5": "5", "30": "30", "60": "60", "D": "1D"}


class _Host:
    def __init__(self, min_interval_s: float) -> None:
        self.lock = asyncio.Lock()
        self.last = 0.0
        self.interval = min_interval_s


class HttpCompanySources:
    def __init__(
        self,
        redis: "Redis",
        *,
        user_agent: str,
        timeout_s: float = 20.0,
        min_interval_s: float = 1.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._redis = redis
        self._client = client or httpx.AsyncClient(
            timeout=timeout_s, follow_redirects=True, headers={"User-Agent": user_agent}
        )
        self._hosts = {h: _Host(min_interval_s) for h in (STOCKNOW, AMARSTOCK, TOPSTOCK)}

    async def aclose(self) -> None:
        await self._client.aclose()

    def url(self, source: str, symbol: str) -> str:
        s = quote(symbol)
        return {
            "stocknow": f"{STOCKNOW}/stocks/{s}",
            "amarstock": f"{AMARSTOCK}/stock/{s}",
            "topstock": f"{TOPSTOCK}/stock/{s}",
        }[source]

    # ---------------------------------------------------------------------------------------- transport
    async def _get(self, host: str, path: str) -> httpx.Response:
        h = self._hosts[host]
        async with h.lock:
            wait = h.interval - (time.monotonic() - h.last)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                r = await self._client.get(host + path)
            except httpx.HTTPError as e:
                raise UpstreamUnavailableError(f"{host} unreachable: {e}") from e
            finally:
                h.last = time.monotonic()
        if r.status_code == 403:
            raise UpstreamForbiddenError(f"{host} answered 403 Forbidden")
        if r.status_code == 404:
            raise NotFoundError(f"{host} has no page for this symbol")
        if r.status_code != 200:
            raise UpstreamUnavailableError(f"{host}{path} answered {r.status_code}")
        return r

    async def _cached(self, key: str, ttl: int, refresh: bool, load: Callable[[], Awaitable[str]]) -> str:
        if not refresh:
            hit = await self._redis.get(key)
            if hit is not None:
                return str(hit)
        text = await load()
        await self._redis.set(key, text, ex=ttl)
        return text

    # ---------------------------------------------------------------------------------------- sources
    async def stocknow(self, symbol: str, refresh: bool = False) -> StockNowPart:
        s = quote(symbol)

        async def fundamentals() -> str:
            path = (
                f"/api/v1/instruments/{s}/fundamentals/{','.join(STOCKNOW_KEYS)}"
                "?groupBy=meta_date,meta_key&yearLimit=10"
            )
            return (await self._get(STOCKNOW, path)).text

        async def news() -> str:
            r = await self._get(STOCKNOW, f"/api/v1/instruments/{s}/news")
            data = r.json()
            items = data.get("data") if isinstance(data, dict) else None
            return json.dumps({"data": (items or [])[:20]})

        raw = await self._cached(f"company:stocknow:{symbol}", SOURCE_TTL_S, refresh, fundamentals)
        try:
            raw_news = await self._cached(f"company:stocknow-news:{symbol}", SOURCE_TTL_S, refresh, news)
        except UpstreamUnavailableError:
            raw_news = '{"data": []}'
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not payload:
            raise NotFoundError(f"stocknow has no fundamentals for {symbol}")
        return await asyncio.to_thread(parse_stocknow, payload, json.loads(raw_news))

    async def amarstock(self, symbol: str, refresh: bool = False) -> AmarStockPart:
        async def page() -> str:
            return (await self._get(AMARSTOCK, f"/stock/{quote(symbol)}")).text

        html = await self._cached(f"company:amarstock:{symbol}", SOURCE_TTL_S, refresh, page)
        return await asyncio.to_thread(parse_amarstock, html)  # HTML parsing is CPU work: off the loop

    async def topstock(self, symbol: str, refresh: bool = False) -> TopStockPart:
        async def page() -> str:
            html = (await self._get(TOPSTOCK, f"/stock/{quote(symbol)}")).text
            # keep only the objects we read: the page is ~0.5 MB
            return json.dumps(flight_objects(html, TOPSTOCK_KEYS))

        raw = await self._cached(f"company:topstock:{symbol}", SOURCE_TTL_S, refresh, page)
        return await asyncio.to_thread(parse_topstock, _as_flight_html(json.loads(raw)))

    # ---------------------------------------------------------------------------------------- bars
    async def bars(self, symbol: str, resolution: str, pages: int) -> list[dict[str, Any]]:
        res = STOCKNOW_RES[resolution]
        out: dict[int, dict[str, Any]] = {}
        for page in range(pages):
            skip = page * 300

            async def load(skip: int = skip) -> str:
                path = f"/api/v1/instruments/{quote(symbol)}/history?data2=true&resolution={res}&skip={skip}"
                return (await self._get(STOCKNOW, path)).text

            raw = await self._cached(
                f"bars:{symbol}:{resolution}:{skip}", BARS_TTL_S[resolution], False, load
            )
            rows = parse_bars(json.loads(raw))
            for b in rows:
                out[b["time"]] = b
            if len(rows) < 300:
                break
        return [out[t] for t in sorted(out)]


def parse_bars(data: Any) -> list[dict[str, Any]]:
    """stocknow history arrays [opens, highs, lows, closes, volumes, unix times] → bar dicts."""
    if not isinstance(data, list) or len(data) < 6:
        raise UpstreamUnavailableError("stocknow history shape changed")
    o, h, lo, c, v, t = data[:6]
    bars = []
    for i in range(min(len(o), len(h), len(lo), len(c), len(v), len(t))):
        if None in (o[i], h[i], lo[i], c[i], t[i]):
            continue
        bars.append(
            {
                "time": int(t[i]),
                "open": float(o[i]),
                "high": float(h[i]),
                "low": float(lo[i]),
                "close": float(c[i]),
                "volume": int(v[i] or 0),
            }
        )
    return bars


def _as_flight_html(objects: dict[str, Any]) -> str:
    """Re-wrap cached objects so `parse_topstock` reads them exactly as it reads the live page."""
    body = json.dumps(objects)
    return f"<script>self.__next_f.push([1,{json.dumps(body)}])</script>"
