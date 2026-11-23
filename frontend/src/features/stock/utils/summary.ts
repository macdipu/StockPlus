import type { Company } from "@/features/company";
import { num, pct } from "@/shared/lib/format";
import type { Analysis } from "../schemas/analysis";
import { actionSentence, dividendYield, fairValueReading } from "./reading";
import type { Relative } from "./strength";

/**
 * The analyst's one-page reading of a share, as plain data. Every rating is the sum of small rules; each rule that
 * applies produces one sentence with its number, so the rating can always be traced to what it was built from. Pure:
 * no fetching and no rendering. These are rules of thumb for orientation, not advice.
 */

export type TileKey = "quality" | "value" | "timing" | "risk";
export type Tone = "up" | "dn" | "warn" | "mute";

export interface Evidence {
  tile: TileKey;
  /** Positive helps the case for owning the share, negative hurts it. */
  points: number;
  text: string;
}

export interface PeContext {
  marketMedian: number | null;
  /** The market's cap-weighted P/E: big companies count for more, unlike the median. */
  marketWeighted?: number | null;
  sector: { name: string; companies: number; median: number | null } | null;
}

/** How the share did against the DSEX index over the last month and three months. */
export interface RelativeStrength {
  m1: Relative | null;
  m3: Relative | null;
}

export interface Fact {
  label: string;
  value: string;
}

export interface TileReading {
  key: TileKey;
  title: string;
  rating: string;
  tone: Tone;
  evidence: Evidence[];
  facts: Fact[];
  /** A short series to draw beside the facts (earnings per share by year), oldest first. */
  trend?: { label: string; values: number[]; first: string; last: string };
}

export interface Summary {
  tiles: TileReading[];
  verdict: string;
  actionLine: string;
  reasonsFor: string[];
  reasonsAgainst: string[];
}

const FINANCIAL = /bank|financial|insurance|leasing|nbfi/i;
const MIN_SECTOR_GROUP = 5; // a sector with fewer companies is too small a group to call a norm

const ratio = (c: Company | undefined, key: string): number | null => c?.ratios.find((r) => r.key === key)?.value ?? null;
const ind = (a: Analysis, key: string): number | null => a.indicators[key] ?? null;

function dividendRecord(c: Company | undefined): { paid: number; of: number } | null {
  for (const f of c?.flags ?? []) {
    const m = /paid a cash dividend in (\d+) of the last (\d+) years/i.exec(f.text);
    if (m) return { paid: Number(m[1]), of: Number(m[2]) };
  }
  return null;
}

/** The buy zone the page shows everywhere: the one the trade plan writes out and the chart draws (from nearby support).
 * The setup plan's own entry zone is a different, tighter range around today's price, so it is only a fallback. */
export function buyZone(a: Analysis): { low: number; high: number } {
  const entry = a.candle_story?.annotations.find((x) => x.kind === "entry");
  if (entry) return { low: Math.min(entry.price, entry.price_to ?? entry.price), high: Math.max(entry.price, entry.price_to ?? entry.price) };
  const z = a.setup.plan.entry_zone;
  return { low: Math.min(...z), high: Math.max(...z) };
}

export function avgTurnoverMn(a: Analysis): number | null {
  const vol = ind(a, "vol_avg20");
  return vol != null && a.price.ltp != null ? (vol * a.price.ltp) / 1_000_000 : null;
}

