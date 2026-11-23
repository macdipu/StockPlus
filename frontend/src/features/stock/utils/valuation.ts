import type { Company } from "@/features/company";
import { num, pct } from "@/shared/lib/format";
import type { Analysis } from "../schemas/analysis";
import { dividendRecord, FINANCIAL, ratio } from "./company-facts";
import { quantile } from "./reading";

/**
 * Which of the fair-value methods suit this particular share, and why. The table mixes methods that make sense for some
 * businesses and none for others (a price-to-book multiple says little about a company earning 50% on its equity), so a
 * median over all of them can mislead. Pure rules over the analysis and the company data; each verdict carries its reason.
 */

export type Fit = "yes" | "partly" | "no";

export interface MethodFit {
  method: string;
  fit: Fit;
  why: string;
}

interface Profile {
  financial: boolean;
  roe: number | null;
  eps: number | null;
  epsGrowth: number | null;
  dps: number | null;
  record: { paid: number; of: number } | null;
  nav: number | null;
}

function profile(a: Analysis, c: Company | undefined): Profile {
  return {
    financial: FINANCIAL.test(a.fundamentals.sector ?? ""),
    roe: ratio(c, "roe"),
    eps: a.fundamentals.eps_ttm,
    epsGrowth: ratio(c, "eps_growth"),
    dps: a.fundamentals.dividend_per_share ?? null,
    record: dividendRecord(c),
    nav: a.fundamentals.nav,
  };
}

export function methodFit(method: string, p: Profile): MethodFit {
  const out = (fit: Fit, why: string): MethodFit => ({ method, fit, why });
  const lossMaking = p.eps != null && p.eps <= 0;

  if (/^P\/E/i.test(method)) {
    if (lossMaking) return out("no", "Earnings are negative, so a multiple of earnings gives nothing.");
    const multiple = Number(/(\d+)x/i.exec(method)?.[1] ?? 0);
    if (p.financial && multiple >= 15) return out("partly", `Banks and financials usually trade well below ${multiple} times earnings.`);
    const needs = multiple >= 25 ? 10 : multiple >= 20 ? 5 : -Infinity; // growth (%) a higher multiple assumes
    if (p.epsGrowth != null && p.epsGrowth < needs) return out("partly", `A ${multiple}x multiple assumes growth; earnings per share moved ${pct(p.epsGrowth, 0)} last year.`);
    return out("yes", "Earnings are positive and the multiple is not demanding.");
  }
  if (/^P\/B/i.test(method)) {
    if (p.nav != null && p.nav <= 0) return out("no", "Book value is not positive.");
    if (p.financial) {
      const times = Number(/([\d.]+)x/i.exec(method)?.[1] ?? 0);
      return times >= 3 ? out("partly", `${times}x book is rich for a bank or financial.`) : out("yes", "For banks and financials, book value is the main anchor.");
    }
    if (p.roe != null && p.roe >= 20) return out("no", `Return on equity is ${num(p.roe, 1)}%: book value understates what this business earns, so a book multiple says little.`);
    if (p.roe != null && p.roe >= 10) return out("partly", "Return on equity is good, so earning power matters more than book value.");
    return out("yes", "A modest return on equity means book value is a fair anchor.");
  }
  if (/^Graham/i.test(method)) {
    if (lossMaking || (p.nav != null && p.nav <= 0)) return out("no", "Needs positive earnings and book value.");
    if (p.roe != null && p.roe >= 20) return out("no", "Built for steady, asset-heavy companies; it penalises a high-return business for its small book.");
    if (p.financial) return out("partly", "A rough check only for financials.");
    return out("yes", "Positive earnings and book value.");
  }
  if (/^Dividend/i.test(method)) {
    if (p.dps == null || p.dps <= 0) return out("no", "No dividend per share to discount.");
    if (p.record && p.record.of >= 3 && p.record.paid / p.record.of >= 0.8) return out("yes", `A dividend was paid in ${p.record.paid} of the last ${p.record.of} years.`);
    return out("partly", "The dividend record is short or patchy.");
  }
  if (/^DCF/i.test(method)) {
    if (lossMaking) return out("no", "Needs positive earnings to project.");
    return out("yes", "Earnings are positive; the bear, base and bull cases show the spread.");
  }
  return out("yes", "");
}

export interface FitReading {
  fits: MethodFit[];
  /** Fair values of the methods that fit, sorted. */
  values: number[];
  median: number;
  gapPct: number | null;
  low: number;
  high: number;
  count: number;
  total: number;
  excluded: MethodFit[];
  text: string;
}

/** The headline fair value from the methods that fit this share. Needs at least three that do. */
export function fitReading(a: Analysis, c: Company | undefined): FitReading | null {
  const p = profile(a, c);
  const rows = a.valuation.rows.filter((r) => r.fair_value != null && r.fair_value > 0);
  const fits = rows.map((r) => methodFit(r.method, p));
  const kept = rows.filter((_, i) => fits[i]?.fit === "yes").map((r) => r.fair_value as number).sort((x, y) => x - y);
  if (kept.length < 3) return null;
  const median = quantile(kept, 0.5);
  const price = a.price.ltp;
  const gapPct = price ? (median / price - 1) * 100 : null;
  const excluded = fits.filter((f) => f.fit !== "yes");
  const text = `Of the ${rows.length} methods, ${kept.length} fit this share. Their median fair value is ${num(median)}${gapPct == null ? "" : ` (${pct(gapPct, 0)} against the price)`}, within a range of ${num(kept[0])} to ${num(kept.at(-1))}.`;
  return { fits, values: kept, median, gapPct, low: kept[0] as number, high: kept.at(-1) as number, count: kept.length, total: rows.length, excluded, text };
}

/** Where each value sits on one shared scale (0 to 100), so every method's marker and the price line line up. */
export function scaleFor(values: readonly number[], price: number | null): (v: number) => number {
  const all = price != null ? [...values, price] : [...values];
  const lo = Math.min(...all) * 0.9;
  const hi = Math.max(...all) * 1.05;
  return (v) => (hi > lo ? Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100)) : 50);
}
