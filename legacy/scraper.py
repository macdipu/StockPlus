"""Data-source layer for www.dse.com.bd: HTTP fetch, payload parsing, per-day cache, normalisation.

Nothing in here knows about indicators or the API; it turns upstream bytes into plain dicts / DataFrames.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

import config as C


class ScrapeError(RuntimeError):
    """Upstream unreachable or its payload no longer matches config.py."""


class SymbolNotFound(ScrapeError):
    pass


class InvalidInput(ValueError):
    """Caller error (bad symbol, too many symbols). Kept distinct from pydantic's ValueError subclasses."""


TZ = ZoneInfo(C.TIMEZONE)
SYMBOL_RE = re.compile(r"^[A-Z0-9&().\-]{1,24}$")


def now() -> datetime:
    return datetime.now(TZ)


def today() -> str:
    return now().strftime("%Y-%m-%d")


def normalize_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if not SYMBOL_RE.match(s):
        raise InvalidInput(f"Invalid DSE trading code: {symbol!r}")
    return s


# --------------------------------------------------------------------------- HTTP
_HEADERS = {"User-Agent": C.USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
_page_lock = threading.Lock()
_last_page_at = 0.0


def _get(url: str, headers: Optional[dict] = None) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(C.HTTP_RETRIES + 1):
        try:
            r = httpx.get(url, headers={**_HEADERS, **(headers or {})}, timeout=C.HTTP_TIMEOUT_S,
                          follow_redirects=True)
            if r.status_code >= 500:
                raise httpx.HTTPStatusError(f"{r.status_code} from {url}", request=r.request, response=r)
            return r
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
            last = e
            if attempt < C.HTTP_RETRIES:
                time.sleep(1.5)
    raise ScrapeError(f"GET {url} failed after {C.HTTP_RETRIES + 1} attempts: {last}")


# --------------------------------------------------------------------------- flight payload
def _undefined_to_none(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _undefined_to_none(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_undefined_to_none(v) for v in o]
    return None if o == "$undefined" else o


def parse_flight(html: str) -> dict:
    """Extract {"company": {...}, "series": [...]} from the Next.js flight chunks in a company page."""
    chunks = re.findall(C.FLIGHT_PUSH_RE, html, flags=re.S)
    if not chunks:
        raise ScrapeError("No Next.js flight payload in the page — FLIGHT_PUSH_RE in config.py needs updating.")
    text = "".join(json.loads(f'"{c}"') for c in chunks)
    dec = json.JSONDecoder()
    out: dict[str, Any] = {}
    for key in (C.FLIGHT_COMPANY_KEY, C.FLIGHT_SERIES_KEY):
        m = re.search(rf'"{key}":\s*([\[{{])', text)
        if not m:
            continue
        out[key], _ = dec.raw_decode(text, m.start(1))
    return _undefined_to_none(out)


# --------------------------------------------------------------------------- cache
def _db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(C.CACHE_DB), exist_ok=True)
    con = sqlite3.connect(C.CACHE_DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS company_pages (symbol TEXT, day TEXT, fetched_at TEXT, payload TEXT,"
                " PRIMARY KEY (symbol, day))")
    return con


def cached_company(symbol: str) -> Optional[dict]:
    with _db() as con:
        row = con.execute("SELECT payload FROM company_pages WHERE symbol=? AND day=?", (symbol, today())).fetchone()
    return json.loads(row[0]) if row else None


def _cache_put(symbol: str, payload: dict) -> None:
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO company_pages VALUES (?,?,?,?)",
                    (symbol, today(), payload["fetched_at"], json.dumps(payload)))


# --------------------------------------------------------------------------- fetchers
def fetch_company(symbol: str, force: bool = False, dump: bool = False) -> dict:
    """Company page payload for today (cached per symbol per Dhaka day)."""
    global _last_page_at
    symbol = normalize_symbol(symbol)
    if not force:
        hit = cached_company(symbol)
        if hit:
            return hit
    with _page_lock:  # one page load at a time, spaced out
        wait = C.MIN_PAGE_INTERVAL_S - (time.monotonic() - _last_page_at)
        if wait > 0:
            time.sleep(wait)
        resp = _get(C.COMPANY_URL.format(symbol=symbol))
        _last_page_at = time.monotonic()
    if resp.status_code == 404:
        raise SymbolNotFound(f"{symbol} is not a DSE trading code")
    if resp.status_code != 200:
        raise ScrapeError(f"{resp.request.url} answered {resp.status_code}")
    data = parse_flight(resp.text)
    company = data.get(C.FLIGHT_COMPANY_KEY)
    if not company or not company.get("code"):
        raise SymbolNotFound(f"{symbol}: page has no company data (unknown or delisted code)")
    if not data.get(C.FLIGHT_SERIES_KEY):
        raise ScrapeError(f"{symbol}: page has no '{C.FLIGHT_SERIES_KEY}' array — update config.py")
    payload = {"symbol": symbol, "fetched_at": now().isoformat(timespec="seconds"),
               "source": str(resp.url), "company": company, "series": data[C.FLIGHT_SERIES_KEY]}
    if dump:
        os.makedirs(C.CAPTURE_DIR, exist_ok=True)
        path = os.path.join(C.CAPTURE_DIR, f"{symbol}_{now():%Y%m%d_%H%M%S}.json")
        with open(path, "w") as f:
            json.dump(payload, f, ensure_ascii=False)
        print(f"[{symbol}] payload saved -> {path} (company keys: {len(company)}, bars: {len(payload['series'])})")
    _cache_put(symbol, payload)
    return payload


def parse_snapshot(obj: dict) -> dict:
    """Snapshot JSON -> {"market": {...}, "session": {...}, "quotes": {CODE: {...}}}."""
    try:
        cols = obj[C.SNAPSHOT_PRICE_COLS_KEY[0]][C.SNAPSHOT_PRICE_COLS_KEY[1]]
        rows = obj[C.SNAPSHOT_PRICE_ROWS_KEY[0]][C.SNAPSHOT_PRICE_ROWS_KEY[1]]
    except (KeyError, TypeError) as e:
        raise ScrapeError(f"Snapshot shape changed ({e}) — update SNAPSHOT_* keys in config.py") from e
    market = obj.get("market") or {}
    trade_time = (market.get("totals") or {}).get("tradeTime")
    quotes = {}
    for row in rows:
        q = dict(zip(cols, row))
        code = q.pop("code")
        q["symbol"] = code
        q["close"] = q.get("close") or None          # 0 while the session is open
        q["change"] = round(q["ltp"] - q["ycp"], 4) if q.get("ltp") and q.get("ycp") else None
        q["tradeTime"] = trade_time
        quotes[code] = q
    session = market.get("session") or obj.get("prices", {}).get("session") or {}
    return {"market": market, "session": session, "quotes": quotes, "tradeTime": trade_time}


def fetch_snapshot() -> dict:
    r = _get(C.SNAPSHOT_URL, {"Accept": "application/json", "Referer": C.BASE_URL + "/"})
    if r.status_code != 200:
        raise ScrapeError(f"snapshot answered {r.status_code}")
    return parse_snapshot(r.json())


# --------------------------------------------------------------------------- shaping
def to_ohlcv(payload: dict, quote: Optional[dict] = None, session: Optional[dict] = None) -> pd.DataFrame:
    """Daily bars from the page, with today's live bar from the snapshot appended/refreshed."""
    f = C.SERIES_FIELDS
    rows = [{"date": b[f["date"]], "open": b[f["open"]], "high": b[f["high"]], "low": b[f["low"]],
             "close": b[f["close"]], "volume": b[f["volume"]], "trades": b.get(f["trades"])}
            for b in payload["series"]]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")].astype(float)

    return merge_live(df, quote, session)


def merge_live(df: pd.DataFrame, quote: Optional[dict], session: Optional[dict]) -> pd.DataFrame:
    """Append (or refresh) today's bar from a live snapshot quote. No-op if it has not traded today."""
    if not (quote and session and session.get("date") and (quote.get("volume") or 0) > 0 and quote.get("ltp")):
        return df
    day = pd.Timestamp(session["date"])
    if len(df) and day < df.index[-1]:
        return df
    df = df.copy()
    last = quote.get("close") or quote["ltp"]
    bar = {"open": quote.get("open") or last, "high": quote.get("high") or last, "low": quote.get("low") or last,
           "close": last, "volume": float(quote["volume"]), "trades": float(quote.get("trades") or 0)}
    df.loc[day, list(bar)] = list(bar.values())
    return df.sort_index()


def _interim_eps(company: dict) -> tuple[dict, dict]:
    inter = company.get("interimFinancials") or {}
    ends = inter.get("periodEnds") or {}
    rows = {r.get("metric"): r for r in inter.get("rows") or []}
    for name in C.EPS_METRICS:
        if name in rows:
            return rows[name], ends
    return {}, ends


def fundamentals(payload: dict, quote: Optional[dict] = None) -> dict:
    c = payload["company"]
    eps_row, ends = _interim_eps(c)
    multi = sorted(c.get("multiYearFinancials") or [], key=lambda r: r.get("year") or 0)
    pattern = (c.get("sharePattern") or [{}])[-1]
    shares_pat = pattern.get("pattern") or {}
    divs = sorted(c.get("dividendHistory") or [], key=lambda r: r.get("year") or 0)
    face = c.get("faceValue") or C.FACE_VALUE_DEFAULT

    out: dict[str, Any] = {
        "name": c.get("name"), "sector": c.get("sector"), "board": c.get("board"), "category": c.get("category"),
        "isin": c.get("isin"), "listing_year": c.get("listingYear"), "year_end": c.get("yearEnd"),
        "ltp": (quote or {}).get("ltp") or c.get("price"),
        "prev_close": (quote or {}).get("ycp") or c.get("prevClose"),
        "eps_annual": eps_row.get("annual"), "eps_q1": eps_row.get("q1"), "eps_q2": eps_row.get("q2"),
        "eps_q3": eps_row.get("q3"), "eps_half_year": eps_row.get("half"), "eps_nine_months": eps_row.get("nine"),
        "eps_last_audited_year": multi[-1].get("epsBasic") if multi else c.get("eps"),
        "nav": c.get("nav") or c.get("bookValue"),
        "face_value": face,
        "total_shares": int(c["paidUpCapital"] / face) if c.get("paidUpCapital") else None,
        "market_cap": c.get("marketCap"),
        "free_float_pct": c.get("freeFloat"),
        "sponsor_pct": shares_pat.get("sponsor"), "govt_pct": shares_pat.get("government"),
        "institute_pct": shares_pat.get("institution"), "foreign_pct": shares_pat.get("foreign"),
        "public_pct": shares_pat.get("public"), "share_pattern_date": pattern.get("date"),
        "pe_dse": c.get("pe"),
        "pe_dse_trailing": ((c.get("peUnauditedTable") or {}).get("trailing") or [None])[-1],
        "dividend_yield_pct": c.get("dividendYield"),
        "week_high_52": c.get("weekHigh52"), "week_low_52": c.get("weekLow52"),
        "agm_date": c.get("agmDate"), "loan_status": c.get("loanStatus"),
        "period_ends": ends,
        "dividend_history": divs[::-1],
        "multi_year": multi[::-1],
    }

    # TTM EPS: the annual figure if it is the newest report, else the newest YTD figure annualised.
    annual_end = ends.get("annual") or ""
    ytd = [("eps_nine_months", "nine", 4 / 3, "9M EPS × 4/3"), ("eps_half_year", "half", 2, "H1 EPS × 2"),
           ("eps_q1", "q1", 4, "Q1 EPS × 4")]
    newer = [(ends.get(p) or "", out[k], m, lbl) for k, p, m, lbl in ytd
             if out.get(k) is not None and (ends.get(p) or "") > annual_end]
    if newer:
        end, v, m, lbl = max(newer, key=lambda t: t[0])
        out["eps_ttm"], out["eps_ttm_basis"] = v * m, f"annualised {lbl} (period {end})"
    elif out["eps_annual"] is not None:
        out["eps_ttm"], out["eps_ttm_basis"] = out["eps_annual"], f"annual EPS (period {annual_end or '?'})"
    else:
        out["eps_ttm"], out["eps_ttm_basis"] = out["eps_last_audited_year"], "last audited year EPS"

    eps, ltp = out["eps_ttm"], out["ltp"]
    out["pe"] = ltp / eps if ltp and eps and eps > 0 else None
    last_div = divs[-1] if divs else None
    out["cash_dividend_pct"] = last_div.get("cash") if last_div else None
    out["stock_dividend_pct"] = last_div.get("stock") if last_div else None
    out["dps"] = (last_div.get("cash") or 0) / 100 * face if last_div else None
    out["last_dividend"] = (f"{last_div.get('cash') or 0:g}% cash (Tk {out['dps']:.2f}/sh), "
                            f"{last_div.get('stock') or 0:g}% stock — {last_div.get('year')}") if last_div else None
    return out


def news(payload: dict, limit: int = 20) -> list[dict]:
    return [{"id": n.get("id"), "date": n.get("date"), "type": n.get("type"), "title": n.get("summary"),
             "text": n.get("body") or ""}
            for n in (payload["company"].get("recentAnnouncements") or [])[:limit]]


def screenshot(symbol: str) -> Optional[str]:
    """Optional full-page screenshot (needs `pip install playwright && playwright install chromium`)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed — skipping screenshot")
        return None
    os.makedirs(C.SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(C.SCREENSHOT_DIR, f"{symbol}.png")
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(user_agent=C.USER_AGENT, viewport={"width": 1440, "height": 900})
            pg.goto(C.COMPANY_URL.format(symbol=symbol), wait_until="networkidle", timeout=60_000)
            pg.screenshot(path=path, full_page=True)
        finally:
            b.close()
    return path
