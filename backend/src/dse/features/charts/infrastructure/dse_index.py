"""Candle source over the exchange's own index endpoints (dse.com.bd /api/live/index-history, index-intraday).

These carry one closing value per point and no open, high, low or volume, so the candles are `ohlc=False`.
Politeness is enforced here, once: one request at a time, spaced apart, an honest User-Agent, and every
raw response cached in Redis.

Labels are not timestamps: "18 Nov '25" (daily, with year), "18 Aug" (daily, no year), "11 Nov, 10:00"
(week, no year), and "10:00" with a `day` field (intraday). Times are Dhaka local time. A label without a
year takes the latest year that is not after the session date the response reports.
"""

import asyncio
import json
import re
import time
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx
from redis.asyncio import Redis

from dse.features.charts.domain.candles import Candles, aggregate
from dse.shared_kernel.errors import NotFoundError, UpstreamForbiddenError, UpstreamUnavailableError

BASE = "https://www.dse.com.bd"
DHAKA = timezone(timedelta(hours=6))  # no daylight saving
MONTHS = {
    m: i
    for i, m in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1
    )
}
_DAILY = re.compile(r"^(\d{1,2}) ([A-Za-z]{3})(?: '(\d{2}))?$")
_WEEK = re.compile(r"^(\d{1,2}) ([A-Za-z]{3}),? (\d{1,2}):(\d{2})$")
MINUTES = {"5": 5, "30": 30, "60": 60}
TTL_S = {"daily": 600, "week": 120, "today": 60}


def _session_date(payload: dict[str, Any]) -> date:
    s = payload.get("session") or {}
    raw = s.get("date") or payload.get("day")
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return datetime.now(DHAKA).date()


def _year_for(month: int, day: int, ref: date) -> int:
    return ref.year if (month, day) <= (ref.month, ref.day) else ref.year - 1


def parse_daily(payload: dict[str, Any]) -> list[tuple[int, float]]:
    """index-history with a range of a month or more: one close per trading day, placed at 00:00 UTC."""
    ref = _session_date(payload)
    out = []
    for p in payload.get("points") or []:
        m = _DAILY.match(str(p.get("t", "")).strip())
        v = p.get("value")
        if not m or not isinstance(v, int | float) or v <= 0:
            continue
        day, mon = int(m.group(1)), MONTHS.get(m.group(2).title())
        if mon is None:
            continue
        year = 2000 + int(m.group(3)) if m.group(3) else _year_for(mon, day, ref)
        out.append((int(datetime(year, mon, day, tzinfo=UTC).timestamp()), float(v)))
    return out


def parse_week(payload: dict[str, Any]) -> list[tuple[int, float]]:
    """index-history with range 1W: several values per day, labelled "11 Nov, 10:00" in Dhaka time."""
    ref = _session_date(payload)
    out = []
    for p in payload.get("points") or []:
        m = _WEEK.match(str(p.get("t", "")).strip())
        v = p.get("value")
        mon = MONTHS.get(m.group(2).title()) if m else None
        if not m or mon is None or not isinstance(v, int | float) or v <= 0:
            continue
        day = int(m.group(1))
        stamp = datetime(_year_for(mon, day, ref), mon, day, int(m.group(3)), int(m.group(4)), tzinfo=DHAKA)
        out.append((int(stamp.timestamp()), float(v)))
    return out


def parse_intraday(payload: dict[str, Any]) -> list[tuple[int, float]]:
    """index-intraday: today's values, labelled "10:00" with the date in `day`."""
    day = _session_date(payload)
    out = []
    for p in payload.get("points") or []:
        t, v = str(p.get("t", "")), p.get("value")
        if not re.fullmatch(r"\d{1,2}:\d{2}", t) or not isinstance(v, int | float) or v <= 0:
            continue
        hh, mm = t.split(":")
        out.append(
            (
                int(datetime(day.year, day.month, day.day, int(hh), int(mm), tzinfo=DHAKA).timestamp()),
                float(v),
            )
        )
    return out


class DseIndexCandles:
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
        self._lock = asyncio.Lock()
        self._last = 0.0
        self._interval = min_interval_s

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _json(self, path: str, ttl: int) -> dict[str, Any]:
        cached = await self._redis.get(f"dse-index:{path}")
        if cached is not None:
            data = json.loads(cached)
            return data if isinstance(data, dict) else {}
        async with self._lock:  # one request at a time, spaced out
            wait = self._interval - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                r = await self._client.get(BASE + path)
            except httpx.HTTPError as e:
                raise UpstreamUnavailableError(f"the exchange's index data is unreachable: {e}") from e
            finally:
                self._last = time.monotonic()
        if r.status_code == 403:
            raise UpstreamForbiddenError("the exchange answered 403 Forbidden for its index data")
        if r.status_code in (400, 404):
            raise NotFoundError("the exchange has no such index")
        if r.status_code != 200:
            raise UpstreamUnavailableError(f"the exchange's index data answered {r.status_code}")
        data = r.json()
        if not isinstance(data, dict) or data.get("error"):
            raise NotFoundError("the exchange has no such index")
        await self._redis.set(f"dse-index:{path}", json.dumps(data), ex=ttl)
        return data

    async def candles(self, symbol: str, resolution: str, pages: int) -> Candles:
        code = quote(symbol.upper())
        if resolution == "D":
            data = await self._json(f"/api/live/index-history?code={code}&range=1Y", TTL_S["daily"])
            return Candles.from_closes(parse_daily(data))
        if resolution == "1":
            data = await self._json(f"/api/live/index-intraday?code={code}", TTL_S["today"])
            return Candles.from_closes(parse_intraday(data))
        data = await self._json(f"/api/live/index-history?code={code}&range=1W", TTL_S["week"])
        return aggregate(Candles.from_closes(parse_week(data)), MINUTES[resolution])
