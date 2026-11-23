import { describe, expect, it } from "vitest";
import { companySchema, type Company } from "@/features/company";
import analysisFixture from "@/shared/api/__fixtures__/analysis.json";
import companyFixture from "@/shared/api/__fixtures__/company.json";
import { analysisSchema, type Analysis } from "../schemas/analysis";
import { fitReading, methodFit, scaleFor } from "./valuation";

const base = analysisSchema.parse((analysisFixture as { data: unknown }).data);
const company = companySchema.parse((companyFixture as { data: unknown }).data);
const withRatios = (r: Record<string, number>, flags: Company["flags"] = []): Company => ({
  ...company,
  ratios: Object.entries(r).map(([key, value]) => ({ key, label: key, value, unit: "", basis: "" })),
  flags,
});
const names = ["P/E 15x", "P/E 20x", "P/E 25x", "P/B 1.5x", "P/B 2.0x", "P/B 3.0x", "Graham Number", "Dividend discount", "DCF (bear)", "DCF (base)", "DCF (bull)"];
const fair = [328.5, 438, 547.5, 62.24, 82.98, 124.47, 142.98, 279.5, 171.87, 307.27, 510.3];
const analysis = (over: Partial<Analysis["fundamentals"]> = {}): Analysis => ({
  ...base,
  price: { ...base.price, ltp: 226.8 },
  fundamentals: { ...base.fundamentals, sector: "Telecom", eps_ttm: 21.9, nav: 41.49, dividend_per_share: 21.5, ...over },
  valuation: { ...base.valuation, rows: names.map((method, i) => ({ method, inputs: "", fair_value: fair[i] as number, gap_pct: null })) },
});
const fitOf = (a: Analysis, c: Company | undefined, method: string) => fitReading(a, c)?.fits.find((f) => f.method === method)?.fit;

describe("a high-return business (GP-like)", () => {
  const c = withRatios({ roe: 52.8, eps_growth: -19 }, [{ tone: "good", text: "Paid a cash dividend in 5 of the last 5 years." }]);
  const a = analysis();
  it("sets aside the book-value methods, and higher P/E multiples when earnings are falling", () => {
    expect(fitOf(a, c, "P/B 1.5x")).toBe("no");
    expect(fitOf(a, c, "Graham Number")).toBe("no");
    expect(fitOf(a, c, "P/E 25x")).toBe("partly");
    expect(fitOf(a, c, "P/E 15x")).toBe("yes");
    expect(fitOf(a, c, "Dividend discount")).toBe("yes");
    expect(fitOf(a, c, "DCF (base)")).toBe("yes");
  });
  it("takes its headline from the methods that fit, and says why the rest were left out", () => {
    const r = fitReading(a, c);
    expect(r?.values).toEqual([171.87, 279.5, 307.27, 328.5, 510.3]);
    expect(r?.median).toBeCloseTo(307.27);
    expect(r?.gapPct).toBeCloseTo((307.27 / 226.8 - 1) * 100);
    expect(r?.text).toBe("Of the 11 methods, 5 fit this share. Their median fair value is 307.27 (+35% against the price), within a range of 171.87 to 510.30.");
    expect(r?.excluded.map((x) => x.method)).toContain("P/B 3.0x");
    expect(r?.excluded.find((x) => x.method === "P/B 3.0x")?.why).toMatch(/Return on equity is 52\.8%/);
  });
});

describe("other kinds of share", () => {
  it("uses book value for a bank", () => {
    expect(fitOf(analysis({ sector: "Bank" }), withRatios({ roe: 12 }), "P/B 1.5x")).toBe("yes");
  });
  it("does not hold a bank to a 15x earnings multiple or a rich 3x book multiple", () => {
    const bank = analysis({ sector: "Bank" });
    const c = withRatios({ roe: 12 });
    expect(fitOf(bank, c, "P/E 15x")).toBe("partly");
    expect(fitOf(bank, c, "P/B 3.0x")).toBe("partly");
    expect(fitOf(bank, c, "P/B 2.0x")).toBe("yes");
  });
  it("calls a modest-return company's book multiples fair", () => {
    expect(fitOf(analysis(), withRatios({ roe: 6 }), "P/B 2.0x")).toBe("yes");
    expect(fitOf(analysis(), withRatios({ roe: 14 }), "P/B 2.0x")).toBe("partly");
  });
  it("sets aside earnings-based methods for a loss-maker", () => {
    const a = analysis({ eps_ttm: -3 });
    const c = withRatios({ roe: -2 });
    expect(fitOf(a, c, "P/E 15x")).toBe("no");
    expect(fitOf(a, c, "DCF (base)")).toBe("no");
    expect(fitReading(a, c)?.values.length).toBeGreaterThanOrEqual(3); // book value still gives a view
  });
  it("gives no headline when nothing can be valued", () => {
    expect(fitReading(analysis({ eps_ttm: -3, nav: -1, dividend_per_share: null }), withRatios({ roe: -2 }))).toBeNull();
  });
  it("skips the dividend method when no dividend is paid", () => {
    expect(fitOf(analysis({ dividend_per_share: null }), withRatios({ roe: 10 }), "Dividend discount")).toBe("no");
  });
  it("treats a patchy dividend record as only a partial fit", () => {
    const c = withRatios({ roe: 10 }, [{ tone: "warn", text: "Paid a cash dividend in 2 of the last 5 years." }]);
    expect(fitOf(analysis(), c, "Dividend discount")).toBe("partly");
  });
});

describe("methodFit for an unknown method", () => {
  it("does not exclude what it does not understand", () => {
    expect(methodFit("Something new", { financial: false, roe: null, eps: 1, epsGrowth: null, dps: null, record: null, nav: 1 }).fit).toBe("yes");
  });
});


describe("scaleFor", () => {
  it("puts every value and the price on one 0 to 100 scale, in order", () => {
    const at = scaleFor([100, 200, 400], 150);
    expect(at(100)).toBeLessThan(at(150));
    expect(at(150)).toBeLessThan(at(400));
    expect(at(400)).toBeLessThanOrEqual(100);
    expect(at(1e9)).toBe(100);
    expect(at(-5)).toBe(0);
  });
});
