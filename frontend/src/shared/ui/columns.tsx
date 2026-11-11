import Link from "next/link";
import type { ReactNode } from "react";
import { crore, DASH, int, num, pct, text, tone } from "@/shared/lib/format";
import type { Column } from "./DataTable";

export const LABELS: Readonly<Record<string, string>> = {
  symbol: "Symbol", name: "Name", sector: "Sector", category: "Cat", ltp: "LTP", change_pct: "Chg %", percent: "Chg %",
  value_mn: "Value mn", vol_ratio: "Vol/avg", rsi14: "RSI", setup_score: "Setup", vpa: "VPA", patterns: "Patterns",
  pe: "P/E", pb: "P/B", pct_from_52w_high: "vs 52w high", pct_from_52w_low: "vs 52w low", eps_ttm: "EPS TTM", nav: "NAV",
  dividend_yield_pct: "Yield %", sponsor_pct: "Sponsor %", free_float_pct: "Float %", market_cap: "Mkt cap", graham: "Graham",
  graham_gap_pct: "Graham gap", ret_1w: "1W", ret_1m: "1M", ret_3m: "3M", ret_6m: "6M", ret_1y: "1Y", macd: "MACD",
  macd_signal: "MACD signal", macd_hist: "MACD hist", sma20: "SMA20", sma50: "SMA50", sma200: "SMA200", ema9: "EMA9",
  ema21: "EMA21", atr_pct: "ATR %", bb_width_pctile: "BB width pctile", range_position_pct: "In range", low_52w: "52w low",
  high_52w: "52w high", instruments: "Stocks", advanced: "▲", declined: "▼", avg_change_pct: "Avg chg %",
  turnover_mn: "Turnover mn", turnover_share_pct: "Share %", median_pe: "Median P/E", weighted_pe: "Weighted P/E",
  avg_rsi: "Avg RSI", volume: "Volume", trades: "Trades",
};

const SIGNED_PCT = new Set(["change_pct", "percent", "avg_change_pct", "ret_1w", "ret_1m", "ret_3m", "ret_6m", "ret_1y", "pct_from_52w_high", "pct_from_52w_low"]);
const BULLISH_VPA = /buying|stopping|no supply/i;
const BEARISH_VPA = /selling|upthrust|no demand/i;

export function formatValue(key: string, v: unknown): ReactNode {
  if (v == null || v === "") return DASH;
  if (key === "symbol") return <b>{String(v)}</b>;
  if (typeof v === "number") {
    if (key === "graham_gap_pct") return <span className={tone(v)}>{pct(v, 0)}</span>;
    if (SIGNED_PCT.has(key)) return <span className={tone(v)}>{pct(v, key.includes("change") || key === "percent" ? 2 : 1)}</span>;
    if (key === "range_position_pct") return `${num(v, 0)}%`;
    if (key === "vol_ratio") return `${num(v)}×`;
    if (key === "market_cap") return crore(v);
    if (key === "setup_score") return `${v}/6`;
    if (["volume", "trades", "instruments", "advanced", "declined"].includes(key)) return int(v);
    return num(v, Number.isInteger(v) ? 0 : 2);
  }
  if (key === "vpa") {
    return <span className={BULLISH_VPA.test(String(v)) ? "up" : BEARISH_VPA.test(String(v)) ? "dn" : ""}>{String(v)}</span>;
  }
  return text(v);
}

/** Columns for a table whose fields are only known at run time (scan results, data matrix, TA values). */
export function columnsFor<R extends object>(keys: readonly string[], sample?: Record<string, unknown>): Column<R>[] {
  return keys.map((key): Column<R> => {
    const numeric = typeof sample?.[key] === "number";
    return {
      key,
      label: LABELS[key] ?? key,
      align: numeric ? "right" : "left",
      value: (r) => {
        const v = (r as Record<string, unknown>)[key];
        return Array.isArray(v) ? v.join(", ") : (v as string | number | null | undefined);
      },
      render: (r) => {
        const v = (r as Record<string, unknown>)[key];
        if (key === "symbol" && typeof v === "string") {
          return <Link href={`/stock/${encodeURIComponent(v)}`}><b>{v}</b></Link>;
        }
        return formatValue(key, v);
      },
    };
  });
}

export function symbolHref(r: { symbol?: string | null }): string | null {
  return r.symbol ? `/stock/${encodeURIComponent(r.symbol)}` : null;
}