export function evidence(a: Analysis, c: Company | undefined, pe: PeContext | null, rs: RelativeStrength | null = null): Evidence[] {
  const out: Evidence[] = [];
  const add = (tile: TileKey, points: number, text: string) => out.push({ tile, points, text });
  const sector = a.fundamentals.sector ?? "";
  const financial = FINANCIAL.test(sector);
  const price = a.price.ltp;

  // ---- business quality
  const roe = ratio(c, "roe");
  if (roe != null) {
    if (roe >= 20) add("quality", 2, `Return on equity ${num(roe, 1)}%: very high, the business earns a lot on its capital.`);
    else if (roe >= 12) add("quality", 1, `Return on equity ${num(roe, 1)}%: good.`);
    else if (roe < 0) add("quality", -2, `Return on equity ${num(roe, 1)}%: the business lost money last year.`);
    else if (roe < 5) add("quality", -1, `Return on equity ${num(roe, 1)}%: low.`);
  }
  const margin = ratio(c, "net_margin");
  if (margin != null) {
    if (margin >= 15) add("quality", 1, `Net margin ${num(margin, 1)}%: keeps a good share of sales as profit.`);
    else if (margin < 0) add("quality", -2, `Net margin ${num(margin, 1)}%: loses money on its sales.`);
    else if (margin < 3) add("quality", -1, `Net margin ${num(margin, 1)}%: very thin.`);
  }
  const de = ratio(c, "debt_to_equity") ?? ratio(c, "loan_to_equity");
  if (de != null && !financial) {
    if (de > 3) add("quality", -2, `Debt is ${num(de, 1)}× equity: very heavy borrowing.`);
    else if (de > 1.5) add("quality", -1, `Debt is ${num(de, 1)}× equity: heavy borrowing.`);
    else if (de <= 0.5) add("quality", 1, `Low borrowing: debt is ${num(de, 1)}× equity.`);
  }
  const growth = ratio(c, "eps_growth");
  if (growth != null) {
    if (growth >= 10) add("quality", 1, `Earnings per share grew ${num(growth, 0)}% last year.`);
    else if (growth <= -40) add("quality", -2, `Earnings per share fell ${num(Math.abs(growth), 0)}% last year.`);
    else if (growth <= -15) add("quality", -1, `Earnings per share fell ${num(Math.abs(growth), 0)}% last year.`);
  }
  const div = dividendRecord(c);
  if (div) {
    if (div.of >= 3 && div.paid / div.of >= 0.8) add("quality", 1, `Paid a cash dividend in ${div.paid} of the last ${div.of} years.`);
    else if (div.of >= 3 && div.paid === 0) add("quality", -1, `No cash dividend in the last ${div.of} years.`);
  }
  const rating = c?.profile.credit_rating?.long_term;
  if (rating) {
    if (/^AA/i.test(rating)) add("quality", 1, `Credit rating ${rating}: strong.`);
    else if (/^(B|C|D)/i.test(rating)) add("quality", -1, `Credit rating ${rating}: weak.`);
  }

  // ---- value
  const fair = fairValueReading(a);
  if (fair && fair.gapPct != null) {
    const g = fair.gapPct;
    const where = `${num(Math.abs(g), 0)}% ${g >= 0 ? "above" : "below"} the price`;
    if (g >= 20) add("value", 2, `Median fair value ${num(fair.median)} is ${where}.`);
    else if (g >= 5) add("value", 1, `Median fair value ${num(fair.median)} is ${where}.`);
    else if (g <= -30) add("value", -2, `Median fair value ${num(fair.median)} is ${where}.`);
    else if (g <= -10) add("value", -1, `Median fair value ${num(fair.median)} is ${where}.`);
    else add("value", 0, `Priced close to its median fair value (${num(fair.median)}).`);
  }
  const p = a.fundamentals.pe;
  if (p != null && p > 0) {
    const useSector = pe?.sector && pe.sector.companies >= MIN_SECTOR_GROUP && pe.sector.median != null;
    const base = useSector ? pe?.sector?.median : pe?.marketMedian;
    const group = useSector ? `${pe?.sector?.name} sector` : "market";
    if (base != null && base > 0) {
      const r = p / base;
      const w = pe?.marketWeighted;
      if (r <= 0.7 && (useSector || w == null || p <= w)) add("value", 1, `P/E ${num(p, 1)} is well below the ${group} median of ${num(base, 1)}.`);
      else if (r <= 0.7) add("value", 0, `P/E ${num(p, 1)} is below the ${group} median of ${num(base, 1)}, but not below the market's size-weighted P/E of ${num(w, 1)}.`);
      else if (r >= 1.5) add("value", -1, `P/E ${num(p, 1)} is well above the ${group} median of ${num(base, 1)}.`);
      else add("value", 0, `P/E ${num(p, 1)} is close to the ${group} median of ${num(base, 1)}.`);
    }
  } else if (a.fundamentals.eps_ttm != null && a.fundamentals.eps_ttm < 0) {
    add("value", -2, "Loss-making: there is no P/E to judge it by.");
  }
  const dy = dividendYield(a).value;
  if (dy != null && dy >= 6) add("value", 1, `Dividend yield ${num(dy, 1)}%: a high income return.`);

  // ---- timing
  const sma200 = ind(a, "sma200");
  const sma50 = ind(a, "sma50");
  if (price != null && sma200 != null) add("timing", price >= sma200 ? 1 : -1, price >= sma200 ? "Above its 200-day average: the long-term trend is up." : "Below its 200-day average: the long-term trend is down.");
  if (price != null && sma50 != null) add("timing", price >= sma50 ? 1 : -1, price >= sma50 ? "Above its 50-day average: the medium-term trend is up." : "Below its 50-day average: the medium-term trend is down.");
  const rsi = ind(a, "rsi14");
  if (rsi != null) {
    if (rsi > 75) add("timing", -1, `Overbought (RSI ${num(rsi, 0)}): a pullback is likely.`);
    else if (rsi >= 50) add("timing", 1, `Momentum is healthy (RSI ${num(rsi, 0)}).`);
    else if (rsi < 30) add("timing", 0, `Oversold (RSI ${num(rsi, 0)}): it may bounce, but it has fallen hard.`);
    else if (rsi < 45) add("timing", -1, `Momentum is weak (RSI ${num(rsi, 0)}).`);
  }
  if (a.setup.score >= 4) add("timing", 1, `${a.setup.score} of ${a.setup.max} timing checks pass.`);
  else if (a.setup.score <= 1) add("timing", -1, `Only ${a.setup.score} of ${a.setup.max} timing checks pass.`);
  const month = a.trend.changes["1M"];
  if (month != null) {
    if (month >= 3) add("timing", 1, `Up ${num(month, 1)}% in a month.`);
    else if (month <= -5) add("timing", -1, `Down ${num(Math.abs(month), 1)}% in a month.`);
  }
  const m3 = rs?.m3;
  if (m3) {
    const said = `${pct(m3.stockPct, 1)} in 3 months against ${pct(m3.indexPct, 1)} for the DSEX index`;
    if (m3.diffPts >= 5) add("timing", 1, `Beating the market: ${said}.`);
    else if (m3.diffPts <= -5) add("timing", -1, `Lagging the market: ${said}.`);
    else add("timing", 0, `Moving with the market: ${said}.`);
  }
  const where = a.candle_story?.where;
  if (where === "inside_buy_zone") add("timing", 1, "Price is inside its buy zone.");
  else if (where === "below_stop") add("timing", -2, "Price is below its stop level.");

  // ---- risk (negative points only)
  const ff = a.fundamentals.free_float_pct;
  if (ff != null && ff < 15) add("risk", -1, `Only ${num(ff, 0)}% of shares are freely traded: large holders dominate, so the price can move on small volume.`);
  const turnover = avgTurnoverMn(a);
  if (turnover != null) {
    if (turnover < 1) add("risk", -2, `Thinly traded: about Tk ${num(turnover, 1)} mn a day, so it can be hard to sell quickly.`);
    else if (turnover < 5) add("risk", -1, `Lightly traded: about Tk ${num(turnover, 1)} mn a day.`);
  }
  const atr = ind(a, "atr14");
  if (atr != null && price) {
    const swing = (atr / price) * 100;
    if (swing > 5) add("risk", -1, `Swings about ${num(swing, 1)}% on a typical day.`);
  }
  if (de != null && de > 1.5 && !financial) add("risk", -1, `Heavy borrowing: debt is ${num(de, 1)}× equity.`);
  if (growth != null && growth <= -15) add("risk", -1, `Earnings are falling (${pct(growth, 0)} last year).`);
  if (roe != null && roe < 0) add("risk", -2, "The company is loss-making.");
  if ((a.fundamentals.category ?? "").toUpperCase() === "Z") add("risk", -2, "Z category: a weaker compliance record.");
  return out;
}

