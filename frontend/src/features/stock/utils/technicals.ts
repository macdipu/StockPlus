import { num, pct } from "@/shared/lib/format";
import type { Analysis } from "../schemas/analysis";

/** Plain-language readings of the technical numbers. Pure: no fetching, no rendering. */

export type Tone = "up" | "dn" | "mute";

export interface ReadingLine {
  topic: string;
  text: string;
  tone: Tone;
}

export interface TechnicalReading {
  headline: string;
  lines: ReadingLine[];
}

export function rsiWord(rsi: number): { word: string; tone: Tone } {
  if (rsi < 30) return { word: "oversold", tone: "mute" };
  if (rsi < 45) return { word: "weak", tone: "dn" };
  if (rsi < 55) return { word: "neutral", tone: "mute" };
  if (rsi <= 70) return { word: "healthy", tone: "up" };
  return { word: "overbought", tone: "dn" };
}

const ind = (a: Analysis, k: string): number | null => a.indicators[k] ?? null;
const vs = (a: Analysis, k: string): number | null => a.trend.vs_ma[k]?.pct ?? null;
const signed = (v: number) => pct(v, 1);

function trend(a: Analysis): { word: string; line: ReadingLine } | null {
  const p50 = vs(a, "SMA50");
  const p200 = vs(a, "SMA200");
  if (p50 == null || p200 == null) return null;
  if (p50 >= 0 && p200 >= 0) return { word: "trend up", line: { topic: "Trend", tone: "up", text: `Uptrend: price is above its 50-day (${signed(p50)}) and 200-day (${signed(p200)}) averages.` } };
  if (p50 < 0 && p200 < 0) return { word: "trend down", line: { topic: "Trend", tone: "dn", text: `Downtrend: price is below its 50-day (${signed(p50)}) and 200-day (${signed(p200)}) averages.` } };
  const above = p50 >= 0 ? "50-day" : "200-day";
  const below = p50 >= 0 ? "200-day" : "50-day";
  return { word: "trend mixed", line: { topic: "Trend", tone: "mute", text: `Mixed trend: above its ${above} average but below its ${below} average.` } };
}

function momentum(a: Analysis): { word: string; line: ReadingLine } | null {
  const rsi = ind(a, "rsi14");
  if (rsi == null) return null;
  const r = rsiWord(rsi);
  const hist = ind(a, "macd_hist");
  const macd = hist == null ? "" : hist >= 0 ? " MACD is above its signal line, a sign the move is improving." : " MACD is below its signal line, a sign the move is still weakening.";
  const tone: Tone = r.tone === "dn" && (hist ?? 0) < 0 ? "dn" : r.tone === "up" && (hist ?? 0) > 0 ? "up" : "mute";
  return { word: `momentum ${r.word}`, line: { topic: "Momentum", tone, text: `RSI ${num(rsi, 0)} is ${r.word}.${macd}` } };
}

function volume(a: Analysis): { word: string; line: ReadingLine } | null {
  const v = ind(a, "vol_ratio");
  if (v == null) return null;
  if (v < 0.7) return { word: "volume light", line: { topic: "Volume", tone: "mute", text: `Light volume: ${num(v, 2)}× its 20-day average, so today's move carries less weight.` } };
  if (v > 1.5) return { word: "volume heavy", line: { topic: "Volume", tone: "up", text: `Heavy volume: ${num(v, 2)}× its 20-day average, so the move carries more weight.` } };
  return { word: "volume normal", line: { topic: "Volume", tone: "mute", text: `Normal volume: ${num(v, 2)}× its 20-day average.` } };
}

/** "2.2% below" or "0.9% above", for a level against the price. */
export function distance(price: number, level: number): string {
  const d = ((level - price) / price) * 100;
  return `${num(Math.abs(d), 1)}% ${d >= 0 ? "above" : "below"}`;
}

