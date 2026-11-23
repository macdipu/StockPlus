import { describe, expect, it } from "vitest";
import { companySchema, type Company } from "@/features/company";
import analysisFixture from "@/shared/api/__fixtures__/analysis.json";
import companyFixture from "@/shared/api/__fixtures__/company.json";
import { analysisSchema, type Analysis } from "../schemas/analysis";
import { avgTurnoverMn, buildSummary, buyZone, epsTrend, evidence, type PeContext, type RelativeStrength } from "./summary";

const base = analysisSchema.parse((analysisFixture as { data: unknown }).data);
const company = companySchema.parse((companyFixture as { data: unknown }).data);

const withRatios = (r: Record<string, number>, flags: Company["flags"] = []): Company => ({
  ...company,
  ratios: Object.entries(r).map(([key, value]) => ({ key, label: key, value, unit: "", basis: "" })),
  flags,
  profile: { ...company.profile, credit_rating: null },
});
const ev = (a: Analysis, c: Company | undefined, pe: PeContext | null = null) => evidence(a, c, pe);
const points = (e: ReturnType<typeof evidence>, tile: string) => e.filter((x) => x.tile === tile).reduce((n, x) => n + x.points, 0);
const tile = (a: Analysis, c: Company | undefined, key: string, pe: PeContext | null = null) => buildSummary(a, c, pe).tiles.find((t) => t.key === key);

describe("business quality", () => {
  it("rates a high-return, low-debt, growing, dividend-paying business Strong, each rule with its number", () => {
    const c = withRatios({ roe: 25, net_margin: 20, debt_to_equity: 0.2, eps_growth: 12 }, [{ tone: "good", text: "Paid a cash dividend in 5 of the last 5 years." }]);
    const t = tile(base, c, "quality");
    expect(t?.rating).toBe("Strong");
    expect(t?.evidence.map((x) => x.text).join(" ")).toMatch(/Return on equity 25\.0%.*Net margin 20\.0%.*debt is 0\.2×.*grew 12%.*5 of the last 5 years/);
  });
  it("rates a loss-making, indebted business Weak", () => {
    const t = tile(base, withRatios({ roe: -4, net_margin: -2, debt_to_equity: 4 }), "quality");
    expect(t?.rating).toBe("Weak");
  });
  it("does not count borrowing against a bank or other financial", () => {
    const bank = { ...base, fundamentals: { ...base.fundamentals, sector: "Bank" } };
    const e = ev(bank, withRatios({ debt_to_equity: 9 }));
    expect(e.some((x) => /borrowing/i.test(x.text))).toBe(false);
  });
  it("says there is not enough data when no company data loaded", () => {
    expect(tile(base, undefined, "quality")?.rating).toBe("Not enough data");
  });
});

describe("value", () => {
  const price = (ltp: number, median: number): Analysis => ({
    ...base,
    price: { ...base.price, ltp },
    fundamentals: { ...base.fundamentals, pe: null, eps_ttm: 5, dividend_per_share: null, dividend_yield_pct: null },
    valuation: { ...base.valuation, median_fair_value: median, rows: [median * 0.8, median, median * 1.2].map((v, i) => ({ method: `m${i}`, inputs: "", fair_value: v, gap_pct: null })) },
  });
  it("is Cheap when the median fair value is well above the price, Expensive when well below", () => {
    expect(tile(price(100, 140), undefined, "value")?.rating).toBe("Fair to cheap");
    expect(tile(price(100, 100), undefined, "value")?.rating).toBe("Fair");
    expect(tile(price(100, 50), undefined, "value")?.rating).toBe("Expensive");
    expect(points(ev(price(100, 150), undefined), "value")).toBeGreaterThan(0);
    expect(points(ev(price(100, 60), undefined), "value")).toBeLessThan(0);
  });
  it("compares P/E with the sector median when the sector has enough companies, else with the market", () => {
    const a = { ...price(100, 100), fundamentals: { ...price(100, 100).fundamentals, pe: 6 } };
    const big: PeContext = { marketMedian: 20, sector: { name: "Textile", companies: 30, median: 18 } };
    const tiny: PeContext = { marketMedian: 20, sector: { name: "Telecom", companies: 3, median: 5 } };
    expect(ev(a, undefined, big).find((x) => /P\/E/.test(x.text))?.text).toContain("Textile sector median of 18.0");
    expect(ev(a, undefined, tiny).find((x) => /P\/E/.test(x.text))?.text).toContain("market median of 20.0");
  });
  it("calls a loss-maker out instead of showing a P/E", () => {
    const a = { ...base, fundamentals: { ...base.fundamentals, pe: null, eps_ttm: -2 } };
    expect(ev(a, undefined).some((x) => /Loss-making/.test(x.text))).toBe(true);
  });
});

