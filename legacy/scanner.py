"""Market-wide scanner.

1. `build_universe()` turns stored daily bars + fundamentals + live quotes into ONE DataFrame, a row per
   instrument, with every scannable field (indicators, previous-bar values for crosses, 52-week stats, returns,
   candle patterns, VPA label, setup score, valuation ratios).
2. A scan is declarative: rules + match mode + universe filter + sort. Presets are named rule sets, so custom
   scans and presets run through the same engine and are equally explainable.

Rule shapes
  {"field": "rsi14", "op": "<", "value": 30}
  {"field": "close", "op": ">", "field2": "sma50"}              compare two fields
  {"field": "sma50", "op": "crosses_above", "field2": "sma200"}   uses <field>_prev columns
  {"field": "rsi14", "op": "between", "value": [50, 70]}
  {"field": "category", "op": "in", "value": ["A", "B"]}
  {"field": "bullish_pattern", "op": "is_true"}
"""
from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
import pandas as pd

import indicators
import patterns
import scraper
import setup_score
import vpa

CROSS_FIELDS = ["close", "sma20", "sma50", "sma200", "ema9", "ema21", "macd", "macd_signal", "rsi14"]


# =========================================================================== universe
def _row(sym: str, df: pd.DataFrame, fund: dict, quote: Optional[dict]) -> dict:
    ind = indicators.add_indicators(df)
    last, prev = ind.iloc[-1], ind.iloc[-2]
    c = float(last["close"])
    yr = ind[ind.index > ind.index[-1] - pd.Timedelta(days=365)]
    hi52 = max(float(fund.get("week_high_52") or yr["high"].max()), float(last["high"]))
    lo52 = min(float(fund.get("week_low_52") or yr["low"].min()), float(last["low"]))
    prev_hi52 = float(yr["high"].iloc[:-1].max()) if len(yr) > 1 else hi52
    bbw = (ind["bb_upper"] - ind["bb_lower"]) / ind["bb_mid"]
    bbw_tail = bbw.iloc[-120:].dropna()
    pats = [n for n, _ in patterns.detect_at(ind, len(ind) - 1)]
    dirs = {d for _, d in patterns.detect_at(ind, len(ind) - 1)}
    v = vpa.classify(ind).iloc[-1]
    rng7 = (ind["high"] - ind["low"]).iloc[-7:]
    crit = setup_score.criteria_frame(ind.iloc[-3:], fund.get("category")).iloc[-1]

    def ret(days):
        past = ind["close"][ind.index <= ind.index[-1] - pd.Timedelta(days=days)]
        return (c / float(past.iloc[-1]) - 1) * 100 if len(past) else None

    eps, nav, ltp = fund.get("eps_ttm"), fund.get("nav"), (quote or {}).get("ltp") or c
    graham = math.sqrt(22.5 * eps * nav) if eps and nav and eps > 0 and nav > 0 else None
    row = {
        "symbol": sym, "name": fund.get("name"), "sector": (quote or {}).get("sector") or fund.get("sector"),
        "category": (quote or {}).get("category") or fund.get("category"), "assetType": (quote or {}).get("assetType"),
        "ltp": ltp, "ycp": (quote or {}).get("ycp") or float(prev["close"]),
        "change_pct": (quote or {}).get("percent") if quote else (c / float(prev["close"]) - 1) * 100,
        "open": float(last["open"]), "high": float(last["high"]), "low": float(last["low"]), "close": c,
        "volume": float(last["volume"]), "value_mn": (quote or {}).get("value"), "trades": (quote or {}).get("trades"),
        "bar_date": ind.index[-1].strftime("%Y-%m-%d"), "bars": len(ind),
        "high_52w": hi52, "low_52w": lo52,
        "pct_from_52w_high": (c / hi52 - 1) * 100, "pct_from_52w_low": (c / lo52 - 1) * 100,
        "new_52w_high": float(last["high"]) >= prev_hi52,
        "breakout_20d": c > float(ind["high"].iloc[-21:-1].max()),
        "breakdown_20d": c < float(ind["low"].iloc[-21:-1].min()),
        "gap_up_pct": (float(last["open"]) / float(prev["high"]) - 1) * 100,
        "gap_down_pct": (float(last["open"]) / float(prev["low"]) - 1) * 100,
        "nr7": float(rng7.iloc[-1]) <= float(rng7.min()) and len(rng7) == 7,
        "inside_bar": float(last["high"]) <= float(prev["high"]) and float(last["low"]) >= float(prev["low"]),
        "bb_width": float(bbw.iloc[-1]) if pd.notna(bbw.iloc[-1]) else None,
        "bb_width_pctile": float((bbw_tail <= bbw_tail.iloc[-1]).mean() * 100) if len(bbw_tail) > 20 else None,
        "atr_pct": float(last["atr14"]) / c * 100 if pd.notna(last["atr14"]) else None,
        "ret_1w": ret(7), "ret_1m": ret(30), "ret_3m": ret(91), "ret_6m": ret(182), "ret_1y": ret(365),
        "patterns": pats, "bullish_pattern": "bullish" in dirs, "bearish_pattern": "bearish" in dirs,
        "vpa": v["vpa"], "vpa_bias": v["vpa_bias"], "vol_rel": None if pd.isna(v["vol_rel"]) else float(v["vol_rel"]),
        "setup_score": int(sum(bool(crit[k]) for k in setup_score.CRITERIA)),
        "eps_ttm": eps, "nav": nav, "pe": ltp / eps if eps and eps > 0 else None,
        "pb": ltp / nav if nav and nav > 0 else None, "dividend_yield_pct": fund.get("dividend_yield_pct"),
        "sponsor_pct": fund.get("sponsor_pct"), "free_float_pct": fund.get("free_float_pct"),
        "market_cap": fund.get("market_cap"), "graham": graham,
        "graham_gap_pct": (graham / ltp - 1) * 100 if graham else None,
    }
    for col in ("sma20", "sma50", "sma200", "ema9", "ema21", "rsi14", "macd", "macd_signal", "macd_hist",
                "bb_upper", "bb_mid", "bb_lower", "atr14", "vol_avg20", "vol_ratio"):
        row[col] = None if pd.isna(last[col]) else float(last[col])
    for col in CROSS_FIELDS:
        row[f"{col}_prev"] = None if pd.isna(prev[col]) else float(prev[col])
    return row


