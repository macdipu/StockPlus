import { describe, expect, it } from "vitest";
import { envelope } from "@/shared/api";
import chart from "@/shared/api/__fixtures__/chart.json";
import { chartSchema } from "./chart";

describe("chart schema vs. a real API response", () => {
  it("parses, and every series has one value per candle", () => {
    const r = envelope(chartSchema).safeParse(chart);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
    const d = r.data?.data;
    expect(d?.indicators.length).toBeGreaterThan(0);
    for (const i of d?.indicators ?? []) for (const s of Object.values(i.series)) expect(s).toHaveLength(d?.candles.time.length ?? -1);
  });
});