describe("timing", () => {
  const trend = (price: number, sma50: number, sma200: number, rsi: number): Analysis => ({
    ...base,
    price: { ...base.price, ltp: price },
    indicators: { ...base.indicators, sma50, sma200, rsi14: rsi },
    trend: { ...base.trend, changes: { ...base.trend.changes, "1M": 0 } },
    setup: { ...base.setup, score: 3 },
    candle_story: null,
  });
  it("is Favourable above both averages with healthy momentum, Unfavourable below both with weak momentum", () => {
    expect(tile(trend(110, 100, 90, 60), undefined, "timing")?.tone).toBe("up");
    const down = tile(trend(80, 100, 120, 35), undefined, "timing");
    expect(down?.tone).not.toBe("up");
    expect(points(ev(trend(80, 100, 120, 35), undefined), "timing")).toBeLessThan(0);
  });
});

describe("risk", () => {
  it("flags a small free float and thin trading in plain words", () => {
    const a: Analysis = { ...base, price: { ...base.price, ltp: 100 }, fundamentals: { ...base.fundamentals, free_float_pct: 8 }, indicators: { ...base.indicators, vol_avg20: 5_000 } };
    const t = tile(a, undefined, "risk");
    expect(avgTurnoverMn(a)).toBeCloseTo(0.5);
    expect(t?.rating).toBe("High");
    expect(t?.evidence.map((x) => x.text).join(" ")).toMatch(/Only 8% of shares are freely traded.*Thinly traded: about Tk 0\.5 mn a day/);
  });
  it("is Low when nothing is flagged", () => {
    const a: Analysis = { ...base, price: { ...base.price, ltp: 100 }, fundamentals: { ...base.fundamentals, free_float_pct: 50, category: "A" }, indicators: { ...base.indicators, vol_avg20: 1_000_000, atr14: 1 } };
    expect(tile(a, withRatios({ roe: 10, eps_growth: 0 }), "risk")?.rating).toBe("Low");
  });
});

describe("the whole summary", () => {
  it("builds four tiles, a sentence verdict and at most three reasons each way, on the real fixtures", () => {
    const s = buildSummary(base, company, null);
    expect(s.tiles.map((t) => t.key)).toEqual(["quality", "value", "timing", "risk"]);
    expect(s.verdict).toMatch(/\.$/);
    expect(s.reasonsFor.length).toBeLessThanOrEqual(3);
    expect(s.reasonsAgainst.length).toBeLessThanOrEqual(3);
    expect(s.actionLine.length).toBeGreaterThan(10);
  });
  it("says so when there is nothing to base a reading on", () => {
    const empty: Analysis = {
      ...base,
      indicators: {},
      fundamentals: { ...base.fundamentals, pe: null, eps_ttm: null, free_float_pct: null, dividend_per_share: null, dividend_yield_pct: null },
      valuation: { ...base.valuation, rows: [], median_fair_value: null },
      setup: { ...base.setup, score: 2 },
      candle_story: null,
      trend: { ...base.trend, changes: {} },
    };
    expect(buildSummary(empty, undefined, null).verdict).toBe("There is not enough data for a reading yet.");
  });
});

describe("the buy zone", () => {
  const story = (low: number, high: number, where: "above_buy_zone" | "inside_buy_zone"): Analysis => ({
    ...base,
    setup: { ...base.setup, plan: { ...base.setup.plan, entry_zone: [225.65, 226.8] } },
    candle_story: {
      ...(base.candle_story as NonNullable<Analysis["candle_story"]>),
      where,
      annotations: [{ kind: "entry", price: high, price_to: low, label: "BUY ZONE", text: "" }],
    },
  });
  it("is the zone the trade plan and chart show, not the setup plan's tighter range around today's price", () => {
    expect(buyZone(story(221.9, 224.2, "above_buy_zone"))).toEqual({ low: 221.9, high: 224.2 });
  });
  it("falls back to the setup plan's zone when there is no trade plan", () => {
    expect(buyZone({ ...story(1, 2, "above_buy_zone"), candle_story: null })).toEqual({ low: 225.65, high: 226.8 });
  });
  it("is what the action line names, so the page never gives two zones", () => {
    expect(buildSummary(story(221.9, 224.2, "above_buy_zone"), undefined, null).actionLine).toBe("Wait for a pullback into 221.90–224.20 before buying.");
    expect(buildSummary(story(221.9, 224.2, "inside_buy_zone"), undefined, null).actionLine).toBe("Price is inside the buy zone (221.90–224.20).");
  });
});

