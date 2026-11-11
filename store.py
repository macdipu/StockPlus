"""Market-wide store (SQLite): daily bars + fundamentals for every instrument, recorded intraday ticks.

Populated by:
  * backfill()        one company page per symbol (sequential, polite, resumable) — history + fundamentals
  * append_eod()      after the close, today's bar for every symbol from ONE snapshot request
  * record_ticks()    every live snapshot change -> ticks table (feeds 1-minute bars / intraday VPA)
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import timedelta
from typing import Iterable, Optional

import pandas as pd

import config as C
import scraper

DB = os.getenv("DSE_STORE_DB", "cache/market.sqlite")
FUNDAMENTALS_MAX_AGE_DAYS = 7

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
  symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL, volume REAL, trades REAL,
  source TEXT NOT NULL, PRIMARY KEY (symbol, date));
CREATE TABLE IF NOT EXISTS fundamentals (
  symbol TEXT PRIMARY KEY, fetched_at TEXT NOT NULL, data TEXT NOT NULL, news TEXT);
CREATE TABLE IF NOT EXISTS ticks (
  symbol TEXT NOT NULL, ts INTEGER NOT NULL, trade_time TEXT, ltp REAL, high REAL, low REAL, volume REAL,
  value REAL, trades REAL, PRIMARY KEY (symbol, ts));
CREATE TABLE IF NOT EXISTS sync_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, finished_at TEXT, kind TEXT, ok INTEGER, failed INTEGER,
  detail TEXT);
CREATE INDEX IF NOT EXISTS ticks_ts ON ticks (ts);
"""


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


# --------------------------------------------------------------------------- writes
def save_company(payload: dict) -> int:
    """Persist one company page: all its daily bars + a normalised fundamentals record."""
    sym = payload["symbol"]
    f = C.SERIES_FIELDS
    rows = [(sym, b[f["date"]], b[f["open"]], b[f["high"]], b[f["low"]], b[f["close"]], b[f["volume"]],
             b.get(f["trades"]), "page") for b in payload["series"]]
    fund = scraper.fundamentals(payload)
    with connect() as con:
        con.executemany("INSERT INTO bars VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(symbol,date) DO UPDATE SET "
                        "open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, "
                        "volume=excluded.volume, trades=excluded.trades, source=excluded.source", rows)
        con.execute("INSERT OR REPLACE INTO fundamentals VALUES (?,?,?,?)",
                    (sym, payload["fetched_at"], json.dumps(fund, default=str), json.dumps(scraper.news(payload, 10))))
    return len(rows)


def append_eod(snapshot: Optional[dict] = None) -> int:
    """Write today's bar for every traded symbol from one snapshot (call after the close; safe to repeat)."""
    snap = snapshot or scraper.fetch_snapshot()
    day = snap["session"].get("date")
    if not day or not snap["session"].get("tradingDay"):
        return 0
    rows = []
    for sym, q in snap["quotes"].items():
        last = q.get("close") or q.get("ltp")
        if not last or not (q.get("volume") or 0):
            continue
        rows.append((sym, day, q.get("open") or last, q.get("high") or last, q.get("low") or last, last,
                     q["volume"], q.get("trades"), "snapshot"))
    with connect() as con:
        # never overwrite a bar that came from the official page
        con.executemany("INSERT INTO bars VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(symbol,date) DO UPDATE SET "
                        "open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, "
                        "volume=excluded.volume, trades=excluded.trades, source=excluded.source "
                        "WHERE bars.source <> 'page'", rows)
    return len(rows)


def record_ticks(quotes: Iterable[dict], ts_ms: int, trade_time: Optional[str]) -> None:
    rows = [(q["symbol"], ts_ms, trade_time, q.get("ltp"), q.get("high"), q.get("low"), q.get("volume"),
             q.get("value"), q.get("trades")) for q in quotes]
    if rows:
        with connect() as con:
            con.executemany("INSERT OR IGNORE INTO ticks VALUES (?,?,?,?,?,?,?,?,?)", rows)


