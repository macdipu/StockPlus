import { describe, expect, it } from "vitest";
import { envelope } from "@/shared/api";
import analysis from "@/shared/api/__fixtures__/analysis.json";
import intraday from "@/shared/api/__fixtures__/intraday.json";
import technicals from "@/shared/api/__fixtures__/technicals.json";
import vpa from "@/shared/api/__fixtures__/vpa.json";
import { z } from "zod";
import { analysisSchema, intradayBarSchema, technicalBarSchema, vpaRowSchema } from "./analysis";

/** These fixtures are real responses captured from the running API: if a backend DTO changes shape, this fails. */
describe("stock schemas vs. real API responses", () => {
  it("analysis", () => {
    const r = envelope(analysisSchema).safeParse(analysis);
    expect(r.success, JSON.stringify(r.error?.issues, null, 1)).toBe(true);
    if (r.success) {
      expect(r.data.data.symbol).toBe("GP");
      expect(r.data.data.setup.plan.entry_zone).toHaveLength(2);
    }
  });

  it("technicals", () => {
    const r = envelope(z.array(technicalBarSchema)).safeParse(technicals);
    expect(r.success, JSON.stringify(r.error?.issues)).toBe(true);
  });

  it("vpa", () => {
    expect(z.array(vpaRowSchema).safeParse(vpa.data).success).toBe(true);
    expect(Object.keys(vpa.meta.legend).length).toBeGreaterThan(3);
  });

  it("intraday", () => {
    expect(z.array(intradayBarSchema).safeParse(intraday.data).success).toBe(true);
  });

  it("rejects a drifted analysis (missing signal.action)", () => {
    const drifted = structuredClone(analysis) as { data: { signal: { action?: string } } };
    delete drifted.data.signal.action;
    expect(envelope(analysisSchema).safeParse(drifted).success).toBe(false);
  });
});