const sum = (e: readonly Evidence[], tile: TileKey) => e.filter((x) => x.tile === tile).reduce((n, x) => n + x.points, 0);
const has = (e: readonly Evidence[], tile: TileKey) => e.some((x) => x.tile === tile);

function rate(tile: TileKey, e: readonly Evidence[]): { rating: string; tone: Tone } {
  const s = sum(e, tile);
  if (tile === "risk") return s === 0 ? { rating: "Low", tone: "up" } : s >= -2 ? { rating: "Moderate", tone: "warn" } : { rating: "High", tone: "dn" };
  if (!has(e, tile)) return { rating: "Not enough data", tone: "mute" };
  if (tile === "quality") return s >= 4 ? { rating: "Strong", tone: "up" } : s >= 2 ? { rating: "Good", tone: "up" } : s >= 0 ? { rating: "Mixed", tone: "warn" } : { rating: "Weak", tone: "dn" };
  if (tile === "value") return s >= 3 ? { rating: "Cheap", tone: "up" } : s >= 1 ? { rating: "Fair to cheap", tone: "up" } : s === 0 ? { rating: "Fair", tone: "mute" } : s === -1 ? { rating: "Fair to expensive", tone: "warn" } : { rating: "Expensive", tone: "dn" };
  return s >= 3 ? { rating: "Favourable", tone: "up" } : s >= 1 ? { rating: "Leaning positive", tone: "up" } : s === 0 ? { rating: "Neutral", tone: "mute" } : s >= -2 ? { rating: "Leaning negative", tone: "warn" } : { rating: "Unfavourable", tone: "dn" };
}