def build_universe(bars: dict, fundamentals: dict, quotes: dict, session: dict, live: bool = True
                   ) -> pd.DataFrame:
    """One row per instrument. live=False scans the last completed session (pre-market scanner)."""
    rows, errors = [], {}
    for sym, df in bars.items():
        q = quotes.get(sym) if live else None
        try:
            d = scraper.merge_live(df, q, session) if live else df[df.index < pd.Timestamp(session.get("date") or
                                                                                           "2100-01-01")]
            if len(d) >= 30:
                rows.append(_row(sym, d, fundamentals.get(sym) or {}, q))
        except Exception as e:  # one bad series must not sink the scan; report it instead
            errors[sym] = f"{type(e).__name__}: {e}"
    u = pd.DataFrame(rows)
    if not u.empty:
        u = u.set_index("symbol", drop=False)
        u.index.name = None   # keep 'symbol' unambiguous as a column (sort/filter by it)
    u.attrs["errors"] = errors
    return u


# =========================================================================== rules
OPS = {"<": np.less, "<=": np.less_equal, ">": np.greater, ">=": np.greater_equal,
       "==": np.equal, "!=": np.not_equal}


class ScanError(ValueError):
    pass


def _col(u: pd.DataFrame, name: str) -> pd.Series:
    if name not in u.columns:
        raise ScanError(f"Unknown field '{name}'. See GET /api/v1/scanner/fields")
    return u[name]


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def evaluate(u: pd.DataFrame, rule: dict) -> pd.Series:
    field, op = rule.get("field"), rule.get("op")
    a = _col(u, field)
    if op in OPS:
        b = _num(_col(u, rule["field2"])) if "field2" in rule else rule.get("value")
        if b is None:
            raise ScanError(f"Rule on '{field}' needs 'value' or 'field2'")
        if isinstance(b, str):            # text fields (sector, vpa_bias, …): compare as text, never coerce
            if op not in ("==", "!="):
                raise ScanError(f"'{op}' needs a number; use == / != / in for text")
            m = a == b
            return (m if op == "==" else ~m).fillna(False)
        return pd.Series(OPS[op](_num(a), b), index=u.index).fillna(False).astype(bool)
    if op == "between":
        lo, hi = rule["value"]
        return _num(a).between(lo, hi).fillna(False)
    if op in ("in", "not_in"):
        m = a.isin(rule["value"])
        return m if op == "in" else ~m
    if op == "is_true":
        return a.fillna(False).astype(bool)
    if op == "is_false":
        return ~a.fillna(False).astype(bool)
    if op == "contains":   # list fields, e.g. patterns contains "Hammer"
        return a.apply(lambda x: rule["value"] in (x or []))
    if op in ("crosses_above", "crosses_below"):
        a0 = _num(_col(u, f"{field}_prev"))
        if "field2" in rule:
            b, b0 = _num(_col(u, rule["field2"])), _num(_col(u, f"{rule['field2']}_prev"))
        else:
            b = b0 = rule["value"]
        a = _num(a)
        m = (a0 <= b0) & (a > b) if op == "crosses_above" else (a0 >= b0) & (a < b)
        return m.fillna(False)
    raise ScanError(f"Unknown op '{op}'. Use one of {sorted(OPS) + ['between', 'in', 'not_in', 'is_true', 'is_false', 'contains', 'crosses_above', 'crosses_below']}")


