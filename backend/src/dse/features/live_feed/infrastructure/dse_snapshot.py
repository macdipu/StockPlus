"""SnapshotFeed adapter: DSE's /api/live/snapshot JSON → LiveSnapshot, with ETag conditional GETs.

The live view needs more than market_data's copy of the same endpoint (indices, breadth, movers, board,
percent), so this feature owns its own parser rather than reaching into another feature's infrastructure.
"""

from datetime import date, time
from typing import Any

import httpx

from dse.features.live_feed.domain.entities import (
    IndexLevel,
    LiveQuote,
    LiveSnapshot,
    MarketState,
    MarketSummary,
    SessionState,
)
from dse.features.live_feed.domain.ports import FetchResult
from dse.shared_kernel.errors import UpstreamForbiddenError, UpstreamUnavailableError
from dse.shared_kernel.symbol import Symbol

FORBIDDEN = (
    "dse.com.bd answered 403 Forbidden: it refuses this client. Check DSE's terms of use, or ask the "
    "exchange for authorised data access."
)


def _f(v: Any) -> float | None:
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def _day(v: Any) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _hhmm(v: Any) -> time | None:
    try:
        return time.fromisoformat(str(v)) if v else None
    except ValueError:
        return None


def parse_live_snapshot(obj: dict[str, Any]) -> LiveSnapshot:
    try:
        cols, rows = obj["prices"]["cols"], obj["prices"]["rows"]
    except (KeyError, TypeError) as e:
        raise UpstreamUnavailableError(f"snapshot shape changed: missing {e}") from e
    market = obj.get("market") or {}
    raw_session = market.get("session") or obj["prices"].get("session") or {}
    totals = dict(market.get("totals") or {})
    quotes: dict[str, LiveQuote] = {}
    for row in rows:
        q = dict(zip(cols, row, strict=False))
        try:
            sym = Symbol(str(q["code"]))
        except Exception:  # noqa: S112 — one malformed code must not drop the whole market
            continue
        quotes[sym.value] = LiveQuote(
            symbol=sym,
            ltp=_f(q.get("ltp")),
            ycp=_f(q.get("ycp")),
            open=_f(q.get("open")),
            high=_f(q.get("high")),
            low=_f(q.get("low")),
            close=_f(q.get("close")) or None,  # 0 while the session is open
            volume=int(q.get("volume") or 0),
            value_mn=_f(q.get("value")),
            trades=int(q["trades"]) if q.get("trades") is not None else None,
            percent=_f(q.get("percent")),
            category=q.get("category"),
            board=q.get("board"),
            sector=q.get("sector"),
            asset_type=q.get("assetType"),
        )
    session = SessionState(
        day=_day(raw_session.get("date")),
        is_open=bool(raw_session.get("isOpen")),
        trading_day=bool(raw_session.get("tradingDay")),
        phase=raw_session.get("phase"),
        opening=_hhmm(raw_session.get("opening")),
        closing=_hhmm(raw_session.get("closing")),
    )
    summary = MarketSummary(
        indices=tuple(
            IndexLevel(str(i.get("key")), _f(i.get("value")), _f(i.get("change")), _f(i.get("percent")))
            for i in market.get("indices") or []
            if isinstance(i, dict)
        ),
        totals={k: v for k, v in totals.items() if k != "tradeTime"},
        breadth=dict(market.get("breadth") or {}),
        movers=dict(market.get("movers") or {}),
    )
    return LiveSnapshot(MarketState(session, totals.get("tradeTime"), summary), quotes)


class DseSnapshotFeed:
    def __init__(
        self,
        base_url: str,
        *,
        user_agent: str,
        timeout_s: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ):
        self._url = base_url.rstrip("/") + "/api/live/snapshot"
        self._client = client or httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch(self, etag: str | None) -> FetchResult:
        headers = {"If-None-Match": etag} if etag else {}
        try:
            r = await self._client.get(self._url, headers=headers)
        except httpx.HTTPError as e:
            raise UpstreamUnavailableError(f"snapshot request failed: {type(e).__name__}: {e}") from e
        if r.status_code == 304:
            return FetchResult(None, etag)
        if r.status_code == 403:
            raise UpstreamForbiddenError(FORBIDDEN)
        if r.status_code != 200:
            raise UpstreamUnavailableError(f"snapshot answered {r.status_code}")
        try:
            body = r.json()
        except ValueError as e:
            raise UpstreamUnavailableError("snapshot is not JSON") from e
        return FetchResult(parse_live_snapshot(body), r.headers.get("etag"))