function facts(tile: TileKey, a: Analysis, c: Company | undefined, pe: PeContext | null, rs: RelativeStrength | null): Fact[] {
  const f = (label: string, v: string | null): Fact[] => (v == null ? [] : [{ label, value: v }]);
  const n = (v: number | null | undefined, d = 1, unit = "") => (v == null ? null : `${num(v, d)}${unit}`);
  if (tile === "quality") {
    const g = ratio(c, "eps_growth");
    const financial = FINANCIAL.test(a.fundamentals.sector ?? "");
    return [...f("Return on equity", n(ratio(c, "roe"), 1, "%")), ...f("Net margin", n(ratio(c, "net_margin"), 1, "%")), ...(financial ? [] : f("Debt / equity", n(ratio(c, "debt_to_equity") ?? ratio(c, "loan_to_equity"), 2, "×"))), ...f("EPS last year", g == null ? null : pct(g, 0))];
  }
  if (tile === "value") {
    const fair = fairValueReading(a);
    const dy = dividendYield(a).value;
    return [...f("P/E", n(a.fundamentals.pe, 1)), ...f("Market median P/E", n(pe?.marketMedian, 1)), ...f("Market P/E, size-weighted", n(pe?.marketWeighted, 1)), ...f("Price / book", n(ratio(c, "pb"), 2, "×")), ...f("Dividend yield", n(dy, 1, "%")), ...f("Median fair value", fair ? num(fair.median) : null)];
  }
  if (tile === "timing") {
    const vs = a.trend.vs_ma["SMA200"];
    return [...f("Vs 200-day average", vs ? pct(vs.pct, 1) : null), ...f("RSI (14)", n(ind(a, "rsi14"), 0)), ...f("1 month", a.trend.changes["1M"] == null ? null : pct(a.trend.changes["1M"], 1)), ...f("Vs DSEX, 3 months", rs?.m3 ? `${rs.m3.diffPts >= 0 ? "+" : "−"}${num(Math.abs(rs.m3.diffPts), 1)} pts` : null), ...f("Timing checks passed", `${a.setup.score} of ${a.setup.max}`)];
  }
  const atr = ind(a, "atr14");
  return [...f("Free float", n(a.fundamentals.free_float_pct, 0, "%")), ...f("Daily turnover", (avgTurnoverMn(a) == null ? null : `Tk ${num(avgTurnoverMn(a), 1)} mn`)), ...f("Typical daily swing", atr != null && a.price.ltp ? n((atr / a.price.ltp) * 100, 1, "%") : null), ...f("Credit rating", c?.profile.credit_rating?.long_term ?? null)];
}

/** Earnings per share by year, oldest first, last eight years: the trend a one-year growth figure hides. */
export function epsTrend(c: Company | undefined): TileReading["trend"] {
  const rows = (c?.per_share_history ?? []).filter((r) => r.eps != null).sort((x, y) => (x.period_end < y.period_end ? -1 : 1)).slice(-8);
  if (rows.length < 3) return undefined;
  const values = rows.map((r) => r.eps as number);
  return { label: "Earnings per share by year", values, first: rows[0]?.period_end.slice(0, 4) ?? "", last: rows.at(-1)?.period_end.slice(0, 4) ?? "" };
}

