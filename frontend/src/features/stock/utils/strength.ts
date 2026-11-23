/** How a share has moved compared with the market index over the same stretch. Pure: bars in, numbers out. */

export interface DayClose {
  day: string; // YYYY-MM-DD
  close: number;
}

export interface Relative {
  stockPct: number;
  indexPct: number;
  /** Stock return minus index return, in percentage points: positive means it beat the market. */
  diffPts: number;
  from: string;
  to: string;
}

/** The latest close on or before `day`, or null when the series starts after it. */
function closeOnOrBefore(bars: readonly DayClose[], day: string): DayClose | null {
  let found: DayClose | null = null;
  for (const b of bars) {
    if (b.day <= day) found = b;
    else break;
  }
  return found;
}

/** Return of the share over its last `sessions` trading sessions, against the index over the same dates. Both series
 * are oldest first. The index is read on or before each date, because it may not publish on every day the share trades. */
export function relativeStrength(stock: readonly DayClose[], index: readonly DayClose[], sessions: number): Relative | null {
  const last = stock.at(-1);
  const start = stock[stock.length - 1 - sessions];
  if (!last || !start || start.close <= 0) return null;
  const idxEnd = closeOnOrBefore(index, last.day);
  const idxStart = closeOnOrBefore(index, start.day);
  if (!idxEnd || !idxStart || idxStart.close <= 0) return null;
  const stockPct = (last.close / start.close - 1) * 100;
  const indexPct = (idxEnd.close / idxStart.close - 1) * 100;
  return { stockPct, indexPct, diffPts: stockPct - indexPct, from: start.day, to: last.day };
}

/** The index's chart payload (unix seconds and closes) as dated closes. */
export function indexCloses(time: readonly number[], close: readonly number[]): DayClose[] {
  const out: DayClose[] = [];
  time.forEach((t, i) => {
    const c = close[i];
    if (c != null) out.push({ day: new Date(t * 1000).toISOString().slice(0, 10), close: c });
  });
  return out;
}

/** A polyline for a tiny trend chart: x spread evenly, y scaled to the range, higher values drawn higher. */
export function sparkPoints(values: readonly number[], width: number, height: number, pad = 3): string {
  if (values.length < 2) return "";
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  return values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (width - 2 * pad);
      const y = height - pad - ((v - lo) / span) * (height - 2 * pad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}
