"""DepthFeed adapter: DSE's /api/live/depth?code=SYMBOL JSON -> MarketDepth, with a short shared cache.

DSE itself serves this with a 10-15 s cache, so asking more often than that gains nothing. `CachedDepthFeed`
keeps the parsed answer in Redis for `ttl_s`, and one in-process lock per symbol collapses simultaneous
requests, so any number of viewers cost DSE about one request per share per `ttl_s` per API replica."""

import asyncio
import json
from typing import Any, Protocol, cast

import httpx
from redis.asyncio import Redis

from dse.features.live_feed.domain.depth import DepthLevel, MarketDepth
from dse.features.live_feed.infrastructure.dse_snapshot import FORBIDDEN
from dse.shared_kernel.errors import NotFoundError, UpstreamForbiddenError, UpstreamUnavailableError
from dse.shared_kernel.symbol import Symbol


def _levels(raw: Any, descending: bool) -> tuple[DepthLevel, ...]:
    out: list[DepthLevel] = []
    for r in raw if isinstance(raw, list) else []:
        try:
            out.append(DepthLevel(float(r["price"]), int(r["quantity"]), int(r.get("orders") or 0)))
        except (KeyError, TypeError, ValueError):
            continue  # one malformed level must not drop the book
    return tuple(sorted(out, key=lambda lv: lv.price, reverse=descending))


def parse_depth(obj: dict[str, Any], symbol: str) -> MarketDepth:
    if not isinstance(obj, dict) or "bids" not in obj or "asks" not in obj:
        raise UpstreamUnavailableError("depth shape changed: missing bids or asks")
    session = obj.get("session") or {}
    stats = obj.get("priceStats") or {}
    return MarketDepth(
        symbol=symbol,
        bids=_levels(obj["bids"], descending=True),
        asks=_levels(obj["asks"], descending=False),
        as_of=obj.get("asOf") if isinstance(obj.get("asOf"), str) else None,
        market_open=bool(session["isOpen"]) if "isOpen" in session else None,
        stats={k: v for k, v in stats.items() if isinstance(v, int | float | str) or v is None},
    )


class DseDepthFeed:
    def __init__(
        self,
        base_url: str,
        *,
        user_agent: str,
        timeout_s: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/api/live/depth"
        self._client = client or httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch(self, symbol: Symbol) -> MarketDepth:
        try:
            r = await self._client.get(self._url, params={"code": symbol.value})
        except httpx.HTTPError as e:
            raise UpstreamUnavailableError(f"depth request failed: {type(e).__name__}: {e}") from e
        if r.status_code == 403:
            raise UpstreamForbiddenError(FORBIDDEN)
        if r.status_code in (400, 404):
            raise NotFoundError(f"DSE has no market depth for '{symbol.value}'")
        if r.status_code != 200:
            raise UpstreamUnavailableError(f"depth answered {r.status_code}")
        try:
            body = r.json()
        except ValueError as e:
            raise UpstreamUnavailableError("depth is not JSON") from e
        return parse_depth(body, symbol.value)


class _Feed(Protocol):
    async def fetch(self, symbol: Symbol) -> MarketDepth: ...


def _encode(d: MarketDepth) -> str:
    return json.dumps(
        {
            "symbol": d.symbol,
            "bids": [[lv.price, lv.quantity, lv.orders] for lv in d.bids],
            "asks": [[lv.price, lv.quantity, lv.orders] for lv in d.asks],
            "as_of": d.as_of,
            "market_open": d.market_open,
            "stats": d.stats,
        },
        separators=(",", ":"),
    )


def _decode(raw: str) -> MarketDepth:
    o = json.loads(raw)
    return MarketDepth(
        symbol=o["symbol"],
        bids=tuple(DepthLevel(p, q, n) for p, q, n in o["bids"]),
        asks=tuple(DepthLevel(p, q, n) for p, q, n in o["asks"]),
        as_of=o["as_of"],
        market_open=o["market_open"],
        stats=o["stats"],
    )


class CachedDepthFeed:
    def __init__(self, inner: _Feed, redis: "Redis", ttl_s: int = 10) -> None:
        self._inner, self._redis, self._ttl = inner, redis, ttl_s
        self._locks: dict[str, asyncio.Lock] = {}

    async def fetch(self, symbol: Symbol) -> MarketDepth:
        key = f"depth:{symbol.value}"
        cached = cast(str | None, await self._redis.get(key))
        if cached:
            return _decode(cached)
        lock = self._locks.setdefault(symbol.value, asyncio.Lock())
        async with lock:  # simultaneous requests for one share share a single upstream call
            cached = cast(str | None, await self._redis.get(key))
            if cached:
                return _decode(cached)
            depth = await self._inner.fetch(symbol)
            await self._redis.set(key, _encode(depth), ex=self._ttl)
            return depth