describe("P/E against the market", () => {
  const a = (pe: number): Analysis => ({ ...base, price: { ...base.price, ltp: 100 }, fundamentals: { ...base.fundamentals, sector: null, pe, eps_ttm: 5, dividend_per_share: null, dividend_yield_pct: null }, valuation: { ...base.valuation, rows: [], median_fair_value: null } });
  it("counts a low P/E as cheap only when it is also at or below the size-weighted market P/E", () => {
    const pe: PeContext = { marketMedian: 20, marketWeighted: 9, sector: null };
    expect(points(ev(a(8), undefined, pe), "value")).toBe(1); // below 0.7 x median and below the weighted P/E
    expect(points(ev(a(12), undefined, pe), "value")).toBe(0); // below the median, but above the size-weighted P/E
  });
});

describe("risk is not alarming for a single fair flag", () => {
  it("reads Moderate for a small free float and falling earnings on an otherwise sound large company", () => {
    const x: Analysis = { ...base, price: { ...base.price, ltp: 100 }, fundamentals: { ...base.fundamentals, free_float_pct: 10, category: "A" }, indicators: { ...base.indicators, vol_avg20: 1_000_000, atr14: 1 } };
    expect(tile(x, withRatios({ roe: 30, eps_growth: -19 }), "risk")?.rating).toBe("Moderate");
  });
});

describe("tile facts", () => {
  it("leave out debt / equity for a bank, where it means nothing", () => {
    const bank = { ...base, fundamentals: { ...base.fundamentals, sector: "Bank" } };
    const labels = (a: Analysis) => tile(a, withRatios({ roe: 12, debt_to_equity: 0.9 }), "quality")?.facts.map((f) => f.label) ?? [];
    expect(labels(bank)).not.toContain("Debt / equity");
    expect(labels({ ...base, fundamentals: { ...base.fundamentals, sector: "Textile" } })).toContain("Debt / equity");
  });
});

describe("strength against the market", () => {
  const rel = (stockPct: number, indexPct: number) => ({ stockPct, indexPct, diffPts: stockPct - indexPct, from: "2026-08-01", to: "2026-11-01" });
  const rs = (m3: ReturnType<typeof rel> | null): RelativeStrength => ({ m1: null, m3 });
  const timing = (r: RelativeStrength | null) => evidence(base, undefined, null, r).filter((x) => x.tile === "timing" && /market/i.test(x.text));
  it("counts beating the index by 5 points or more in the share's favour, in plain words with both numbers", () => {
    const [e] = timing(rs(rel(8, 1)));
    expect(e?.points).toBe(1);
    expect(e?.text).toBe("Beating the market: +8.0% in 3 months against +1.0% for the DSEX index.");
  });
  it("counts lagging it against the share, and moving with it as neutral", () => {
    expect(timing(rs(rel(-7, 1)))[0]?.points).toBe(-1);
    expect(timing(rs(rel(2, 0)))[0]).toMatchObject({ points: 0, text: expect.stringContaining("Moving with the market") });
  });
  it("adds nothing without the index", () => {
    expect(timing(null)).toHaveLength(0);
    expect(timing(rs(null))).toHaveLength(0);
  });
  it("shows the gap as a fact on the Timing tile", () => {
    const t = buildSummary(base, undefined, null, rs(rel(8, 1))).tiles.find((x) => x.key === "timing");
    expect(t?.facts).toContainEqual({ label: "Vs DSEX, 3 months", value: "+7.0 pts" });
  });
});

describe("epsTrend", () => {
  const years = (eps: Array<number | null>): Company => ({ ...company, per_share_history: eps.map((e, i) => ({ period_end: `${2018 + i}-12-31`, eps: e })) });
  it("is the last eight years of earnings per share, oldest first", () => {
    const t = epsTrend(years([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]));
    expect(t?.values).toEqual([3, 4, 5, 6, 7, 8, 9, 10]);
    expect([t?.first, t?.last]).toEqual(["2020", "2027"]);
  });
  it("skips years without a figure and needs at least three", () => {
    expect(epsTrend(years([1, null, 3, null, 5]))?.values).toEqual([1, 3, 5]);
    expect(epsTrend(years([1, 2]))).toBeUndefined();
    expect(epsTrend(undefined)).toBeUndefined();
  });
});