def run(u: pd.DataFrame, rules: list, match: str = "all", universe: Optional[dict] = None,
        sort: Optional[dict] = None, limit: int = 100) -> pd.DataFrame:
    if u.empty:
        return u
    base = pd.Series(True, index=u.index)
    universe = universe or {}
    for key, col in (("sectors", "sector"), ("categories", "category"), ("assetTypes", "assetType")):
        if universe.get(key):
            base &= u[col].isin(universe[key])
    if universe.get("min_value_mn"):
        base &= _num(u["value_mn"]).fillna(0) >= universe["min_value_mn"]
    masks = [evaluate(u, r) for r in rules] or [pd.Series(True, index=u.index)]
    hit = pd.concat(masks, axis=1)
    hit = hit.all(axis=1) if match == "all" else hit.any(axis=1)
    out = u[base & hit]
    if sort:
        out = out.sort_values(sort["field"], ascending=not sort.get("desc", True), na_position="last")
    return out.head(limit)


# =========================================================================== presets
def P(name, group, desc, rules, sort=None, match="all", premarket=False):
    return {"name": name, "group": group, "description": desc, "rules": rules, "match": match,
            "sort": sort or {"field": "value_mn", "desc": True}, "premarket": premarket}


PRESETS = {
    # Trend & moving averages
    "golden_cross": P("Golden cross", "Trend", "SMA 50 crossed above SMA 200 today",
                      [{"field": "sma50", "op": "crosses_above", "field2": "sma200"}]),
    "death_cross": P("Death cross", "Trend", "SMA 50 crossed below SMA 200 today",
                     [{"field": "sma50", "op": "crosses_below", "field2": "sma200"}]),
    "ema_bull_cross": P("EMA 9/21 bullish cross", "Trend", "EMA 9 crossed above EMA 21 today",
                        [{"field": "ema9", "op": "crosses_above", "field2": "ema21"}]),
    "ema_bear_cross": P("EMA 9/21 bearish cross", "Trend", "EMA 9 crossed below EMA 21 today",
                        [{"field": "ema9", "op": "crosses_below", "field2": "ema21"}]),
    "price_cross_sma50": P("Price crossed above SMA 50", "Trend", "Close moved above SMA 50 today",
                           [{"field": "close", "op": "crosses_above", "field2": "sma50"}]),
    "above_all_mas": P("Above all moving averages", "Trend", "Close above SMA 20, 50 and 200",
                       [{"field": "close", "op": ">", "field2": "sma20"}, {"field": "close", "op": ">", "field2": "sma50"},
                        {"field": "close", "op": ">", "field2": "sma200"}], {"field": "ret_1m", "desc": True}),
    "strong_uptrend": P("Stacked uptrend", "Trend", "Close > SMA20 > SMA50 > SMA200",
                        [{"field": "close", "op": ">", "field2": "sma20"}, {"field": "sma20", "op": ">", "field2": "sma50"},
                         {"field": "sma50", "op": ">", "field2": "sma200"}], {"field": "ret_3m", "desc": True}),
    "below_all_mas": P("Below all moving averages", "Trend", "Close below SMA 20, 50 and 200",
                       [{"field": "close", "op": "<", "field2": "sma20"}, {"field": "close", "op": "<", "field2": "sma50"},
                        {"field": "close", "op": "<", "field2": "sma200"}], {"field": "ret_1m", "desc": False}),
    # Momentum
    "macd_bull_cross": P("MACD bullish cross", "Momentum", "MACD crossed above its signal line today",
                         [{"field": "macd", "op": "crosses_above", "field2": "macd_signal"}]),
    "macd_bear_cross": P("MACD bearish cross", "Momentum", "MACD crossed below its signal line today",
                         [{"field": "macd", "op": "crosses_below", "field2": "macd_signal"}]),
    "rsi_oversold": P("RSI oversold", "Momentum", "RSI(14) below 30", [{"field": "rsi14", "op": "<", "value": 30}],
                      {"field": "rsi14", "desc": False}),
    "rsi_overbought": P("RSI overbought", "Momentum", "RSI(14) above 70", [{"field": "rsi14", "op": ">", "value": 70}],
                        {"field": "rsi14", "desc": True}),
    "rsi_cross_50": P("RSI crossed above 50", "Momentum", "RSI(14) moved above 50 today",
                      [{"field": "rsi14", "op": "crosses_above", "value": 50}]),
    # Volatility
    "bb_squeeze": P("Bollinger squeeze", "Volatility", "Band width in the lowest 10% of the last 120 sessions",
                    [{"field": "bb_width_pctile", "op": "<=", "value": 10}], {"field": "bb_width", "desc": False}),
    "bb_breakout_up": P("Bollinger breakout up", "Volatility", "Close above the upper band",
                        [{"field": "close", "op": ">", "field2": "bb_upper"}]),
    "bb_breakdown": P("Bollinger breakdown", "Volatility", "Close below the lower band",
                      [{"field": "close", "op": "<", "field2": "bb_lower"}]),
    "nr7": P("NR7", "Volatility", "Narrowest range of the last 7 sessions (compression)",
             [{"field": "nr7", "op": "is_true"}], premarket=True),
    "inside_bar": P("Inside bar", "Volatility", "Today's range inside yesterday's", [{"field": "inside_bar", "op": "is_true"}],
                    premarket=True),
    # Breakouts
    "new_52w_high": P("New 52-week high", "Breakout", "Traded at or above the prior 52-week high",
                      [{"field": "new_52w_high", "op": "is_true"}], {"field": "change_pct", "desc": True}),
    "near_52w_high": P("Near 52-week high", "Breakout", "Within 5% of the 52-week high",
                       [{"field": "pct_from_52w_high", "op": ">=", "value": -5}], {"field": "pct_from_52w_high", "desc": True}),
    "near_52w_low": P("Near 52-week low", "Breakout", "Within 5% of the 52-week low",
                      [{"field": "pct_from_52w_low", "op": "<=", "value": 5}], {"field": "pct_from_52w_low", "desc": False}),
    "breakout_20d": P("20-day breakout", "Breakout", "Close above the highest high of the previous 20 sessions",
                      [{"field": "breakout_20d", "op": "is_true"}, {"field": "vol_ratio", "op": ">=", "value": 1.2}]),
    "breakdown_20d": P("20-day breakdown", "Breakout", "Close below the lowest low of the previous 20 sessions",
                       [{"field": "breakdown_20d", "op": "is_true"}]),
    "gap_up": P("Gap up", "Breakout", "Opened above yesterday's high", [{"field": "gap_up_pct", "op": ">", "value": 0}],
                {"field": "gap_up_pct", "desc": True}),
    "gap_down": P("Gap down", "Breakout", "Opened below yesterday's low", [{"field": "gap_down_pct", "op": "<", "value": 0}],
                  {"field": "gap_down_pct", "desc": False}),
    # Volume / VPA
    "volume_spike_up": P("Volume spike, price up", "Volume", "Volume ≥ 2× its 20-day average on an up day",
                         [{"field": "vol_ratio", "op": ">=", "value": 2}, {"field": "change_pct", "op": ">", "value": 0}],
                         {"field": "vol_ratio", "desc": True}),
    "volume_spike_down": P("Volume spike, price down", "Volume", "Volume ≥ 2× its 20-day average on a down day",
                           [{"field": "vol_ratio", "op": ">=", "value": 2}, {"field": "change_pct", "op": "<", "value": 0}],
                           {"field": "vol_ratio", "desc": True}),
    "vpa_bullish": P("VPA bullish", "Volume", "Strong buying, stopping volume or no supply today",
                     [{"field": "vpa_bias", "op": "==", "value": "bullish"}], {"field": "vol_rel", "desc": True}),
    "vpa_bearish": P("VPA bearish", "Volume", "Strong selling, upthrust or no demand today",
                     [{"field": "vpa_bias", "op": "==", "value": "bearish"}], {"field": "vol_rel", "desc": True}),
    # Candles
    "bullish_candles": P("Bullish candle pattern", "Candles", "Any bullish pattern completed today",
                         [{"field": "bullish_pattern", "op": "is_true"}], premarket=True),
    "bearish_candles": P("Bearish candle pattern", "Candles", "Any bearish pattern completed today",
                         [{"field": "bearish_pattern", "op": "is_true"}], premarket=True),
    "hammer": P("Hammer", "Candles", "Hammer after a decline", [{"field": "patterns", "op": "contains", "value": "Hammer"}],
                premarket=True),
    "bullish_engulfing": P("Bullish engulfing", "Candles", "Bullish engulfing today",
                           [{"field": "patterns", "op": "contains", "value": "Bullish Engulfing"}], premarket=True),
    "morning_star": P("Morning star", "Candles", "Morning star completed today",
                      [{"field": "patterns", "op": "contains", "value": "Morning Star"}], premarket=True),
    # Setup
    "short_term_setup": P("Short-term long setup ≥ 5/6", "Setup",
                          "Above EMA21 & SMA50, RSI 50–70, volume ≥ 1.5×, bullish candle, not Z",
                          [{"field": "setup_score", "op": ">=", "value": 5}], {"field": "setup_score", "desc": True}),
    "pre_market_watch": P("Pre-market watchlist", "Setup",
                          "Last completed session: setup ≥ 4/6 and close above EMA 21", [
                              {"field": "setup_score", "op": ">=", "value": 4},
                              {"field": "close", "op": ">", "field2": "ema21"}],
                          {"field": "setup_score", "desc": True}, premarket=True),
    # Fundamentals
    "value_pe": P("Low P/E (0–15)", "Fundamental", "Positive TTM earnings, P/E under 15",
                  [{"field": "pe", "op": "between", "value": [0.01, 15]}], {"field": "pe", "desc": False}),
    "graham_undervalued": P("Below Graham number", "Fundamental", "Price below √(22.5 × EPS × NAV)",
                            [{"field": "graham_gap_pct", "op": ">", "value": 0}], {"field": "graham_gap_pct", "desc": True}),
    "low_pb": P("Below book (P/B < 1)", "Fundamental", "Price under NAV per share",
                [{"field": "pb", "op": "between", "value": [0.01, 1]}], {"field": "pb", "desc": False}),
    "high_dividend": P("Dividend yield ≥ 5%", "Fundamental", "Trailing dividend yield of 5% or more",
                       [{"field": "dividend_yield_pct", "op": ">=", "value": 5}], {"field": "dividend_yield_pct", "desc": True}),
    "strong_sponsor": P("Sponsor holding ≥ 30%", "Fundamental", "Sponsors/directors hold at least 30% (BSEC floor)",
                        [{"field": "sponsor_pct", "op": ">=", "value": 30}], {"field": "sponsor_pct", "desc": True}),
}