def backfill(symbols: Optional[list] = None, force: bool = False, progress=print) -> dict:
    """Load each symbol's company page once (cached per day), sequentially. Resumable: skips fresh symbols."""
    started = scraper.now().isoformat(timespec="seconds")
    if symbols is None:
        symbols = sorted(scraper.fetch_snapshot()["quotes"])
    fresh = set()
    if not force:
        cutoff = (scraper.now() - timedelta(days=FUNDAMENTALS_MAX_AGE_DAYS)).isoformat()
        with connect() as con:
            fresh = {r[0] for r in con.execute("SELECT symbol FROM fundamentals WHERE fetched_at >= ?", (cutoff,))}
    todo = [s for s in symbols if s not in fresh]
    ok, failed = 0, []
    t0 = time.monotonic()
    for i, sym in enumerate(todo, 1):
        try:
            save_company(scraper.fetch_company(sym))   # fetch_company spaces requests (MIN_PAGE_INTERVAL_S)
            ok += 1
        except scraper.ScrapeError as e:
            failed.append(f"{sym}: {e}")
        if progress and (i % 25 == 0 or i == len(todo)):
            eta = (time.monotonic() - t0) / i * (len(todo) - i)
            progress(f"backfill {i}/{len(todo)} ok={ok} failed={len(failed)} eta={eta / 60:.1f} min")
    with connect() as con:
        con.execute("INSERT INTO sync_log (started_at, finished_at, kind, ok, failed, detail) VALUES (?,?,?,?,?,?)",
                    (started, scraper.now().isoformat(timespec="seconds"), "backfill", ok, len(failed),
                     json.dumps(failed[:50])))
    return {"requested": len(symbols), "skipped_fresh": len(symbols) - len(todo), "ok": ok, "failed": failed}


# --------------------------------------------------------------------------- reads
def bars(symbol: str, limit: int = 400) -> pd.DataFrame:
    with connect() as con:
        df = pd.read_sql_query("SELECT date, open, high, low, close, volume, trades FROM bars WHERE symbol=? "
                               "ORDER BY date DESC LIMIT ?", con, params=(symbol, limit))
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index().astype(float)


def all_bars(min_bars: int = 60, limit: int = 300) -> dict:
    """{symbol: DataFrame} for every symbol with enough history (one query)."""
    with connect() as con:
        df = pd.read_sql_query("SELECT symbol, date, open, high, low, close, volume, trades FROM bars "
                               "ORDER BY symbol, date", con)
    out = {}
    if df.empty:
        return out
    df["date"] = pd.to_datetime(df["date"])
    for sym, g in df.groupby("symbol", sort=False):
        if len(g) >= min_bars:
            out[sym] = g.drop(columns="symbol").set_index("date").iloc[-limit:].astype(float)
    return out


def all_fundamentals() -> dict:
    with connect() as con:
        return {s: json.loads(d) for s, d in con.execute("SELECT symbol, data FROM fundamentals")}


def fundamentals_of(symbol: str) -> Optional[dict]:
    with connect() as con:
        row = con.execute("SELECT data FROM fundamentals WHERE symbol=?", (symbol,)).fetchone()
    return json.loads(row[0]) if row else None


def minute_bars(symbol: str, day: Optional[str] = None) -> pd.DataFrame:
    """1-minute OHLCV built from recorded ticks (only exists from when the server started recording)."""
    day = day or scraper.today()
    start = int(pd.Timestamp(day, tz=C.TIMEZONE).timestamp() * 1000)
    with connect() as con:
        t = pd.read_sql_query("SELECT ts, ltp, volume, value FROM ticks WHERE symbol=? AND ts>=? AND ts<? ORDER BY ts",
                              con, params=(symbol, start, start + 86_400_000))
    if t.empty:
        return t
    t["time"] = pd.to_datetime(t["ts"], unit="ms", utc=True).dt.tz_convert(C.TIMEZONE).dt.floor("min")
    t["dvol"] = t["volume"].diff().fillna(t["volume"]).clip(lower=0)   # snapshot volume is cumulative
    g = t.groupby("time")
    return pd.DataFrame({"open": g["ltp"].first(), "high": g["ltp"].max(), "low": g["ltp"].min(),
                         "close": g["ltp"].last(), "volume": g["dvol"].sum()})


def status() -> dict:
    with connect() as con:
        n_sym, n_bars, last = con.execute("SELECT COUNT(DISTINCT symbol), COUNT(*), MAX(date) FROM bars").fetchone()
        n_f = con.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0]
        n_t, last_t = con.execute("SELECT COUNT(*), MAX(ts) FROM ticks").fetchone()
        log = con.execute("SELECT kind, started_at, finished_at, ok, failed FROM sync_log ORDER BY id DESC LIMIT 1"
                          ).fetchone()
    return {"symbols_with_bars": n_sym, "bars": n_bars, "last_bar_date": last, "fundamentals": n_f,
            "ticks": n_t, "last_tick_ms": last_t,
            "last_sync": dict(zip(("kind", "started_at", "finished_at", "ok", "failed"), log)) if log else None}
