import { describe, expect, it } from "vitest";
import { ema, macd, rsi } from "./indicators";

describe("indicators", () => {
  it("ema seeds with the simple average then smooths", () => {
    const out = ema([1, 2, 3, 4, 5], 3);
    expect(out.slice(0, 2)).toEqual([null, null]);
    expect(out[2]).toBe(2);
    expect(out[3]).toBeCloseTo(3);
    expect(out[4]).toBeCloseTo(4);
  });

  it("rsi is 100 on a straight rise and 0 on a straight fall", () => {
    const up = Array.from({ length: 20 }, (_, i) => 10 + i);
    expect(rsi(up).at(-1)).toBe(100);
    const down = [...up].reverse();
    expect(rsi(down).at(-1)).toBe(0);
    expect(rsi(up)[13]).toBeNull();
  });

  it("macd histogram is macd minus signal", () => {
    const closes = Array.from({ length: 60 }, (_, i) => 100 + Math.sin(i / 4) * 5);
    const last = macd(closes).at(-1)!;
    expect(last.macd).not.toBeNull();
    expect(last.hist).toBeCloseTo(last.macd! - last.signal!);
  });
});