/** The technical picture in a headline and four or five plain lines. */
export function technicalReading(a: Analysis): TechnicalReading | null {
  const price = a.price.ltp;
  const t = trend(a);
  const m = momentum(a);
  const v = volume(a);
  const lines: ReadingLine[] = [t?.line, m?.line, v?.line].filter((x): x is ReadingLine => x != null);
  const atr = ind(a, "atr14");
  if (atr != null && price) lines.push({ topic: "Swing", tone: "mute", text: `A typical day moves the price about ${num((atr / price) * 100, 1)}% (ATR ${num(atr)}).` });
  if (price) {
    const nearest = (xs: readonly number[]) => [...xs].sort((x, y) => Math.abs(x - price) - Math.abs(y - price))[0];
    const support = nearest(a.levels.below);
    const resistance = nearest(a.levels.above);
    const parts = [support != null ? `support ${num(support)} (${distance(price, support)})` : null, resistance != null ? `resistance ${num(resistance)} (${distance(price, resistance)})` : null].filter(Boolean);
    if (parts.length) lines.push({ topic: "Levels", tone: "mute", text: `Nearest ${parts.join(" and ")}.` });
  }
  if (lines.length === 0) return null;
  const words = [t?.word, m?.word, v?.word].filter(Boolean) as string[];
  const head = words.join(", ");
  return { headline: head ? `${head.charAt(0).toUpperCase()}${head.slice(1)}.` : "Not enough data for a technical reading.", lines };
}

export interface IndicatorRow {
  label: string;
  value: string;
  reading: string;
  tone: Tone;
}

/** The indicators table with a meaning beside each number. */
export function indicatorRows(a: Analysis): IndicatorRow[] {
  const rows: IndicatorRow[] = [];
  const price = a.price.ltp;
  const rsi = ind(a, "rsi14");
  if (rsi != null) {
    const r = rsiWord(rsi);
    rows.push({ label: "RSI (14)", value: num(rsi, 1), reading: `${r.word.charAt(0).toUpperCase()}${r.word.slice(1)}: ${rsi < 30 ? "fallen hard, may bounce" : rsi < 45 ? "sellers have the upper hand" : rsi < 55 ? "no clear lean" : rsi <= 70 ? "buyers have the upper hand" : "stretched, a pullback is likely"}`, tone: r.tone });
  }
  const hist = ind(a, "macd_hist");
  if (ind(a, "macd") != null) rows.push({ label: "MACD / signal / histogram", value: `${num(ind(a, "macd"))} / ${num(ind(a, "macd_signal"))} / ${num(hist)}`, reading: hist == null ? "" : hist >= 0 ? "Above its signal line: momentum improving" : "Below its signal line: momentum weakening", tone: hist == null ? "mute" : hist >= 0 ? "up" : "dn" });
  const e9 = ind(a, "ema9");
  const e21 = ind(a, "ema21");
  if (e9 != null && e21 != null) rows.push({ label: "EMA 9 / 21", value: `${num(e9)} / ${num(e21)}`, reading: e9 >= e21 ? "Short average above the longer one: short-term up" : "Short average below the longer one: short-term down", tone: e9 >= e21 ? "up" : "dn" });
  const s20 = ind(a, "sma20");
  const s50 = ind(a, "sma50");
  const s200 = ind(a, "sma200");
  if (price != null && s20 != null && s50 != null && s200 != null) {
    const above = [s20, s50, s200].filter((s) => price >= s).length;
    rows.push({ label: "SMA 20 / 50 / 200", value: `${num(s20)} / ${num(s50)} / ${num(s200)}`, reading: `Price is above ${above} of the 3 averages`, tone: above === 3 ? "up" : above === 0 ? "dn" : "mute" });
  }
  const lo = ind(a, "bb_lower");
  const hi = ind(a, "bb_upper");
  if (price != null && lo != null && hi != null) {
    rows.push({ label: "Bollinger bands (20, 2)", value: `${num(lo)} – ${num(hi)}`, reading: price < lo ? "Below the lower band: stretched down" : price > hi ? "Above the upper band: stretched up" : `Inside the bands, ${num(((price - lo) / (hi - lo)) * 100, 0)}% of the way up`, tone: price < lo ? "mute" : "mute" });
  }
  const atr = ind(a, "atr14");
  if (atr != null && price) rows.push({ label: "ATR (14)", value: num(atr), reading: `About ${num((atr / price) * 100, 1)}% of the price on a typical day`, tone: "mute" });
  const vr = ind(a, "vol_ratio");
  if (vr != null) rows.push({ label: "Volume vs 20-day average", value: `${num(vr, 2)}×`, reading: vr < 0.7 ? "Light" : vr > 1.5 ? "Heavy" : "Normal", tone: "mute" });
  return rows;
}
