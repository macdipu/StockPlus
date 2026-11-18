/** Small, pure indicator maths for the chart's extra panes (the server serves the daily overlays). */

export function ema(values: readonly number[], period: number): (number | null)[] {
  const k = 2 / (period + 1);
  const out: (number | null)[] = [];
  let prev: number | null = null;
  values.forEach((v, i) => {
    if (i < period - 1) {
      out.push(null);
      return;
    }
    if (prev === null) {
      const seed = values.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0) / period;
      prev = seed;
    } else {
      prev = v * k + prev * (1 - k);
    }
    out.push(prev);
  });
  return out;
}

/** Wilder's RSI. */
export function rsi(closes: readonly number[], period = 14): (number | null)[] {
  const out: (number | null)[] = closes.map(() => null);
  if (closes.length <= period) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i]! - closes[i - 1]!;
    gain += Math.max(d, 0);
    loss += Math.max(-d, 0);
  }
  gain /= period;
  loss /= period;
  out[period] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i]! - closes[i - 1]!;
    gain = (gain * (period - 1) + Math.max(d, 0)) / period;
    loss = (loss * (period - 1) + Math.max(-d, 0)) / period;
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return out;
}

export interface MacdPoint {
  macd: number | null;
  signal: number | null;
  hist: number | null;
}

export function macd(closes: readonly number[], fast = 12, slow = 26, signal = 9): MacdPoint[] {
  const f = ema(closes, fast);
  const s = ema(closes, slow);
  const line = closes.map((_, i) => (f[i] != null && s[i] != null ? f[i]! - s[i]! : null));
  const start = line.findIndex((v) => v != null);
  const sig: (number | null)[] = line.map(() => null);
  if (start >= 0) {
    const tail = ema(line.slice(start) as number[], signal);
    tail.forEach((v, j) => (sig[start + j] = v));
  }
  return line.map((m, i) => ({ macd: m, signal: sig[i] ?? null, hist: m != null && sig[i] != null ? m - sig[i]! : null }));
}
