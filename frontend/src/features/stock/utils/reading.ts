import { num, pct } from "@/shared/lib/format";
import type { Analysis } from "../schemas/analysis";

/** Plain-language readings of the analysis numbers. Pure: the same inputs always say the same thing. */

const ACTION: Record<string, string> = {
  "STRONG BUY": "Strong setup to buy",
  BUY: "Reasonable setup to buy",
  HOLD: "No clear signal: hold, or wait",
  SELL: "Weak setup: avoid buying now. If you already hold it, review your exit",
  "STRONG SELL": "Very weak setup: avoid. If you hold it, review your exit",
  AVOID: "Avoid for now",
};

export const actionSentence = (action: string): string => ACTION[action] ?? action;

export interface EdgeReading {
  tone: "up" | "dn" | "mute";
  text: string;
}

/** Whether past setups like this one did better than an ordinary day, in words. `similar` and `base` are the
 * shares of past cases that reached the target before the stop (0 to 1). */
export function edgeReading(similar: number | null, base: number | null, cases: number, reliable: boolean): EdgeReading {
  if (similar == null || base == null) return { tone: "mute", text: "Not enough past cases to say how setups like this one have done." };
  const s = Math.round(similar * 100);
  const b = Math.round(base * 100);
  const small = reliable ? "" : ` (only ${cases} past cases, so treat this loosely)`;
  const diff = similar - base;
  if (diff >= 0.03) return { tone: "up", text: `An edge: setups like this reached the target first ${s}% of the time, against ${b}% on an ordinary day${small}.` };
  if (diff <= -0.03) return { tone: "dn", text: `Worse than usual: setups like this reached the target first ${s}% of the time, against ${b}% on an ordinary day${small}.` };
  return { tone: "mute", text: `No edge: setups like this reached the target first ${s}% of the time, the same as an ordinary day (${b}%)${small}.` };
}

export interface YieldReading {
  value: number | null;
  basis: string;
}

/** One dividend yield for the page: the last dividend per share over today's price. The exchange's own yield statistic
 * is only a fallback, because it is not tied to the price shown beside it. */
export function dividendYield(a: Analysis): YieldReading {
  const dps = a.fundamentals.dividend_per_share ?? null;
  const price = a.price.ltp;
  if (dps != null && price != null && price > 0) return { value: (dps / price) * 100, basis: `last dividend Tk ${num(dps)} ÷ price ${num(price)}` };
  if (a.fundamentals.dividend_yield_pct != null) return { value: a.fundamentals.dividend_yield_pct, basis: "exchange figure" };
  return { value: null, basis: "" };
}

export interface FairValueReading {
  /** How many methods gave a fair value. */
  total: number;
  median: number;
  gapPct: number | null;
  low: number;
  high: number;
  q1: number;
  q3: number;
  wide: boolean;
  text: string;
}

export function quantile(sorted: readonly number[], q: number): number {
  const i = (sorted.length - 1) * q;
  const lo = Math.floor(i);
  const hi = Math.ceil(i);
  return (sorted[lo] as number) + ((sorted[hi] as number) - (sorted[lo] as number)) * (i - lo);
}

/** One line from the fair-value table: the median, the middle half of the methods and the full range. */
export function fairValueReading(a: Analysis): FairValueReading | null {
  const fair = a.valuation.rows.map((r) => r.fair_value).filter((v): v is number => v != null && v > 0).sort((x, y) => x - y);
  if (fair.length < 3) return null;
  const median = a.valuation.median_fair_value ?? quantile(fair, 0.5);
  const q1 = quantile(fair, 0.25);
  const q3 = quantile(fair, 0.75);
  const price = a.price.ltp;
  const gapPct = price ? (median / price - 1) * 100 : null;
  const wide = (q3 - q1) / median > 0.6;
  const parts = [
    `Median fair value ${num(median)}${gapPct == null ? "" : ` (${pct(gapPct, 0)} against the price)`}.`,
    `The middle half of the ${fair.length} methods lands between ${num(q1)} and ${num(q3)}; all of them between ${num(fair[0])} and ${num(fair[fair.length - 1])}.`,
    wide ? "The methods disagree widely, so treat the median as a rough guide." : "",
  ];
  return { total: fair.length, median, gapPct, low: fair[0] as number, high: fair[fair.length - 1] as number, q1, q3, wide, text: parts.filter(Boolean).join(" ") };
}

interface Level {
  kind: string;
  price: number;
  price_to?: number | null;
}

/** Watch levels that sit on top of the buy zone, stop or a target (within 0.4%) only repeat them. */
export function withoutRepeatedWatch<T extends Level>(levels: readonly T[]): T[] {
  const firm = levels.filter((l) => l.kind !== "watch");
  const same = (a: number, b: number) => Math.abs(a - b) <= Math.abs(b) * 0.004;
  return levels.filter((l) => l.kind !== "watch" || !firm.some((f) => same(l.price, f.price) || (f.price_to != null && same(l.price, f.price_to))));
}
