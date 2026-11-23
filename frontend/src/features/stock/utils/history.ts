import type { DailyBar } from "../schemas/candles";

export interface TodayBar {
  day: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** Today's session from the live quote on top of the saved history (which ends yesterday): replaces a same-day
 * bar, appends a newer one, ignores an older one. Trades are not in the live quote, so they stay unknown. */
export function withToday(bars: readonly DailyBar[], live: TodayBar | null | undefined): readonly DailyBar[] {
  if (!live || !(live.volume > 0)) return bars;
  const last = bars.at(-1);
  const today: DailyBar = { ...live, trades: null };
  if (!last || live.day > last.day) return [...bars, today];
  return live.day === last.day ? [...bars.slice(0, -1), { ...today, trades: last.trades }] : bars;
}

export interface PriceRow extends DailyBar {
  change: number | null;
  changePct: number | null;
}

export interface PriceTable {
  rows: PriceRow[]; // newest first
  avgPrice: number;
  maxPrice: number;
  minPrice: number;
  avgVolume: number;
  maxVolume: number;
  minVolume: number;
  change: number;
  changePct: number | null;
}

/** The last `days` trading days (bars are oldest first), each with its change on the previous close. */
export function priceTable(bars: readonly DailyBar[], days: number): PriceTable | null {
  const window = bars.slice(-days);
  const first = window[0];
  const last = window.at(-1);
  if (!first || !last) return null;
  const rows = window
    .map((b, i): PriceRow => {
      const prev = i > 0 ? window[i - 1] : bars[bars.length - window.length - 1];
      const change = prev ? b.close - prev.close : null;
      return { ...b, change, changePct: prev && prev.close ? (change! / prev.close) * 100 : null };
    })
    .reverse();
  const closes = window.map((b) => b.close);
  const vols = window.map((b) => b.volume);
  const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);
  return {
    rows,
    avgPrice: sum(closes) / closes.length,
    maxPrice: Math.max(...closes),
    minPrice: Math.min(...closes),
    avgVolume: sum(vols) / vols.length,
    maxVolume: Math.max(...vols),
    minVolume: Math.min(...vols),
    change: last.close - first.close,
    changePct: first.close ? ((last.close - first.close) / first.close) * 100 : null,
  };
}

export interface SeasonStat {
  label: string;
  n: number; // periods observed
  avgPct: number;
  winPct: number; // share of periods that closed up
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]; // DSE trades Sun–Thu

function summarise(label: string, returns: number[]): SeasonStat {
  const n = returns.length;
  return {
    label,
    n,
    avgPct: n ? returns.reduce((a, b) => a + b, 0) / n : 0,
    winPct: n ? (returns.filter((r) => r > 0).length / n) * 100 : 0,
  };
}

/** Average calendar-month return: month-end close vs the previous month-end close. The first (partial) month and
 * the current, still-running month are left out so every sample is a full month. */
export function monthlySeasonality(bars: readonly DailyBar[]): SeasonStat[] {
  const ends = new Map<string, number>(); // "YYYY-MM" -> last close (bars are oldest first)
  for (const b of bars) ends.set(b.day.slice(0, 7), b.close);
  const keys = [...ends.keys()];
  const byMonth: number[][] = Array.from({ length: 12 }, () => []);
  for (let i = 1; i < keys.length - 1; i++) {
    const prev = ends.get(keys[i - 1]!)!;
    const cur = ends.get(keys[i]!)!;
    if (prev) byMonth[Number(keys[i]!.slice(5, 7)) - 1]!.push((cur / prev - 1) * 100);
  }
  return MONTHS.map((m, i) => summarise(m, byMonth[i]!));
}

/** Average close-to-close return by weekday. */
export function weekdaySeasonality(bars: readonly DailyBar[]): SeasonStat[] {
  const by: number[][] = Array.from({ length: 7 }, () => []);
  for (let i = 1; i < bars.length; i++) {
    const prev = bars[i - 1]!.close;
    if (!prev) continue;
    const dow = (new Date(`${bars[i]!.day}T00:00:00Z`).getUTCDay() + 6) % 7; // Mon = 0
    by[dow]!.push((bars[i]!.close / prev - 1) * 100);
  }
  return WEEKDAYS.map((d, i) => summarise(d, by[i]!)).filter((s) => s.n > 0);
}