FIELD_DOCS = {
    "ltp": "Last traded price", "change_pct": "% change vs yesterday's close", "value_mn": "Turnover, BDT mn",
    "rsi14": "RSI(14)", "macd": "MACD(12,26)", "macd_signal": "MACD signal(9)", "macd_hist": "MACD histogram",
    "sma20": "SMA 20", "sma50": "SMA 50", "sma200": "SMA 200", "ema9": "EMA 9", "ema21": "EMA 21",
    "bb_upper": "Bollinger upper", "bb_lower": "Bollinger lower", "bb_width": "Band width / mid",
    "bb_width_pctile": "Band-width percentile over 120 sessions", "atr14": "ATR(14)", "atr_pct": "ATR as % of price",
    "vol_ratio": "Volume / 20-day average", "pct_from_52w_high": "% below 52-week high",
    "pct_from_52w_low": "% above 52-week low", "ret_1w": "1-week return %", "ret_1m": "1-month return %",
    "ret_3m": "3-month return %", "ret_6m": "6-month return %", "ret_1y": "1-year return %",
    "gap_up_pct": "Open vs prior high %", "gap_down_pct": "Open vs prior low %", "setup_score": "Setup score 0–6",
    "pe": "P/E (TTM)", "pb": "P/B", "eps_ttm": "TTM EPS", "nav": "NAV/share", "dividend_yield_pct": "Dividend yield %",
    "sponsor_pct": "Sponsor %", "free_float_pct": "Free float %", "market_cap": "Market cap BDT",
    "graham_gap_pct": "Graham number vs price %", "vpa": "VPA label", "vpa_bias": "VPA bias",
    "patterns": "Candle patterns today (list)", "bullish_pattern": "Bullish pattern today", "nr7": "NR7 day",
    "inside_bar": "Inside bar", "new_52w_high": "New 52-week high", "breakout_20d": "20-day breakout",
    "breakdown_20d": "20-day breakdown", "sector": "Sector", "category": "A/B/N/Z", "assetType": "EQ / MF",
}

