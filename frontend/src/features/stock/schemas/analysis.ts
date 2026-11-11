import { z } from "zod";

const n = z.number().nullable();

export const analysisSchema = z.object({
  symbol: z.string(),
  name: z.string().nullable(),
  as_of: z.string().nullable(),
  price: z.object({
    ltp: n,
    prev_close: n,
    change: n,
    change_pct: n,
    open: n,
    high: n,
    low: n,
    volume: n,
    trades: n,
    value_mn: n,
    live_bar: z.boolean(),
    market_open: z.boolean(),
    last_bar_date: z.string(),
    first_bar_date: z.string(),
    bars_available: z.number(),
  }),
  signal: z.object({
    action: z.string(),
    net_votes: z.number(),
    bullish_reasons: z.array(z.string()),
    bearish_reasons: z.array(z.string()),
    rule: z.string(),
  }),
  setup: z.object({
    score: z.number(),
    max: z.number(),
    checks: z.array(z.object({ key: z.string(), label: z.string(), pass: z.boolean() })),
    plan: z.object({
      entry: z.number(),
      entry_zone: z.tuple([z.number(), z.number()]),
      stop: z.number(),
      stop_basis: z.string(),
      target: z.number(),
      target_basis: z.string(),
      atr: z.number(),
      risk_pct: z.number(),
      reward_pct: z.number(),
      rr: n,
      rr_ok: z.boolean(),
    }),
    flags: z.array(z.string()),
  }),
  probability: z.object({
    horizon_sessions: z.number(),
    target_pct: z.number(),
    stop_pct: z.number(),
    similar_setups: z.object({
      n: z.number(),
      wins: z.number(),
      losses: z.number(),
      unresolved: z.number(),
      p_target_first: n,
      avg_fwd_return_pct: n,
      pct_positive_fwd: n,
      expectancy_pct: n,
    }),
    all_days_baseline: z.object({ p_target_first: n }),
    reliable: z.boolean(),
    warning: z.string().nullable().optional(),
    method: z.string(),
  }),
  indicators: z.record(z.string(), n),
  candles: z.object({
    last_candle: z.string(),
    patterns: z.array(
      z.object({
        date: z.string(),
        bars_ago: z.number(),
        pattern: z.string(),
        direction: z.enum(["bullish", "bearish", "neutral"]),
        high: z.number(),
        low: z.number(),
      }),
    ),
  }),
  levels: z.object({ price: z.number(), high_52w: z.number(), low_52w: z.number(), above: z.array(z.number()), below: z.array(z.number()) }),
  trend: z.object({
    changes: z.record(z.string(), n),
    vs_ma: z.record(z.string(), z.object({ value: z.number(), pct: z.number() }).nullable()),
  }),
  valuation: z.object({
    rows: z.array(z.object({ method: z.string(), inputs: z.string(), fair_value: n, gap_pct: n })),
    notes: z.array(z.string()),
    implied_growth: n,
    median_fair_value: n,
  }),
  fundamentals: z.object({
    sector: z.string().nullable(),
    category: z.string().nullable(),
    eps_ttm: n,
    eps_ttm_basis: z.string().nullable(),
    eps_annual: n,
    eps_q1: n,
    eps_q2: n,
    eps_q3: n,
    nav: n,
    pe: n,
    pe_dse_trailing: n,
    market_cap: n,
    total_shares: n,
    free_float_pct: n,
    dividend_yield_pct: n,
    last_dividend: z.object({ year: z.number(), cash_pct: z.number(), stock_pct: z.number() }).nullable(),
    shareholding: z.object({
      sponsor_pct: n,
      government_pct: n,
      institution_pct: n,
      foreign_pct: n,
      public_pct: n,
    }),
    week_high_52: n,
    week_low_52: n,
  }),
  news: z.array(
    z.object({ id: z.string().nullable(), date: z.string().nullable(), type: z.string().nullable(), title: z.string().nullable(), text: z.string() }),
  ),
  summary: z.array(z.string()),
  disclaimer: z.string(),
});
export type Analysis = z.infer<typeof analysisSchema>;

export const technicalBarSchema = z.object({
  date: z.string(),
  open: n,
  high: n,
  low: n,
  close: n,
  volume: n,
  sma20: n,
  sma50: n,
  sma200: n,
  ema9: n,
  ema21: n,
  bb_upper: n,
  bb_lower: n,
  vol_avg20: n,
});
export type TechnicalBar = z.infer<typeof technicalBarSchema>;

export const vpaRowSchema = z.object({
  date: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
  vpa: z.string().nullable(),
  vpa_bias: z.string().nullable(),
  spread_rel: n,
  vol_rel: n,
  close_pos: n,
});
export type VpaRow = z.infer<typeof vpaRowSchema>;

export const vpaLegendSchema = z.record(z.string(), z.object({ bias: z.string(), meaning: z.string() }));

export const intradayBarSchema = z.object({
  time: z.string().regex(/^\d{2}:\d{2}$/),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
  vpa: z.string().nullable(),
});
export type IntradayBar = z.infer<typeof intradayBarSchema>;