const TITLES: Record<TileKey, string> = { quality: "Business quality", value: "Value", timing: "Timing", risk: "Risk" };

function verdict(tiles: readonly TileReading[]): string {
  const r = (k: TileKey) => tiles.find((t) => t.key === k)?.rating ?? "";
  const q = { Strong: "A strong business", Good: "A decent business", Mixed: "A business with mixed results", Weak: "A weak business" }[r("quality")] ?? "";
  const v = { Cheap: "priced cheaply", "Fair to cheap": "priced a little below fair value", Fair: "priced about right", "Fair to expensive": "priced a little above fair value", Expensive: "priced well above fair value" }[r("value")] ?? "";
  const t = {
    Favourable: "and the timing looks good",
    "Leaning positive": "with the timing leaning positive",
    Neutral: "with no clear timing signal",
    "Leaning negative": "but the trend is leaning against it",
    Unfavourable: "but the trend and momentum are weak right now",
  }[r("timing")] ?? "";
  const head = [q, v].filter(Boolean).join(", ");
  const text = [head, t].filter(Boolean).join(head && t ? ", " : "");
  const risk = r("risk") === "High" ? " Risk is high; see below." : "";
  return text ? `${text.charAt(0).toUpperCase()}${text.slice(1)}.${risk}` : "There is not enough data for a reading yet.";
}

function actionLine(a: Analysis): string {
  const z = buyZone(a);
  const zone = `${num(z.low)}–${num(z.high)}`;
  switch (a.candle_story?.where) {
    case "inside_buy_zone":
      return `Price is inside the buy zone (${zone}).`;
    case "above_buy_zone":
      return `Wait for a pullback into ${zone} before buying.`;
    case "below_buy_zone":
      return `Price is below the buy zone (${zone}); wait for it to steady.`;
    case "below_stop":
      return `Price is below its stop (${num(a.setup.plan.stop)}): avoid for now.`;
    default:
      return `${actionSentence(a.signal.action)}.`;
  }
}

export function buildSummary(a: Analysis, c: Company | undefined, pe: PeContext | null, rs: RelativeStrength | null = null): Summary {
  const e = evidence(a, c, pe, rs);
  const tiles: TileReading[] = (["quality", "value", "timing", "risk"] as const).map((key) => ({
    key,
    title: TITLES[key],
    ...rate(key, e),
    evidence: e.filter((x) => x.tile === key),
    facts: facts(key, a, c, pe, rs),
    ...(key === "quality" ? { trend: epsTrend(c) } : {}),
  }));
  const pro = e.filter((x) => x.points > 0).sort((x, y) => y.points - x.points);
  const con = e.filter((x) => x.points < 0).sort((x, y) => x.points - y.points);
  return {
    tiles,
    verdict: verdict(tiles),
    actionLine: actionLine(a),
    reasonsFor: pro.slice(0, 3).map((x) => x.text),
    reasonsAgainst: con.slice(0, 3).map((x) => x.text),
  };
}

/** How the ratings are reached, for the "How this is rated" note. */
export const HOW_RATED: readonly string[] = [
  "Each rating adds up small rules, shown as the ✓ and ✗ lines on each tile. Nothing else goes into it.",
  "Business quality: return on equity, net margin, borrowing (not for banks and financials), earnings growth, dividend record and credit rating.",
  "Value: median fair value against the price, P/E against the sector median (or the market median when the sector has fewer than 5 companies; a share also has to be at or below the size-weighted market P/E to count as cheap on P/E), and dividend yield.",
  "Timing: price against the 50 and 200-day averages, RSI, how many of the six setup checks pass, the last month's move, whether it is beating or lagging the DSEX index over 3 months (by 5 points or more), and whether price is in its buy zone.",
  "Risk: free float under 15%, thin trading, large daily swings, heavy borrowing, falling earnings, losses and Z category. One or two flags read as Moderate, three or more as High.",
  "These are rules of thumb for orientation. They have not been tested on past prices the way the Picks buckets have, and they are not advice.",
];
