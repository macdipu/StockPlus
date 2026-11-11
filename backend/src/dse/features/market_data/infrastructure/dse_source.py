"""MarketDataSource adapter over HTTP. Politeness (spacing, single retry) is enforced here, once."""

import asyncio
import logging
import time

import httpx

from dse.features.market_data.domain.entities import CompanyPage, MarketSnapshot
from dse.features.market_data.infrastructure.dse_parser import parse_company_page, parse_snapshot
from dse.shared_kernel.clock import Clock
from dse.shared_kernel.errors import NotFoundError, UpstreamForbiddenError, UpstreamUnavailableError
from dse.shared_kernel.symbol import Symbol

log = logging.getLogger("dse.source")
FORBIDDEN = (
    "dse.com.bd answered 403 Forbidden: it refuses this client. Check DSE's terms of use, or ask the "
    "exchange for authorised data access."
)


class DseHttpSource:
    def __init__(
        self,
        base_url: str,
        clock: Clock,
        *,
        user_agent: str,
        timeout_s: float = 20.0,
        min_page_interval_s: float = 2.5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._clock = clock
        self._interval = min_page_interval_s
        self._client = client or httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )
        self._page_lock = asyncio.Lock()
        self._last_page = 0.0

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, url: str, **headers: str) -> httpx.Response:
        last: Exception | None = None
        for attempt in (1, 2):
            try:
                r = await self._client.get(url, headers=headers)
                if r.status_code < 500:
                    return r
                last = UpstreamUnavailableError(f"{r.status_code} from {url}")
            except httpx.HTTPError as e:
                last = e
            if attempt == 1:
                await asyncio.sleep(1.5)
        raise UpstreamUnavailableError(f"GET {url} failed twice: {last}")

    async def company_page(self, symbol: Symbol) -> CompanyPage:
        async with self._page_lock:  # one page load at a time, spaced out
            wait = self._interval - (time.monotonic() - self._last_page)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                r = await self._get(f"{self._base}/company/{symbol}")
            finally:
                self._last_page = time.monotonic()
        if r.status_code == 403:
            raise UpstreamForbiddenError(FORBIDDEN)
        if r.status_code == 404:
            raise NotFoundError(f"{symbol} is not a DSE trading code", symbol=str(symbol))
        if r.status_code != 200:
            raise UpstreamUnavailableError(f"company page for {symbol} answered {r.status_code}")
        return parse_company_page(r.text, symbol, self._clock.now())

    async def market_snapshot(self) -> MarketSnapshot:
        r = await self._get(f"{self._base}/api/live/snapshot", Accept="application/json")
        if r.status_code == 403:
            raise UpstreamForbiddenError(FORBIDDEN)
        if r.status_code != 200:
            raise UpstreamUnavailableError(f"snapshot answered {r.status_code}")
        return parse_snapshot(r.json())
