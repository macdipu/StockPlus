"""Analysis service: page payload + live quote -> one knowledge dict. Pure (no I/O) except `get_analysis`."""
from __future__ import annotations

from typing import Optional

import pandas as pd

import config as C
import indicators
import patterns
import report
import scraper
import setup_score
import signals
import valuation

INDICATOR_COLS = ["sma20", "sma50", "sma200", "ema9", "ema21", "rsi14", "macd", "macd_signal", "macd_hist",
                  "bb_upper", "bb_mid", "bb_lower", "atr14", "vol_avg20", "vol_ratio"]
MIN_BARS = 60


def _f(v) -> Optional[float]:
    return None if v is None or pd.isna(v) else float(v)


def build(payload: dict, quote: Optional[dict] = None, session: Optional[dict] = None):
    """Return (knowledge dict, indicator DataFrame)."""
    symbol = payload["symbol"]
    df = scraper.to_ohlcv(payload, quote, session)
    if len(df) < MIN_BARS:
        raise scraper.ScrapeError(f"{symbol}: only {len(df)} daily bars — too few to analyse.")
    fund = scraper.fundamentals(payload, quote)
    cat = fund.get("category")
    ind = indicators.add_indicators(df)
    pats = patterns.scan(ind)
    # DSE's own 52-week figures win over the ones computed from bars
    sr = indicators.support_resistance(ind, hi52=fund.get("week_high_52"), lo52=fund.get("week_low_52"))
    crit = setup_score.criteria_frame(ind, cat)
    setup = setup_score.score(ind, cat, sr, crit)
    sig = signals.signal(ind, setup, pats, cat)
    prob = signals.profit_probability(ind, crit, setup)

    last = ind.iloc[-1]
    ltp = fund.get("ltp") or float(last["close"])
    prev_close = fund.get("prev_close") or float(ind["close"].iloc[-2])
    live = bool(quote and session and session.get("date") == ind.index[-1].strftime("%Y-%m-%d"))
    k = {
        "symbol": symbol,
        "name": fund.get("name"),
        "as_of": (quote or {}).get("tradeTime") or payload["fetched_at"],
        "source": payload.get("source") or C.COMPANY_URL.format(symbol=symbol),
        "disclaimer": report.DISCLAIMER,
        "price": {"ltp": ltp, "prev_close": prev_close, "change": ltp - prev_close if prev_close else None,
                  "change_pct": (ltp / prev_close - 1) * 100 if prev_close else None,
                  "open": float(last["open"]), "high": float(last["high"]), "low": float(last["low"]),
                  "volume": float(last["volume"]), "trades": _f(last.get("trades")),
                  "value_mn": (quote or {}).get("value"), "live_bar": live,
                  "market_open": bool((session or {}).get("isOpen")),
                  "last_bar_date": ind.index[-1].strftime("%Y-%m-%d"),
                  "first_bar_date": ind.index[0].strftime("%Y-%m-%d"), "bars_available": len(ind)},
        "fundamentals": fund,
        "indicators": {c: _f(last[c]) for c in INDICATOR_COLS},
        "candles": {"last_candle": patterns.describe_last_candle(ind), "patterns": pats, "thresholds": patterns.T,
                    "last_sessions": [{"date": d.strftime("%Y-%m-%d"),
                                       **{c: float(r[c]) for c in ("open", "high", "low", "close", "volume")}}
                                      for d, r in ind.iloc[-10:].iterrows()]},
        "levels": sr,
        "trend": indicators.trend(ind),
        "valuation": valuation.value(fund),
        "setup": setup,
        "signal": sig,
        "probability": prob,
        "news": scraper.news(payload),
    }
    k["summary"] = report.summarize(k)
    return k, ind


def candles(ind: pd.DataFrame, limit: Optional[int] = None) -> list[dict]:
    d = ind if not limit else ind.iloc[-limit:]
    cols = ["open", "high", "low", "close", "volume", "sma20", "sma50", "sma200", "ema9", "ema21",
            "bb_upper", "bb_lower", "vol_avg20"]
    return [{"date": idx.strftime("%Y-%m-%d"), **{c: _f(r[c]) for c in cols}} for idx, r in d.iterrows()]


def get_analysis(symbol: str, force: bool = False, live: bool = True, dump: bool = False):
    """Convenience for scripts / agents: fetch (cached) page + current snapshot, then build."""
    payload = scraper.fetch_company(symbol, force=force, dump=dump)
    quote = session = None
    if live:
        try:
            snap = scraper.fetch_snapshot()
            quote, session = snap["quotes"].get(payload["symbol"]), snap["session"]
        except scraper.ScrapeError as e:
            print(f"[{payload['symbol']}] live snapshot unavailable ({e}); using page data only")
    return build(payload, quote, session)