DEFAULT_COLUMNS = ["symbol", "sector", "category", "ltp", "change_pct", "value_mn", "vol_ratio", "rsi14",
                   "setup_score", "vpa", "patterns", "pe", "pct_from_52w_high"]


def to_records(df: pd.DataFrame, columns: Optional[list] = None) -> list:
    cols = [c for c in (columns or DEFAULT_COLUMNS) if c in df.columns]
    out = []
    for rec in df[cols].to_dict("records"):
        out.append({k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else
                        round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()})
    return out


# =========================================================================== market analytics
def sectors(u: pd.DataFrame) -> list:
    g = u.groupby("sector")
    out = pd.DataFrame({
        "instruments": g.size(), "advanced": g["change_pct"].apply(lambda s: int((s > 0).sum())),
        "declined": g["change_pct"].apply(lambda s: int((s < 0).sum())),
        "avg_change_pct": g["change_pct"].mean(), "turnover_mn": g["value_mn"].sum(),
        "median_pe": g["pe"].median(), "avg_rsi": g["rsi14"].mean(), "ret_1m": g["ret_1m"].median(),
    }).reset_index()
    tot = out["turnover_mn"].sum() or 1
    out["turnover_share_pct"] = out["turnover_mn"] / tot * 100
    return to_records(out.sort_values("turnover_mn", ascending=False), list(out.columns))


def pe_summary(u: pd.DataFrame) -> dict:
    d = u[(u["pe"].notna()) & (u["pe"] > 0) & u["market_cap"].notna()].copy()
    d["earnings"] = d["market_cap"] / d["pe"]

    def agg(x):
        return {"instruments": int(len(x)), "median_pe": float(x["pe"].median()) if len(x) else None,
                "weighted_pe": float(x["market_cap"].sum() / x["earnings"].sum()) if len(x) else None}
    return {"market": agg(d),
            "by_sector": {k: agg(g) for k, g in d.groupby("sector")},
            "by_category": {k: agg(g) for k, g in d.groupby("category")},
            "note": "P/E uses TTM EPS (positive earnings only); weighted = Σ market cap / Σ earnings."}


def correlation(bars: dict, symbols: list, days: int = 120) -> dict:
    closes = pd.DataFrame({s: bars[s]["close"] for s in symbols if s in bars}).iloc[-days - 1:]
    rets = closes.pct_change().dropna(how="all")
    m = rets.corr(min_periods=20).round(3)
    return {"symbols": list(m.columns), "days": days,
            "matrix": [[None if pd.isna(x) else float(x) for x in row] for row in m.values]}
